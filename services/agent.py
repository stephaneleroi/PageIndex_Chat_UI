"""
Document Agent — voies de réponse fondées sur le raisonnement PageIndex.

Exécution par session :
  * single : une pièce → tree_search → lecture des nœuds → rédaction citée ;
  * kb     : dossier de pièces → sélection sur les fiches → lecture directe
             (ou map-reduce ciblé si le volume déborde le budget) → rédaction ;
  * libre  : aucun document → modèle nu (sans prompt système).
Une décomposition légère (decompose_query) scinde les questions composites et
aiguille chaque (sous-)question : overview → fiches ; detail → texte.
"""

import asyncio
import json
import logging
import os
import re
from typing import AsyncGenerator, List, Optional

from models.document import DocumentStore
from models.session import Message, SessionStore, session_store
from services.skill_manager import skill_manager
from services.prompt_templates import render_prompt

logger = logging.getLogger(__name__)

REFLECT_ACCEPT_THRESHOLD = 6

LANG_INSTRUCTION = (
    "Important: You MUST respond in French (français). All your output text, reasoning, "
    "analysis, and answers should be in French. "
    "When mentioning any mathematical symbol, variable, subscript, superscript, or formula, "
    "you MUST wrap them in LaTeX delimiters: use $...$ for inline math (e.g. $s_j$, $f_{MD}$, "
    "$t_{m,i}^{\\mathrm{loc}}$) and \\\\[...\\\\] for display/block math. "
    "NEVER output bare symbols like x_i or s_{j+1} without dollar signs."
)


# Style de la réponse finale (demande utilisateur) : prose continue collée à
# la question. Inspiré du prompt V5_BIS de l'utilisateur : interdits de
# format ÉNUMÉRÉS avec exception explicite, périmètre strict, et préservation
# des exigences de citation. Appliqué aux seuls prompts de RÉDACTION (le
# raisonnement interne du planificateur garde ses formats structurés).
STYLE_INSTRUCTION = (
    "Answer style (MUST follow):\n"
    "- Answer ONLY what is asked; no digressions, no unsolicited opinions or advice, "
    "no comments about the document, the question or your own answer.\n"
    "- No introduction, no recap conclusion, no politeness formulas.\n"
    "- Write in continuous prose with complete sentences. Do NOT use bullet points, "
    "numbered lists, tables, headings/subheadings or bold/italic emphasis — UNLESS the "
    "user explicitly asks for such a format or provides a template that uses one. "
    "When the user asks to DISTINGUISH or SEPARATE categories (e.g. « distingue bien "
    "X, Y et Z »), that IS an explicit structure request: organise the answer in one "
    "clearly headed section per requested category.\n"
    "- When the user asks for a chronology, a timeline or « le déroulé chronologique », "
    "order the events by ascending date and time (earliest first), never by document order.\n"
    "- These remain mandatory in all cases: inline citations `(node_<id>, page N)` and "
    "quotation marks around exact quotes.\n"
)

# Mode synthèse globale : une vue d'ensemble transversale, PAS une énumération
# pièce par pièce. Ajouté au prompt de rédaction quand la question est une
# demande de synthèse (cf. _is_global_summary).
GLOBAL_SUMMARY_INSTRUCTION = (
    "GLOBAL SUMMARY MODE (MUST follow):\n"
    "- The user wants ONE transversal synthesis of the WHOLE set, NOT a piece-by-piece list. "
    "Organise the answer BY THEME/topic, aggregating what recurs across pieces; give the overall "
    "picture (what it is about, the people involved, the timeline, the key facts).\n"
    "- Do NOT walk through the pieces one after another, and do NOT turn the answer into a "
    "catalogue. Still cite sources to support thematic statements `(doc: <filename>, node_<id>, "
    "page N)`, grouping several pieces in one citation when they share a point.\n"
)

# Grounding ASSOUPLI pour la synthèse globale : traçabilité SANS forcer une
# citation par phrase (ce qui poussait le modèle à énumérer les pièces) —
# citations groupées par thème.
# Prompts de grounding externalisés en gabarits Jinja (services/prompts/*.jinja) :
# c'est la surface de prompt qu'on itère et qu'on évalue → diff lisible, A/B aisé.
# La clause multi-doc du KB est intégrée au gabarit ; le texte est inchangé.
GROUNDING_INSTRUCTION_SUMMARY = render_prompt("grounding_summary")
GROUNDING_INSTRUCTION_SINGLE = render_prompt("grounding_single")
GROUNDING_INSTRUCTION_KB = render_prompt("grounding_kb")


class DocumentAgent:
    """Session-based agentic document Q&A."""

    def __init__(self, pageindex_service, store: DocumentStore,
                 sessions: SessionStore = session_store):
        self.pageindex = pageindex_service
        self.store = store
        self.sessions = sessions
        # Cache des fiches ciblées (map-reduce) : (doc_id, head_id, question) →
        # fiche|None. Évite de recalculer un map déjà fait (retry, reformulation,
        # sous-question répétée). Conservé le temps du process.
        self._focused_cache = {}

    # ============================================================ #
    #  Context / tool-context builders
    # ============================================================ #
    def _ensure_doc_loaded(self, doc_id: str):
        """Make sure tree/node_map/page_images for this doc are in memory."""
        doc = self.store.get_document(doc_id)
        if not doc or doc.status != "ready":
            return None

        tree = self.store.get_tree(doc_id)
        node_map = self.store.get_node_map(doc_id)
        page_images = self.store.get_page_images(doc_id)

        if tree and not node_map:
            page_count = doc.page_count or self.pageindex.get_pdf_page_count(doc.file_path)
            if page_count != doc.page_count:
                self.store.update_document(doc_id, page_count=page_count)
            node_map = self.pageindex.create_node_mapping(
                tree, include_page_ranges=True, max_page=page_count
            )
            self.store.cache_node_map(doc_id, node_map)
        return doc

    def _build_tool_context(self, mode: str, doc_ids: List[str],
                            primary_doc_id: Optional[str],
                            model_type: str) -> dict:
        docs_ctx = {}
        for doc_id in doc_ids:
            doc = self._ensure_doc_loaded(doc_id)
            if not doc:
                continue
            tree = self.store.get_tree(doc_id)
            node_map = self.store.get_node_map(doc_id)
            page_images = self.store.get_page_images(doc_id) or {}
            analysis = self.store.get_analysis(doc_id)
            docs_ctx[doc_id] = {
                "tree": tree,
                "node_map": node_map,
                "page_images": page_images,
                "filename": doc.filename,
                "folder": getattr(doc, 'folder', '') or '',
                "page_count": doc.page_count,
                "analysis": analysis,
            }

        return {
            "mode": mode,
            "primary_doc_id": primary_doc_id if primary_doc_id in docs_ctx else None,
            "accessible_doc_ids": list(docs_ctx.keys()),
            "docs": docs_ctx,
            "model_type": model_type,
        }

    def _build_docs_overview(self, tool_context: dict) -> str:
        """Build a short bullet list describing every accessible doc —
        used inside prompts so the LLM knows what's available without
        dumping full trees (progressive disclosure)."""
        docs = tool_context.get("docs") or {}
        if not docs:
            return "(no documents loaded)"
        lines = []
        for doc_id, d in docs.items():
            analysis = d.get("analysis") or {}
            summary_txt = (analysis.get("summary") or "").strip().replace("\n", " ")
            if summary_txt and len(summary_txt) > 200:
                summary_txt = summary_txt[:200] + "…"
            topics = ", ".join(analysis.get("main_topics") or []) or "—"
            folder = d.get('folder') or ''
            lines.append(
                f"- {doc_id} | {d.get('filename')} | {d.get('page_count', 0)} pages"
                + (f" | dossier: {folder}" if folder else "") + "\n"
                f"    summary: {summary_txt or '(no analysis)'}\n"
                f"    topics : {topics}"
            )
        return "\n".join(lines)

    def _single_doc_tree_summary(self, tool_context: dict) -> str:
        """For single-doc mode we can afford to inline the full TOC."""
        primary = tool_context.get("primary_doc_id")
        docs = tool_context.get("docs") or {}
        if not primary or primary not in docs:
            return ""
        tree = docs[primary].get("tree")
        if not tree:
            return ""
        return json.dumps(
            self.pageindex.remove_fields(tree, ["text"]),
            indent=2, ensure_ascii=False,
        )


    @staticmethod
    def _estimate_quality(answer: str, refs: List[str], tool_context: dict) -> Optional[dict]:
        """Note de qualité ESTIMÉE — déterministe, sans appel LLM, calculée
        pour chaque réponse fondée sur des documents. Mesure la forme
        vérifiable (sourçage, cohérence mécanique des renvois nœud/page,
        substance, absence de fuite technique) ; le fond reste du ressort de
        la vérification par juge LLM, déclenchée à la demande. Retourne None
        quand la réponse ne s'appuie sur aucune source (pas de badge)."""
        if not refs:
            return None
        text = answer or ""
        score, checks = 10, []

        cites = re.findall(
            r'\(\s*(doc:[^,]+,\s*)?node[_\s]*(\w+)\s*,\s*pages?[\s  ]*(\d+)', text)
        if len(text) < 200:
            score -= 3
            checks.append("réponse très courte")
        if '"thought"' in text or re.search(r'\b\w+\(\{"', text):
            score -= 5
            checks.append("texte technique parasite dans la réponse")

        if not cites:
            score -= 4
            checks.append("aucun renvoi à une pièce ou une page")
        else:
            checks.append(f"{len(cites)} citation(s)")
            # Cohérence mécanique des renvois, sans LLM : le nœud cité
            # fait-il partie des sources lues, et la page citée tombe-t-elle
            # dans la plage de pages de ce nœud (node_map) ?
            docs = tool_context.get("docs") or {}
            ref_nodes = {r.split('::')[-1] for r in refs}
            multi_doc = len(docs) > 1
            if multi_doc:
                # En multi-pièces, l'inventaire des fiches (nœud racine de
                # chaque document) est joint au rédacteur : citable même sans
                # lecture profonde.
                for d in docs.values():
                    nm = d.get("node_map") or {}
                    if nm:
                        ref_nodes.add(min(nm.keys()))
                # Une citation sans document est ambiguë quand la session
                # contient plusieurs pièces : la pastille ne peut pas être
                # résolue vers le bon fichier.
                sans_doc = sum(1 for doc_part, _, _ in cites if not doc_part)
                if sans_doc:
                    score -= 2
                    checks.append(f"{sans_doc} renvoi(s) sans indication du document (ambigu en multi-pièces)")
            bad_node = bad_page = 0
            for _, nid, page_s in cites:
                pad = nid.zfill(4) if nid.isdigit() else nid
                if pad not in ref_nodes:
                    bad_node += 1
                    continue
                info = None
                for d in docs.values():
                    nm = d.get("node_map") or {}
                    if pad in nm:
                        info = nm[pad]
                        break
                if info:
                    s_ = info.get("start_index") or 1
                    e_ = info.get("end_index") or s_
                    if not (s_ <= int(page_s) <= e_):
                        bad_page += 1
            if bad_node:
                score -= 2
                checks.append(f"{bad_node} renvoi(s) vers une section non consultée")
            if bad_page:
                score -= 2
                checks.append(f"{bad_page} renvoi(s) à une page hors de la section citée")
            if not bad_node and not bad_page:
                checks.append("renvois nœud/page cohérents")

        # Citations dégénérées : placeholder « source » ou crochets 【】 à la
        # place du vrai node_id. La regex `cites` ne les capture pas (elle
        # exige « node »), donc sans ce contrôle une réponse truffée de
        # citations cassées — pastilles pointant vers un mauvais nœud, ou
        # nulle part — pouvait afficher 10/10. On ne pénalise PAS les formes
        # « (page N) » / « (pages N-M) » seules, qui restent valides (le nœud
        # est déduit au clic).
        broken = len(re.findall(r'\bsource\s*,\s*pages?\s*\d', text, re.IGNORECASE))
        broken += text.count('【')
        if broken:
            score -= 2
            checks.append(f"{broken} renvoi(s) mal formé(s)")
        # `problems` = anomalies seules (on retire les items positifs : nombre de
        # citations, renvois cohérents). Sert à la pré-détection (besoin de vérif).
        problems = [c for c in checks
                    if not (re.fullmatch(r'\d+ citation\(s\)', c)
                            or c == 'renvois nœud/page cohérents')]
        return {"score": max(0, min(10, score)), "checks": checks, "problems": problems}

    # Mots/régex de pré-détection (déterministe, sans LLM).
    _EXHAUSTIVITY_RE = re.compile(
        r"(aucun(e)?\s+autre|rien\s+d['e]autre|c['e]est\s+tout|"
        r"il\s+n['e]y\s+a\s+pas\s+d['e]autre|aucun(e)?\s+\w+\s+suppl)", re.IGNORECASE)
    _REFUTES_RE = re.compile(
        r"(aucun(e)?\s+\w+\s+n['e]est|pas\s+de\s+\w+|n['e]existe\s+pas|"
        r"non\s+établi|tous?\s+(deux\s+)?majeurs?|sont\s+majeurs?|"
        r"n['e]y\s+a\s+pas\s+de)", re.IGNORECASE)

    def _predetect(self, query: str, answer: str, refs: list, tool_context: dict,
                   context: str = "", partial_context: bool = False) -> Optional[dict]:
        """Pré-détection DÉTERMINISTE (sans LLM), à chaque réponse, stockée sur le message.
        Produit deux choses :
          - `alerts` : anomalies **déjà tranchées** déterministiquement (citations + verbatim)
            → affichées telles quelles, gratuitement (« ce qui est peu coûteux intégré à la
            réponse ») ;
          - `scope` : vérificateurs **LLM recommandés** (sémantiques : présupposé, exhaustivité,
            complétude) — exécutés seulement au clic.
        Aucune vérification LLM n'est lancée ici."""
        q = self._estimate_quality(answer, refs, tool_context)
        if q is None:
            return None
        text = answer or ""
        alerts, scope, flags = [], [], []

        # === Alertes DÉTERMINISTES (résolues ici, sans modèle) ===
        # Citations : nœud hors sources lues / page hors plage / mal formée (cf. problems).
        alerts += [{"type": "citations", "label": p} for p in (q.get("problems") or [])]
        # Verbatim : chaque phrase entre guillemets doit exister mot pour mot dans les
        # sources lues. On TRANCHE ici (déterministe) au lieu de seulement « flaguer ».
        if context:
            for s in self._verbatim_issues(answer, context):
                alerts.append({"type": "verbatim",
                               "label": f"Passage entre guillemets « {s} » introuvable tel quel dans les pièces (citation peut-être inexacte)."})

        # === Vérificateurs LLM RECOMMANDÉS (sémantiques — au clic) ===
        # Présupposé : la question présuppose une entité/un rôle (`_question_presupposes`)
        # ET la réponse ne le réfute pas déjà (`_REFUTES_RE`) → risque de confabulation.
        if self._question_presupposes(query) and not self._REFUTES_RE.search(text):
            scope.append("presupposition")
            flags.append({"scope": "presupposition",
                          "label": "La question suppose une personne ou un élément précis "
                                   "(ex. « le mineur ») : vérifier qu'il figure bien dans les "
                                   "pièces, pour éviter une réponse qui l'inventerait."})
        # Exhaustivité : la réponse affirme une absence/exhaustivité (« aucun autre »…) →
        # invérifiable sur un contexte possiblement partiel.
        if self._EXHAUSTIVITY_RE.search(text):
            scope.append("exhaustivity")
            flags.append({"scope": "exhaustivity",
                          "label": "La réponse affirme qu'il n'y a rien d'autre : comme les "
                                   "pièces consultées peuvent être incomplètes, à confronter au dossier."})
        # Complétude : réponse construite sur un contexte partiel (map-reduce / décomposition).
        if partial_context:
            scope.append("completeness")
            flags.append({"scope": "completeness",
                          "label": "La réponse a été assemblée à partir d'extraits du dossier : "
                                   "des éléments ont pu être laissés de côté."})

        q.update({
            "alerts": alerts,             # déterministe, à afficher tel quel
            "scope": scope,               # vérificateurs LLM recommandés
            "flags": flags,               # libellés des recommandations
            "need_verify": bool(scope),   # propose « Vérifier le fond »
        })
        return q

    # ============================================================ #
    #  Direction 4: Self-reflection
    # ============================================================ #
    # NB : méthode d'INSTANCE (utilise self.pageindex) et appelée self.reflect(...).
    # Surtout PAS @staticmethod — sinon `self` capte le 1er argument (la question),
    # `self.pageindex` lève une AttributeError, et l'except renvoyait toujours le
    # défaut {score:7, action:accept} → l'auto-évaluation ne s'exécutait jamais.
    async def reflect(self, query: str, answer: str,
                      context_summary: str,
                      model_type: str = "text",
                      is_vision: bool = False,
                      docs_overview: str = "") -> dict:
        vision_note = ""
        if is_vision:
            vision_note = (
                "\nIMPORTANT: The answer was generated using a vision model that can "
                "directly read page images. Data from images is valid evidence even if "
                "it's not in the text context.\n"
            )

        docs_section = ""
        if docs_overview:
            docs_section = (
                "\nAvailable documents — metadata the answerer can cite directly "
                "(filename / page count / doc_id). Meta-questions like “how many "
                "documents / which documents / page counts” can be answered purely "
                "from this block without any tool observation:\n"
                f"{docs_overview[:24000]}\n"
            )

        prompt = f"""Evaluate this answer's quality.

Question: {query}
{vision_note}
{docs_section}
Context used (tool observations):
{context_summary[:30000]}

Generated answer:
{answer[:3000]}

Check:
1. Does the answer address the question?
2. Is the answer supported by the context OR by the Available-documents metadata above? (For vision mode, image data is also valid.)
3. Are there factual inconsistencies between the answer and the context/metadata?
4. Is important information missing?
5. FALSE PRESUPPOSITION: does the answer affirm an entity, role, status, date or fact that the question merely PRESUPPOSED, but that the context does NOT establish (or that it contradicts)? Example: the question asks for "le mineur mis en cause" and the answer names someone as the minor, while the context describes every person as "Majeur" / never establishes any minor. The wording of the question is NOT evidence that the thing exists. If the answer designates such a non-established entity instead of stating it is absent, this is a serious defect: set "score" <= 3 and "action": "retry", and put the discrepancy in "issues" (e.g. "Aucun mineur n'est établi par les pièces : ne pas en désigner un ; indiquer que les personnes citées sont toutes majeures.").

Note: If the question is a meta-question about the document set itself
(e.g. how many documents, document names, page counts), the Available-documents
metadata alone is sufficient evidence — do NOT penalise the answer for lacking
tool observations in that case.

{LANG_INSTRUCTION}

Output JSON only:
{{
    "score": <1-10>,
    "issues": ["décris le problème 1 en français", ...],
    "missing_info": ["décris l'information manquante en français"],
    "action": "accept" or "retry"
}}"""
        try:
            raw = await self.pageindex.call_llm(prompt, 'text')
            raw = self._extract_json_str(raw)
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Reflection parse failed: {e}")
            return {"score": 7, "issues": [], "missing_info": [], "action": "accept"}

    async def _presupposition_violation(self, query: str, answer: str,
                                        context: str, model_type: str = "text",
                                        votes: int = 3):
        """Vérificateur DÉDIÉ et ÉTROIT (≠ reflect omnibus) : la réponse désigne-t-elle
        une entité / un rôle / un statut / une date PRÉSUPPOSÉ(E) par la question, mais
        que les sources n'ÉTABLISSENT pas (ou contredisent) ? Multi-vote à la MAJORITÉ
        (plus fiable que le jugement unique de reflect). Renvoie une consigne de
        correction (str) si violation majoritaire, sinon None."""
        prompt = (
            "Tu vérifies UN SEUL point, rien d'autre.\n"
            f"QUESTION posée : {query}\n\n"
            f"RÉPONSE produite :\n{(answer or '')[:2500]}\n\n"
            f"EXTRAIT DES SOURCES (seule vérité admise) :\n{(context or '')[:12000]}\n\n"
            "La RÉPONSE désigne-t-elle une entité, un rôle, un statut ou une date que la "
            "QUESTION PRÉSUPPOSE, mais que les SOURCES n'ÉTABLISSENT PAS (ou contredisent) ? "
            "Exemple : la question demande « le mineur » et la réponse nomme quelqu'un comme "
            "mineur, alors que les sources décrivent toutes les personnes comme majeures ou "
            "n'établissent aucun mineur. Le libellé de la question ne prouve RIEN ; l'absence "
            "d'établissement par les sources suffit à constituer une violation.\n"
            "IMPORTANT : si la RÉPONSE indique DÉJÀ que l'entité présupposée est absente / non "
            "établie (réfutation correcte du présupposé), alors il n'y a PAS de violation "
            "(violation:false).\n"
            'Réponds UNIQUEMENT en JSON : {"violation": true|false, "correction": '
            '"<ce que la réponse devrait dire à la place, une phrase>"}'
        )

        async def _one():
            try:
                raw = await self.pageindex.call_llm(prompt, 'text')
                return json.loads(self._extract_json_str(raw))
            except Exception:
                return None

        results = await asyncio.gather(*[_one() for _ in range(max(1, votes))])
        viol = [r for r in results if r and r.get("violation")]
        if len(viol) * 2 <= max(1, votes):       # pas de majorité stricte → OK
            return None
        return next((v.get("correction") for v in viol if v.get("correction")), "") \
            or "L'entité présupposée par la question n'est pas établie par les pièces ; le dire explicitement."

    # ============================================================ #
    #  Direction 5: Proactive document analysis
    # ============================================================ #
    async def analyze_document(self, doc_id: str,
                               model_type: str = "text") -> dict:
        tree = self.store.get_tree(doc_id)
        if not tree:
            return {}

        tree_summary = json.dumps(
            self.pageindex.remove_fields(tree, ["text"]),
            indent=2, ensure_ascii=False,
        )

        prompt = f"""You are analyzing a document based on its structure.
Provide a comprehensive analysis.

Document structure:
{tree_summary[:6000]}

{LANG_INSTRUCTION}

Output JSON only:
{{
    "summary": "résume en 2-3 phrases en français le contenu principal du document",
    "key_findings": ["constat clé 1", "constat clé 2", "constat clé 3"],
    "main_topics": ["thème 1", "thème 2"],
    "suggested_questions": [
        "question 1 en français qu'un lecteur pourrait poser",
        "question 2 en français",
        "question 3 en français",
        "question 4 en français",
        "question 5 en français"
    ]
}}"""
        try:
            raw = await self.pageindex.call_llm(prompt, 'text')
            raw = self._extract_json_str(raw)
            analysis = json.loads(raw)
        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            analysis = {
                "summary": "Analysis could not be generated.",
                "key_findings": [],
                "main_topics": [],
                "suggested_questions": [],
            }

        doc = self.store.get_document(doc_id)
        if doc:
            try:
                os.makedirs(doc.result_dir, exist_ok=True)
                with open(doc.analysis_path, "w", encoding="utf-8") as f:
                    json.dump(analysis, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to save analysis: {e}")

        return analysis

    # ============================================================ #
    #  Main entry: run_session (handles both single and kb modes)
    # ============================================================ #
    # ============================================================ #
    #  Voie simple mono-document — pipeline canonique PageIndex
    #  (cookbook/pageindex_RAG_simple.ipynb)
    # ============================================================ #
    # Défaut 60000 ; surchargeable par env (PAGEINDEX_CTX_BUDGET) pour forcer la
    # bascule map-reduce en test sans toucher au code (cf. skill evaluer-reponse-sourcee).
    SIMPLE_CONTEXT_BUDGET = int(os.environ.get("PAGEINDEX_CTX_BUDGET", "60000"))  # caractères de texte source pour le rédacteur
    SIMPLE_MAX_NODES = 10

    # ---- Voie corpus (le dossier EST un arbre PageIndex) ----
    # Un seul tree_search sur les fiches de toutes les pièces.
    CORPUS_SELECT_BUDGET = 48000    # budget total des fiches dans l'arbre de sélection
    PIECE_NOTES_BUDGET = 800        # sous-budget des notes descriptives ajoutées à une fiche de sélection
    CORPUS_INVENTORY_BUDGET = 45000  # budget total de l'inventaire joint au rédacteur
    CORPUS_MAX_PIECES_READ = 12     # pièces lues en intégral (le reste : citable via l'inventaire)
    CORPUS_PIECE_DRILL_THRESHOLD = 20000  # au-delà, une pièce composite est sélectionnée
    #   section par section (tree_search interne) au lieu d'être lue en entier (hiérarchie niv. 2)
    # Synthèses ciblées (map) concurrentes max (santé Ollama). Surchargeable par env :
    # aligner sur OLLAMA_NUM_PARALLEL, ou pousser plus haut derrière vLLM (continuous batching).
    MAP_CONCURRENCY = int(os.environ.get("MAP_CONCURRENCY", "3"))

    def _build_simple_answer_prompt(self, query, context, history_context, grounding,
                                    allowed_citations: str = "", user_consignes: str = ""):
        return f"""Answer the question based on the context below — the selected sections of the
document. Their text is wrapped in <page_N>…</page_N> markers.

Question: {query}

Context:
{context}
{history_context}
{user_consignes}
{LANG_INSTRUCTION}

{grounding}
{allowed_citations}
{STYLE_INSTRUCTION}

Provide a clear, comprehensive answer in French."""

    async def _run_single_simple(self, session_id, query, model_type,
                                 use_memory, tool_context, context_overview,
                                 persist=True, intent=None):
        """UNE recherche par raisonnement sur l'arbre → lecture des nœuds
        retenus → rédaction. Pas de décomposition, pas de boucle ReAct.
        L'auto-évaluation reste comme garde-fou, avec au plus UNE expansion
        bornée (tree_search complémentaire sur les manques signalés)."""
        # Demande de synthèse globale → vue d'ensemble transversale sur les
        # résumés de toutes les sections (pas de sélection top-k).
        # Aiguillage : l'intention classée à la décomposition prime ; à défaut
        # (intent=None), repli sur l'heuristique par mots-clés.
        use_global = ((intent == "overview") if intent in ("overview", "detail")
                      else self._is_global_summary(query))
        if use_global:
            async for chunk in self._run_global_summary(
                    session_id, query, model_type, use_memory, tool_context,
                    context_overview, persist=persist):
                yield chunk
            return
        doc_id = tool_context["primary_doc_id"]
        dctx = tool_context["docs"][doc_id]
        tree = dctx["tree"]
        node_map = dctx.get("node_map") or {}
        is_vision = model_type != "text"

        def _node_text(nid):
            info = node_map.get(nid, {})
            node = info.get("node", info)
            return (node.get("text") or "") if isinstance(node, dict) else ""

        async def _search(q, exclude):
            res = await self.pageindex.tree_search(q, tree)
            nl = [n for n in (res.get("node_list") or [])
                  if n in node_map and n not in exclude][:self.SIMPLE_MAX_NODES]
            return nl, (res.get("thinking") or "").strip()

        def _assemble(nids):
            # Each section is headed by its REAL node id — the writer must
            # cite "(node_<id>, page N)" and can't invent ids it never saw.
            parts, dropped, used = [], [], 0
            for nid in nids:
                t = _node_text(nid)
                if not t:
                    continue
                if used + len(t) > self.SIMPLE_CONTEXT_BUDGET and parts:
                    dropped.append(nid)
                    continue
                block = f"=== Section node_{nid} ===\n" + t[: self.SIMPLE_CONTEXT_BUDGET - used]
                parts.append(block)
                used += len(block)
            return "\n\n".join(parts), dropped

        # ---- 1. Recherche par raisonnement sur l'arbre ----
        yield "[SEARCHING]\n"
        node_list, thinking = await _search(query, set())
        yield self._step_marker(
            0, 0, thinking, "tree_search", {"query": query},
            f"[doc={doc_id}] {len(node_list)} nœud(s) retenu(s) : {', '.join(node_list) or '—'}",
        )

        # ---- 2. Lecture des nœuds retenus (budget de contexte) ----
        context, dropped = _assemble(node_list)
        logger.info(
            f"voie simple [doc={doc_id}]: nœuds retenus={node_list or '—'}, "
            f"contexte={len(context)} caractères"
            + (f", nœuds écartés (budget)={dropped}" if dropped else "")
        )

        refs = [f"{doc_id}::{n}" for n in node_list]
        if refs:
            yield f"\n[NODES]{json.dumps(refs)}\n"

        # ---- 3. Rédaction ----
        yield "[ANSWERING]\n"
        history_context = self._build_history_context(session_id, use_memory)
        answer_prompt = self._build_simple_answer_prompt(
            query, context, history_context, GROUNDING_INSTRUCTION_SINGLE,
            allowed_citations=self._build_allowed_citations(refs, tool_context),
            user_consignes=self._build_user_consignes(refs, tool_context))

        full_answer = ""
        image_paths = self._collect_images_for_refs(refs, tool_context) if is_vision else []
        if is_vision and image_paths:
            vision_prompt = self._build_vision_answer_prompt(
                query, [query], history_context, "direct",
                gathered_context=context,
                grounding=GROUNDING_INSTRUCTION_SINGLE,
                mode="single", docs_overview=context_overview,
            )
            async for chunk in self.pageindex.call_vlm_stream(vision_prompt, image_paths, model_type):
                full_answer += chunk
                yield chunk
        else:
            async for chunk in self.pageindex.call_llm_stream(answer_prompt, model_type):
                full_answer += chunk
                yield chunk

        # La rédaction est terminée : le front peut rendre la réponse
        # exploitable (pastilles) sans attendre l'éventuelle auto-évaluation.
        yield "[ANSWER_DONE]\n"

        # En sous-question (décomposition), run_session gère la persistance et
        # l'évaluation sur la réponse assemblée — la voie ne le fait pas ici.
        if not persist:
            return

        self.sessions.add_message(session_id, Message(role="user", content=query))
        self.sessions.add_message(session_id, Message(
            role="assistant", content=full_answer, nodes=refs,
            thinking=(f"Step 1 [tree_search]: {thinking}" if thinking else ""),
            quality=self._predetect(query, full_answer, refs, tool_context, context=context),
        ))

        # Vérification : À LA DEMANDE uniquement (bouton « Vérifier », curseur de
        # profondeur). Aucune vérification LLM automatique ici → réponse rapide. Voir
        # POST /sessions/<id>/messages/<i>/verify (reflect + vérificateur de présupposé
        # + re-rédaction selon le niveau). Le badge déterministe (`_estimate_quality`)
        # reste calculé ci-dessus.

    # Unité de travail = la PIÈCE (un sous-arbre de premier niveau), pas le
    # fichier : un répertoire de N fichiers et un fichier de N pièces donnent
    # alors le même résultat. Repli sûr : 1 pièce = le document entier.
    USE_PIECE_UNIT = True

    @staticmethod
    def _subtree_nodes(node: dict) -> list:
        """Nœud de tête + tous ses descendants, en ordre de lecture."""
        out = [node]
        for c in node.get("nodes") or []:
            out.extend(DocumentAgent._subtree_nodes(c))
        return out

    @staticmethod
    def _piece_heads(tree) -> list:
        """Têtes des pièces d'un arbre : liste de ≥2 racines → autant de pièces ;
        racine unique englobante → enfants du conteneur de pièces numérotées
        (Document/Pièce/Annexe/Rapport N) ; sinon une seule pièce (le document)."""
        roots = tree if isinstance(tree, list) else ([tree] if tree else [])
        if len(roots) >= 2:
            return roots
        if not roots:
            return []
        root = roots[0]
        for container in [root] + (root.get("nodes") or []):
            kids = container.get("nodes") or []
            numbered = [k for k in kids
                        if re.match(r"^\s*(?:document|pi[eè]ce|annexe|rapport)\s",
                                    (k.get("title") or ""), re.IGNORECASE)]
            if len(numbered) >= 2:
                return kids
        return [root]

    def _extract_pieces(self, tool_context: dict) -> list:
        """Liste des PIÈCES de tous les documents. Chaque pièce conserve son
        VRAI doc_id (pour des citations `doc::node` exactes) et la liste ordonnée
        de ses node_ids. Repli sûr : un document non découpable = une pièce."""
        pieces = []
        for doc_id, dctx in (tool_context.get("docs") or {}).items():
            tree = dctx.get("tree")
            filename = dctx.get("filename", doc_id)
            heads = self._piece_heads(tree)
            single = len(heads) <= 1
            for h in heads:
                node_ids = [n.get("node_id") for n in self._subtree_nodes(h) if n.get("node_id")]
                if not node_ids:
                    continue
                title = filename if single else ((h.get("title") or "").strip() or filename)
                pieces.append({
                    "doc_id": doc_id, "filename": filename, "title": title,
                    "head_id": h.get("node_id"), "head_node": h, "node_ids": node_ids,
                })
        return pieces

    def _piece_fiche(self, piece: dict, tool_context: dict, budget: int,
                     notes_by_doc: Optional[dict] = None) -> str:
        """Fiche de sélection d'une pièce : résumé de son nœud de tête + titres
        de ses sous-sections + NOTES DESCRIPTIVES de l'utilisateur (pour que le
        tree_search « voie » le contenu — y compris ce que l'humain signale).
        Les notes descriptives portent un sous-budget propre, AJOUTÉ après la
        troncature de la fiche : un signal humain n'est jamais évincé par une
        fiche longue."""
        nm = (tool_context.get("docs") or {}).get(piece["doc_id"], {}).get("node_map") or {}
        head = nm.get(piece["head_id"]) or {}
        hnode = head.get("node", head)
        fiche = (hnode.get("summary") or "").strip() if isinstance(hnode, dict) else ""
        titres = []
        for nid in piece["node_ids"][1:]:
            n = (nm.get(nid) or {}).get("node", {})
            t = (n.get("title") or "").strip() if isinstance(n, dict) else ""
            if t:
                titres.append(f"- {t}")
        if titres:
            fiche = (fiche + "\nSections :\n" + "\n".join(titres)).strip()
        if len(fiche) > budget:
            fiche = fiche[:budget] + "…"
        notes = self._piece_descr_notes(piece, notes_by_doc)
        if notes:
            body = "\n".join(f"- {t}" for t in notes)
            if len(body) > self.PIECE_NOTES_BUDGET:
                body = body[:self.PIECE_NOTES_BUDGET] + "…"
            fiche = (fiche + "\nNotes de l'utilisateur sur cette pièce :\n" + body).strip()
        return fiche or "(pas de fiche)"

    def _selection_fiche(self, dctx: dict, budget: int) -> str:
        """Fiche de sélection (niveau 1) d'une pièce : résumé du nœud racine, +
        pour une pièce COMPOSITE, les titres de ses sous-sections — sinon le
        tree_search de niveau 1 ne « voit » pas le contenu profond (cas réel :
        un en-tête ministériel masquant un sujet de concours et ses documents)."""
        nm = dctx.get("node_map") or {}
        if not nm:
            return "(pas de fiche)"
        keys = sorted(nm.keys())
        root = nm[keys[0]]
        rnode = root.get("node", root)
        fiche = (rnode.get("summary") or "").strip() if isinstance(rnode, dict) else ""
        if len(keys) > 1:
            titres = []
            for k in keys[1:]:
                node = nm[k].get("node", nm[k])
                t = (node.get("title") or "").strip() if isinstance(node, dict) else ""
                if t:
                    titres.append(f"- {t}")
            if titres:
                fiche = (fiche + "\nSections :\n" + "\n".join(titres)).strip()
        return (fiche[:budget] + "…") if len(fiche) > budget else (fiche or "(pas de fiche)")

    def _build_user_consignes(self, refs, tool_context, budget: int = 6000) -> str:
        """Bloc de CONSIGNES utilisateur (notes kind='consigne') pour la
        rédaction. Une consigne n'est NI une source NI une pièce : elle ORIENTE
        la réponse (comment répondre) — jamais citée, jamais traitée comme une
        preuve. Les notes 'desc' (qui décrivent la pièce) en sont exclues :
        elles servent la SÉLECTION (fiche niveau 1 / épinglage), pas la rédaction."""
        docs_ctx = tool_context.get("docs") or {}
        doc_ids, lines = [], []
        for r in refs or []:
            d = str(r).split("::")[0]
            if d and d not in doc_ids:
                doc_ids.append(d)
        for doc_id in doc_ids:
            try:
                notes = self.store.get_notes(doc_id) or {}
            except Exception:
                notes = {}
            nm = (docs_ctx.get(doc_id) or {}).get("node_map") or {}
            for node_id, lst in notes.items():
                node = (nm.get(node_id) or {}).get("node", {})
                title = (node.get("title") if isinstance(node, dict) else "") or node_id
                for n in (lst or []):
                    if n.get("kind", "desc") != "consigne":
                        continue
                    t = (n.get("text") or "").strip()
                    if t:
                        lines.append(f"- [{title}] {t}")
        if not lines:
            return ""
        body = "\n".join(lines)
        if len(body) > budget:
            body = body[:budget] + "…"
        return (
            "\n【Consignes de l'utilisateur (ses notes) — ORIENTENT la rédaction】\n"
            "Ce sont des consignes / une pré-rédaction de l'utilisateur, PAS des "
            "sources : ne les cite JAMAIS, ne les traite pas comme une preuve. "
            "Tiens-en compte pour le cadrage et la mise en avant ; si une consigne "
            "contredit le contexte sourcé, suis le SOURCE.\n" + body + "\n"
        )

    def _piece_descr_notes(self, pc, notes_by_doc: Optional[dict]) -> list:
        """Textes des notes DESCRIPTIVES (kind='desc') de la pièce — celles qui
        décrivent son contenu. Servent à la fois à la fiche de sélection
        (_piece_fiche) et à l'épinglage (_piece_has_notes). Les notes 'consigne'
        (comment répondre) en sont exclues : elles ne décrivent pas la pièce."""
        notes = (notes_by_doc or {}).get(pc["doc_id"], {})
        out = []
        for nid in pc.get("node_ids", []):
            for n in (notes.get(nid) or []):
                if n.get("kind", "desc") == "desc":
                    t = (n.get("text") or "").strip()
                    if t:
                        # La page (si saisie sur une page) accompagne la note pour
                        # le CONTEXTE de sélection — façon « point saillant ». Elle
                        # n'est PAS citée : la note reste hors du contexte sourcé.
                        p = n.get("page")
                        out.append(f"{t} (p. {p})" if p else t)
        return out

    def _piece_has_notes(self, pc, notes_by_doc: dict) -> bool:
        """Vrai si une note DESCRIPTIVE annote cette pièce (→ épinglage)."""
        return bool(self._piece_descr_notes(pc, notes_by_doc))

    def _build_corpus_inventory(self, tool_context: dict) -> str:
        """Inventaire des fiches identitaires de TOUTES les pièces — source
        citable en appui (synthèse de corpus). Budget PAR FICHE adaptatif
        (budget_total // N) pour tenir à grande échelle (70+ pièces) sans
        tronquer la liste des pièces."""
        pieces = self._extract_pieces(tool_context)
        if not pieces:
            return ""
        per_fiche = max(300, self.CORPUS_INVENTORY_BUDGET // max(1, len(pieces)))
        lines = []
        for pc in pieces:
            nm = (tool_context.get("docs") or {}).get(pc["doc_id"], {}).get("node_map") or {}
            info = nm.get(pc["head_id"]) or {}
            node = info.get("node", info)
            summary = (node.get("summary") or "").strip() if isinstance(node, dict) else ""
            if len(summary) > per_fiche:
                summary = summary[:per_fiche] + "…"
            s, e = info.get("start_index"), info.get("end_index")
            pages = f"pages {s}-{e}" if s and e and s != e else f"page {s or 1}"
            lines.append(f"📄 {pc['filename']} — {pc['title']} (node_{pc['head_id']}, {pages})\n{summary}")
        if not lines:
            return ""
        return ("【Inventaire des pièces — fiche identitaire de CHAQUE document de la session. "
                "Source citable au même titre que les extraits : cite "
                "`(doc: <fichier>, node_<id>, page N)` avec le fichier et le node de la ligne 📄 "
                "de la pièce concernée.】\n" + "\n\n".join(lines))

    async def _focused_summary(self, title, doc_id, nid, node_text, question,
                               model_type, instructions=None):
        """MAP (map-reduce ciblé) : résumé d'UN nœud orienté par la question, en
        CONSERVANT les pages « (p. N) » (depuis les <page_N>) pour que le reduce
        puisse citer. Renvoie None si la pièce n'apporte rien d'utile à la
        question (pour ne pas polluer la compilation).

        `instructions` (optionnel) = consigne d'extraction propre à cette
        (sous-)question, issue de la décomposition : on dit au map CE QU'IL DOIT
        extraire de cette pièce, et non plus seulement « ce qui répond »."""
        prompt = render_prompt(
            "focused_summary", question=question, node_text=node_text,
            instructions=instructions or "")
        try:
            out = (await self.pageindex.call_llm(prompt, model_type) or "").strip()
        except Exception as e:
            logger.warning(f"_focused_summary échec ({title}/{nid}) : {e}")
            return None
        if not out or out.lower().startswith("(rien"):
            return None
        return {"title": title, "doc_id": doc_id, "nid": nid, "text": out}

    async def _run_corpus_simple(self, session_id, query, model_type, use_memory,
                                 tool_context, context_overview, persist=True,
                                 intent=None, instructions=None):
        """Le dossier EST un arbre PageIndex : UN seul tree_search sur les
        fiches de toutes les pièces (au lieu d'un cross_search par document),
        lecture intégrale des pièces retenues, rédaction citée avec l'inventaire
        complet en appui. Généralise la voie simple mono-document au corpus.

        Échelle (70+ pièces) : fiches de sélection et inventaire à budget par
        fiche adaptatif ; nombre de pièces lues en intégral borné (les autres
        restent citables via l'inventaire)."""
        docs = tool_context["docs"]
        is_vision = model_type != "text"

        # Demande de synthèse globale → vue d'ensemble transversale sur les
        # fiches de toutes les pièces (pas de tree_search ni de lecture).
        # Aiguillage : l'intention classée à la décomposition prime ; à défaut
        # (intent=None), repli sur l'heuristique par mots-clés.
        use_global = ((intent == "overview") if intent in ("overview", "detail")
                      else self._is_global_summary(query))
        if use_global:
            async for chunk in self._run_global_summary(
                    session_id, query, model_type, use_memory, tool_context,
                    context_overview, persist=persist):
                yield chunk
            return

        # ---- 1. Arbre de sélection : une entrée par PIÈCE (alias court) ----
        # Notes utilisateur chargées une fois : les notes DESCRIPTIVES enrichissent
        # la fiche de sélection (tree_search les « voit ») ; réutilisées plus bas
        # pour l'épinglage (filet de sécurité). Les notes 'consigne' n'entrent pas ici.
        pieces = self._extract_pieces(tool_context)
        notes_by_doc = {}
        for pc in pieces:
            did = pc["doc_id"]
            if did not in notes_by_doc:
                try:
                    notes_by_doc[did] = self.store.get_notes(did) or {}
                except Exception:
                    notes_by_doc[did] = {}
        per_fiche = max(300, self.CORPUS_SELECT_BUDGET // max(1, len(pieces)))
        children = []
        for i, pc in enumerate(pieces):
            children.append({"node_id": f"p{i}", "title": pc["title"],
                             "summary": self._piece_fiche(pc, tool_context, per_fiche, notes_by_doc)})
        corpus_tree = {"node_id": "root", "title": "Dossier",
                       "summary": "Racine du dossier ; chaque enfant est une pièce.",
                       "nodes": children}

        # ---- 2. UNE recherche par raisonnement sur les fiches des pièces ----
        yield "[SEARCHING]\n"
        res = await self.pageindex.tree_search(query, corpus_tree)
        picked_idx = []
        for a in (res.get("node_list") or []):
            a = str(a)
            j = a[1:] if a[:1] == "p" else a
            if j.isdigit() and 0 <= int(j) < len(pieces):
                picked_idx.append(int(j))
        picked = [pieces[j] for j in dict.fromkeys(picked_idx)][:self.CORPUS_MAX_PIECES_READ]
        # Épinglage (filet de sécurité) : une pièce portant une note DESCRIPTIVE
        # (signal humain « ça compte ») est priorisée même si tree_search ne l'a
        # pas retenue — en complément de son injection dans la fiche de sélection.
        pinned = [pc for pc in pieces if pc not in picked and self._piece_has_notes(pc, notes_by_doc)]
        if pinned:
            picked = (picked + pinned)[:self.CORPUS_MAX_PIECES_READ]
        thinking = (res.get("thinking") or "").strip()
        yield self._step_marker(
            0, 0, thinking, "tree_search", {"query": query},
            f"{len(picked)} pièce(s) retenue(s)"
            + (f" (dont {len(pinned)} épinglée(s) par vos notes)" if pinned else "")
            + " : " + (", ".join(pc["title"] for pc in picked) or "—"),
        )

        # ---- 3. Sélection fine des nœuds retenus. Hiérarchie niveau 2 : une
        # pièce COMPOSITE volumineuse est sélectionnée section par section
        # (tree_search interne) au lieu d'être prise en entier. Les refs portent
        # le VRAI doc_id de la pièce → citations `doc::node` exactes. ----
        selected = []  # (doc_id, title, head_id, nid, text)
        for pc in picked:
            doc_id = pc["doc_id"]
            title = pc["title"]
            head_id = pc["head_id"]
            nm = (docs.get(doc_id) or {}).get("node_map") or {}
            piece_nids = [nid for nid in pc["node_ids"] if nid in nm]
            piece_len = sum(len((nm[nid].get("node", nm[nid]).get("text") or ""))
                            for nid in piece_nids)
            if len(piece_nids) > 1 and piece_len > self.CORPUS_PIECE_DRILL_THRESHOLD:
                sub = await self.pageindex.tree_search(query, pc["head_node"])
                hit = [n for n in (sub.get("node_list") or []) if n in piece_nids]
                nids = hit or piece_nids
                yield self._step_marker(
                    0, 0, (sub.get("thinking") or "").strip(), "tree_search",
                    {"doc_id": doc_id},
                    f"[{title}] pièce volumineuse : {len(nids)} section(s) retenue(s)")
            else:
                nids = piece_nids
            for nid in nids:
                info = nm.get(nid)
                if not info:
                    continue
                node = info.get("node", info)
                text = (node.get("text") or "") if isinstance(node, dict) else ""
                if text:
                    selected.append((doc_id, title, head_id, nid, text))

        total_len = sum(len(t) for *_, t in selected)

        # ---- 4. AIGUILLAGE lecture directe vs MAP-REDUCE ciblé. Si le texte des
        # nœuds retenus tient dans le budget → lecture directe (rapide, défaut).
        # Sinon → map-reduce orienté requête : chaque PIÈCE retenue (sous-arbre de
        # niveau 1 — même granularité que les fiches génériques) est résumée SOUS
        # L'ANGLE de la question (pages conservées), puis la rédaction porte sur
        # ces synthèses ciblées — la couverture n'est plus plafonnée par un
        # contexte unique. Les fiches ciblées sont MISES EN CACHE (réutilisées sur
        # retry / reformulation / sous-question répétée). ----
        use_map_reduce = total_len > self.SIMPLE_CONTEXT_BUDGET and len(selected) > 1
        if use_map_reduce:
            # Regroupement par PIÈCE : une fiche ciblée par sous-arbre de niveau 1.
            order, by_piece = [], {}
            for doc_id, title, head_id, nid, text in selected:
                key = (doc_id, head_id)
                if key not in by_piece:
                    by_piece[key] = {"title": title, "texts": []}
                    order.append(key)
                by_piece[key]["texts"].append(text)
            yield self._step_marker(
                0, 0, "", "map_reduce", {"query": query},
                f"{len(order)} pièce(s) ({total_len} car.) > budget "
                f"{self.SIMPLE_CONTEXT_BUDGET} → synthèse ciblée par pièce")
            sem = asyncio.Semaphore(self.MAP_CONCURRENCY)

            async def _map(doc_id, head_id, title, text):
                ckey = (doc_id, head_id, query, instructions)
                if ckey in self._focused_cache:          # déjà calculée → réutiliser
                    return self._focused_cache[ckey]
                async with sem:
                    fiche = await self._focused_summary(
                        title, doc_id, head_id, text, query, model_type,
                        instructions=instructions)
                self._focused_cache[ckey] = fiche         # cache mémoire (anti-recalcul)
                if fiche:                                 # persiste sur disque (homogène avec les notes)
                    self.store.save_focused_fiche(
                        doc_id, head_id, query,
                        fiche.get("text", ""), fiche.get("nid", head_id))
                return fiche

            tasks = []
            for key in order:
                doc_id, head_id = key
                pc = by_piece[key]
                text = "\n\n".join(pc["texts"])[: self.SIMPLE_CONTEXT_BUDGET]
                tasks.append(asyncio.create_task(_map(doc_id, head_id, pc["title"], text)))
            fiches, done_n = [], 0
            for coro in asyncio.as_completed(tasks):
                fiche = await coro
                done_n += 1
                if fiche:
                    fiches.append(fiche)
                yield self._step_marker(
                    0, 0, "", "map_reduce", {},
                    f"synthèses ciblées : {done_n}/{len(order)} "
                    f"— {len(fiches)} pièce(s) pertinente(s)")
            parts, refs = [], []
            for f in fiches:
                parts.append(f"=== {f['title']} — node_{f['nid']} ===\n{f['text']}")
                refs.append(f"{f['doc_id']}::{f['nid']}")
            source_text = "\n\n".join(parts)
            context_label = ("【Synthèses ciblées des pièces (orientées par la "
                             "question, pages d'origine conservées)】\n")
        else:
            parts, refs, used = [], [], 0
            for doc_id, title, head_id, nid, text in selected:
                if used + len(text) > self.SIMPLE_CONTEXT_BUDGET and parts:
                    break
                block = (f"=== {title} — Section node_{nid} ===\n"
                         + text[: self.SIMPLE_CONTEXT_BUDGET - used])
                parts.append(block)
                used += len(block)
                refs.append(f"{doc_id}::{nid}")
            source_text = "\n\n".join(parts)
            context_label = "【Texte intégral des pièces retenues】\n"

        logger.info(
            f"voie corpus ({'map-reduce' if use_map_reduce else 'lecture directe'}): "
            f"{len(picked)} pièce(s), {len(refs)} nœud(s), {len(source_text)} car.")

        if refs:
            yield f"\n[NODES]{json.dumps(refs)}\n"

        # ---- 5. Contexte de rédaction : source + inventaire complet en appui ----
        inventory = self._build_corpus_inventory(tool_context)
        context = ""
        if source_text:
            context += context_label + source_text + "\n\n"
        if inventory:
            context += inventory

        # ---- 6. Rédaction ----
        yield "[ANSWERING]\n"
        history_context = self._build_history_context(session_id, use_memory)
        full_answer = ""
        image_paths = self._collect_images_for_refs(refs, tool_context) if is_vision else []
        if is_vision and image_paths:
            vision_prompt = self._build_vision_answer_prompt(
                query, [query], history_context, "aggregate",
                gathered_context=context, grounding=GROUNDING_INSTRUCTION_KB,
                mode="kb", docs_overview=context_overview,
            )
            async for chunk in self.pageindex.call_vlm_stream(vision_prompt, image_paths, model_type):
                full_answer += chunk
                yield chunk
        else:
            answer_prompt = self._build_answer_prompt(
                query, [query], context, history_context, "aggregate",
                grounding=GROUNDING_INSTRUCTION_KB, mode="kb",
                docs_overview=context_overview,
                allowed_citations=self._build_allowed_citations(refs, tool_context),
                user_consignes=self._build_user_consignes(refs, tool_context),
            )
            async for chunk in self.pageindex.call_llm_stream(answer_prompt, model_type):
                full_answer += chunk
                yield chunk
        yield "[ANSWER_DONE]\n"

        # En sous-question (décomposition), run_session gère la persistance et
        # l'évaluation sur la réponse assemblée — la voie ne le fait pas ici.
        if not persist:
            return

        self.sessions.add_message(session_id, Message(role="user", content=query))
        self.sessions.add_message(session_id, Message(
            role="assistant", content=full_answer, nodes=refs,
            thinking=(f"Sélection corpus [tree_search]: {thinking}" if thinking else ""),
            quality=self._predetect(query, full_answer, refs, tool_context, context=context, partial_context=use_map_reduce),
        ))

        # Vérification : À LA DEMANDE uniquement (bouton « Vérifier », curseur de
        # profondeur) — aucune vérification LLM automatique ici. Voir
        # POST /sessions/<id>/messages/<i>/verify. Badge déterministe conservé ci-dessus.

    @staticmethod
    def _question_presupposes(query: str) -> bool:
        """Heuristique (sans LLM) : la question demande-t-elle d'identifier une
        ENTITÉ / un RÔLE défini(e) qui pourrait ne pas exister (présupposé) ?
        Sert à NE PAS sauter la vérification sur une réponse « saine » : une
        confabulation de présupposé paraît saine (longue + citée). Conservateur."""
        q = (query or "").lower()
        if re.search(r"\bqui\s+(est|sont|était|étaient|serait|seraient)\b", q):
            return True
        return bool(re.search(
            r"\b(le|la|l['’]|les|du|de la|son|sa|leur)\s+"
            r"(mineur|majeur|victime|m[ée]decin|suspect|mis\s+en\s+cause|auteur|"
            r"t[ée]moin|pr[ée]venu|accus[ée]|plaignant|requ[ée]rant|d[ée]funt|"
            r"signataire|destinataire|condamn[ée]|coupable)\b", q))

    @staticmethod
    def _verbatim_issues(answer: str, context: str) -> list:
        """Vérificateur VERBATIM DÉTERMINISTE : toute phrase entre guillemets de la
        réponse doit apparaître mot pour mot dans les sources (tolérance espaces).
        Renvoie la liste des citations entre guillemets INTROUVABLES dans le contexte."""
        norm = lambda s: re.sub(r"\s+", " ", (s or "")).strip().lower()
        ctx = norm(context)
        issues = []
        for m in re.findall(r"[«\"“]([^«»\"”]{12,200})[»\"”]", answer or ""):
            n = norm(m)
            if n and n not in ctx:
                issues.append(m.strip()[:90])
        return issues

    @staticmethod
    def _is_global_summary(query: str) -> bool:
        """Détecte une demande de SYNTHÈSE GLOBALE (vue d'ensemble) — par
        mots-clés, sans appel LLM (la latence compte). Exclut les demandes
        explicites de détail par pièce (mode 'résumé par pièce', à part)."""
        q = (query or "").lower()
        # Demande explicite de détail par pièce → ce n'est PAS une synthèse globale.
        if re.search(r"(chaque (pi[eè]ce|document|rapport)|pi[eè]ce par pi[eè]ce|"
                     r"document par document|une fiche par|d[ée]taill[ée])", q):
            return False
        # Marqueurs intrinsèquement globaux.
        if re.search(r"(vue d.ensemble|fais le point|de quoi (s.agit|parle|traite))", q):
            return True
        # Verbe de synthèse ET référence à l'ENSEMBLE (sinon « résumé des faits
        # reprochés » serait pris à tort pour une synthèse de tout le dossier).
        verbe = re.search(r"(synth[èe]se|synth[ée]tis|r[ée]sum\w*|pr[ée]sent\w*)", q)
        ensemble = re.search(r"(dossier|document|affaire|proc[ée]dure|"
                             r"tout(es)? les pi[èe]ces|l.ensemble|globale?)", q)
        return bool(verbe and ensemble)

    def _build_summary_entries(self, tool_context: dict):
        """Entrées pour une synthèse globale : (label, ref 'doc::nid', summary,
        start_page). Mono-document → une entrée par NŒUD (section) ;
        multi-documents → une entrée par PIÈCE (nœud racine)."""
        entries = []
        for pc in self._extract_pieces(tool_context):
            nm = (tool_context.get("docs") or {}).get(pc["doc_id"], {}).get("node_map") or {}
            info = nm.get(pc["head_id"]) or {}
            node = info.get("node", info)
            summary = (node.get("summary") or "").strip() if isinstance(node, dict) else ""
            entries.append((pc["title"], f"{pc['doc_id']}::{pc['head_id']}",
                            summary, info.get("start_index") or 1))
        return entries

    async def _run_global_summary(self, session_id, query, model_type, use_memory,
                                  tool_context, context_overview, persist=True):
        """Synthèse GLOBALE transversale : rédaction sur les fiches/résumés de
        TOUTES les pièces (ou sections), sans tree_search ni lecture détaillée.
        Citations au niveau pièce (nœud racine + page de début). Un seul appel
        LLM → plus rapide, et c'est le rôle même des fiches identitaires."""
        is_vision = model_type != "text"
        entries = self._build_summary_entries(tool_context)
        if not entries:
            # Repli : pas de fiches → on retombe sur le flux normal.
            async for chunk in self._run_corpus_simple(
                    session_id, query, model_type, use_memory, tool_context, context_overview):
                yield chunk
            return

        is_kb = not (tool_context.get("primary_doc_id"))
        per = max(300, self.CORPUS_INVENTORY_BUDGET // max(1, len(entries)))
        lines, refs = [], []
        for label, ref, summary, page in entries:
            _, _, nid = ref.partition("::")
            s = (summary[:per] + "…") if len(summary) > per else summary
            lines.append(f"📄 {label} (node_{nid}, page {page})\n{s or '(pas de fiche)'}")
            refs.append(ref)
        inventory = ("【Fiches de toutes les pièces — base de la synthèse. "
                     "Cite la pièce concernée via le node_ et la page de sa ligne 📄.】\n"
                     + "\n\n".join(lines))

        yield "[SEARCHING]\n"
        yield self._step_marker(
            0, 0, "Synthèse globale : agrégation des fiches de toutes les pièces.",
            "global_summary", {}, f"{len(entries)} pièce(s)/section(s) agrégée(s)")
        if refs:
            yield f"\n[NODES]{json.dumps(refs)}\n"

        grounding = GROUNDING_INSTRUCTION_SUMMARY  # assoupli : pas de citation par phrase
        yield "[ANSWERING]\n"
        history_context = self._build_history_context(session_id, use_memory)
        answer_prompt = self._build_answer_prompt(
            query, [query], inventory, history_context, "aggregate",
            grounding=grounding, mode=("kb" if is_kb else "single"),
            docs_overview=context_overview, summary_mode=True,
            user_consignes=self._build_user_consignes(refs, tool_context))
        full_answer = ""
        async for chunk in self.pageindex.call_llm_stream(answer_prompt, model_type):
            full_answer += chunk
            yield chunk
        yield "[ANSWER_DONE]\n"

        # En sous-question (décomposition), run_session gère la persistance et
        # l'évaluation sur la réponse assemblée — la voie ne le fait pas ici.
        if not persist:
            return

        self.sessions.add_message(session_id, Message(role="user", content=query))
        self.sessions.add_message(session_id, Message(
            role="assistant", content=full_answer, nodes=refs,
            thinking="Synthèse globale (agrégation des fiches de toutes les pièces)",
            quality=self._predetect(query, full_answer, refs, tool_context)))
        # Vérification : à la demande uniquement (voir /verify) — pas d'auto-évaluation.

    async def _run_free_chat(self, session_id, query, model_type, use_memory):
        """Conversation libre (Q-R sans document sélectionné) : le modèle NU.

        Principe de recette (utilisateur) : l'application ne doit pas dégrader
        le modèle. Aucune instruction système, aucun style imposé — la
        question part telle quelle, l'historique comme vrais tours de
        dialogue, exactement comme dans un chat direct avec le modèle."""
        yield "[ANSWERING]\n"
        messages = []
        if use_memory:
            for m in self.sessions.get_messages(session_id)[-10:]:
                if m.superseded or not (m.content or "").strip():
                    continue
                messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": query})
        full_answer = ""
        async for chunk in self.pageindex.call_llm_stream(None, model_type, messages=messages):
            full_answer += chunk
            yield chunk
        yield "[ANSWER_DONE]\n"
        self.sessions.add_message(session_id, Message(role="user", content=query))
        self.sessions.add_message(session_id, Message(role="assistant", content=full_answer))

    async def decompose_query(self, query, context_overview="", model_type="text"):
        """Décomposition + AIGUILLAGE (1 appel LLM). Découpe la question en
        sous-questions SEULEMENT si elle regroupe plusieurs demandes distinctes,
        ET classe l'intention de CHAQUE (sous-)question :
        - "overview" : synthèse / vue d'ensemble → réponse sur les fiches ;
        - "detail"   : fait précis ou comparaison de versions → exige le TEXTE
          des pièces (sélection par tree_search puis LECTURE du contenu).
        Retourne {needs_decomposition, items:[{question, intent}]}. L'intention
        prime sur l'heuristique `_is_global_summary` ; repli (échec LLM) :
        intent=None → l'heuristique reprend la main."""
        prompt = render_prompt("decompose",
                               context_overview=context_overview[:1200], query=query)
        try:
            raw = await self.pageindex.call_llm(prompt, model_type)
            data = json.loads(self._extract_json_str(raw))
            items = []
            for it in (data.get("items") or []):
                q = (it.get("question") or "").strip()
                if not q:
                    continue
                intent = it.get("intent")
                items.append({"question": q,
                              "intent": intent if intent in ("overview", "detail") else None,
                              "instructions": (it.get("instructions") or "").strip() or None})
            if not items:
                items = [{"question": query, "intent": None, "instructions": None}]
            need = bool(data.get("needs_decomposition")) and len(items) > 1
            if not need:
                items = items[:1]
            return {"needs_decomposition": need, "items": items}
        except Exception as e:
            logger.warning(f"decompose_query: repli sans décomposition ({e})")
            return {"needs_decomposition": False,
                    "items": [{"question": query, "intent": None, "instructions": None}]}

    async def _relay_subquery(self, gen, text_sink: list, refs_sink: list):
        """Consomme une voie exécutée en sous-question : relaie au frontend le
        texte et les marqueurs utiles (nœuds, étapes), MAIS masque les marqueurs
        de cycle ([SEARCHING]/[ANSWERING]/[ANSWER_DONE]/[REFLECTING]) pour que la
        réponse décomposée reste UN seul cycle. Accumule texte + refs."""
        in_answer = False
        async for chunk in gen:
            s = chunk.strip()
            if s.startswith('[ANSWERING]'):
                in_answer = True
                continue
            if s.startswith('[ANSWER_DONE]'):
                in_answer = False
                continue
            if (s.startswith('[SEARCHING]') or s.startswith('[REFLECTING]')
                    or s.startswith('[AGENT_REFLECT]')):
                continue
            if s.startswith('[NODES]'):
                try:
                    refs_sink.extend(json.loads(s[len('[NODES]'):].strip()))
                except Exception:
                    pass
                yield chunk
                continue
            if s.startswith('[AGENT_STEP]'):
                yield chunk
                continue
            if in_answer:
                text_sink.append(chunk)
            yield chunk

    async def _run_decomposed(self, session_id, query, items, model_type, use_memory,
                              tool_context, context_overview, effective_single):
        """Question composite : chaque sous-question est routée vers la voie
        adaptée selon son INTENTION (overview → fiches ; detail → lecture du
        texte), et les réponses sont assemblées en sections sous UN seul cycle."""
        yield "[SEARCHING]\n"
        yield "[ANSWERING]\n"
        sections, all_refs = [], []
        for i, it in enumerate(items):
            sq = it["question"]
            intent = it.get("intent")
            instructions = it.get("instructions")
            header = ("\n\n" if i else "") + f"## {sq}\n\n"
            yield header
            text_sink = []
            if effective_single:
                gen = self._run_single_simple(session_id, sq, model_type, use_memory,
                                              tool_context, context_overview,
                                              persist=False, intent=intent)
            else:
                gen = self._run_corpus_simple(session_id, sq, model_type, use_memory,
                                              tool_context, context_overview,
                                              persist=False, intent=intent,
                                              instructions=instructions)
            async for chunk in self._relay_subquery(gen, text_sink, all_refs):
                yield chunk
            sections.append(header + "".join(text_sink))
        yield "[ANSWER_DONE]\n"
        full = "".join(sections)
        self.sessions.add_message(session_id, Message(role="user", content=query))
        self.sessions.add_message(session_id, Message(
            role="assistant", content=full, nodes=all_refs,
            thinking="Décomposition en sous-questions",
            quality=self._predetect(query, full, all_refs, tool_context, partial_context=True)))

        # Vérification : à la demande uniquement (voir /verify) — pas de garde-fou
        # automatique sur la réponse assemblée.

    async def run_session(self, session_id: str, query: str,
                          model_type: str = "text",
                          use_memory: bool = True) -> AsyncGenerator[str, None]:
        session = self.sessions.get_session(session_id)
        if not session:
            yield "[Error: Session not found]"
            return

        mode = session.mode
        doc_ids = list(session.doc_ids or [])

        # Mode kb SANS document : conversation libre — dialogue direct avec le
        # modèle de rédaction, sans outils ni citations (donc sans badge de
        # qualité, réservé aux réponses fondées sur des documents).
        if mode == "kb" and not doc_ids:
            async for chunk in self._run_free_chat(session_id, query, model_type, use_memory):
                yield chunk
            return
        if not doc_ids:
            yield "[Error: Document not set]"
            return

        # Verify all docs exist & are ready.
        ready_ids = []
        for did in doc_ids:
            doc = self.store.get_document(did)
            if doc and doc.status == "ready":
                ready_ids.append(did)
            else:
                logger.warning(f"Skipping non-ready doc {did} in session {session_id}")
        if not ready_ids:
            yield "[Error: Aucun des documents sélectionnés n'est prêt]"
            return

        # L'unité de routage est la PIÈCE : 1 pièce → voie simple ; ≥2 → voie
        # corpus. Un fichier composite (plusieurs pièces) bascule donc en voie
        # corpus, exactement comme un répertoire de fichiers.
        tool_context = self._build_tool_context(mode, ready_ids, None, model_type)

        if not tool_context["docs"]:
            yield "[Error: Échec du chargement des documents]"
            return

        if self.USE_PIECE_UNIT:
            effective_single = len(self._extract_pieces(tool_context)) <= 1
        else:
            effective_single = (mode == "single") or (len(ready_ids) == 1)
        if effective_single:
            tool_context["primary_doc_id"] = ready_ids[0]

        context_overview = self._build_docs_overview(tool_context)
        # In single mode we can afford to inline the TOC too for richer planning.
        if effective_single:
            tree_str = self._single_doc_tree_summary(tool_context)
            if tree_str:
                context_overview = context_overview + "\n\nPrimary document TOC (text elided):\n" + tree_str[:6000]

        # ---- Décomposition + aiguillage : un appel LLM décide si la question
        # regroupe plusieurs demandes distinctes ET classe l'intention de chaque
        # (sous-)question (overview → fiches ; detail → lecture du texte). Si
        # composite, chaque sous-question part sur la voie de son intention et
        # les réponses sont assemblées en sections. ----
        decomp = await self.decompose_query(query, context_overview, model_type)
        items = decomp.get("items") or [{"question": query, "intent": None}]
        if decomp.get("needs_decomposition"):
            async for chunk in self._run_decomposed(
                    session_id, query, items, model_type,
                    use_memory, tool_context, context_overview, effective_single):
                yield chunk
            return

        # Question unique : l'intention classée prime sur l'heuristique
        # _is_global_summary (transmise à la voie, repli si intent absent).
        intent = items[0].get("intent")
        instructions = items[0].get("instructions")

        # ---- Voie simple (mono-document) : pipeline canonique du cookbook
        # PageIndex (tree_search une fois → lecture des nœuds → rédaction).
        # La voie corpus prend le relais en mode kb multi-pièces.
        if effective_single:
            async for chunk in self._run_single_simple(
                session_id, query, model_type, use_memory,
                tool_context, context_overview, intent=intent,
            ):
                yield chunk
            return

        # ---- Voie corpus (kb multi-pièces) : le dossier est un arbre PageIndex.
        # UN tree_search sur les fiches de toutes les pièces, lecture intégrale
        # des pièces retenues, rédaction avec l'inventaire complet en appui.
        async for chunk in self._run_corpus_simple(
            session_id, query, model_type, use_memory,
            tool_context, context_overview, intent=intent,
            instructions=instructions,
        ):
            yield chunk
        return

    # ============================================================ #
    #  Helpers
    # ============================================================ #
    def _step_marker(self, sq_idx, step, thought, tool, tool_input, observation):
        data = {
            "sub_question_idx": sq_idx,
            "step": step + 1,
            "thought": thought,
            "tool": tool,
            "tool_input": tool_input,
            "observation": (observation or "")[:500],
        }
        return f"[AGENT_STEP]{json.dumps(data, ensure_ascii=False)}\n"

    def _collect_images_for_refs(self, refs: list, tool_context: dict) -> list:
        """Given qualified refs (doc::nid), gather corresponding page image paths."""
        docs = tool_context.get("docs") or {}
        paths = []
        seen = set()
        for ref in refs:
            if "::" in ref:
                did, nid = ref.split("::", 1)
            else:
                did = tool_context.get("primary_doc_id")
                nid = ref
            dctx = docs.get(did)
            if not dctx:
                continue
            node_map = dctx.get("node_map") or {}
            page_images = dctx.get("page_images") or {}
            info = node_map.get(nid)
            if not info:
                continue
            s = info.get("start_index") or 1
            e = info.get("end_index") or s
            for p in range(s, e + 1):
                key = (did, p)
                if key not in seen and p in page_images:
                    paths.append(page_images[p])
                    seen.add(key)
        return paths

    def _build_history_context(self, session_id: str, use_memory: bool) -> str:
        if not use_memory:
            return ""
        history = self.sessions.get_messages(session_id)
        if not history:
            return ""
        # Skip messages flagged as superseded (e.g. low-score drafts that
        # were replaced by a reflection-triggered retry). They remain in the
        # UI for transparency but must NOT leak back into LLM context,
        # otherwise the model may keep seeing/repeating stale content.
        history = [m for m in history if not getattr(m, 'superseded', False)]
        if not history:
            return ""
        ctx = "\nPrevious conversation:\n"
        # Exclude the most recent user turn since that's the current question.
        recent = history[-10:]
        for msg in recent:
            ctx += f"{msg.role}: {msg.content[:200]}\n"
        return ctx

    def _build_vision_answer_prompt(self, query, sub_questions,
                                    history_context, strategy,
                                    gathered_context: str = "",
                                    grounding: str = GROUNDING_INSTRUCTION_SINGLE,
                                    mode: str = "single",
                                    docs_overview: str = ""):
        sub_q_note = ""
        if len(sub_questions) > 1:
            sub_q_note = (
                f"\nThe question was decomposed into sub-questions: "
                f"{json.dumps(sub_questions, ensure_ascii=False)}\n"
                f"Synthesis strategy: {strategy}\n"
            )

        docs_section = ""
        if docs_overview:
            docs_section = (
                f"\n【Available documents — metadata you already know】\n"
                f"{docs_overview[:24000]}\n"
            )

        context_section = ""
        if gathered_context:
            context_section = (
                f"\nAnalysis results from the reasoning process "
                f"(IMPORTANT — use these findings as primary reference):\n"
                f"{gathered_context[:24000]}\n"
            )

        skill_section = skill_manager.build_skill_prompt()
        skill_note = (
            "\n\nFollow the output format and workflow of any matching custom skill below:\n"
            + skill_section
            if skill_section else ""
        )

        mode_note = (
            "\nYou are answering based on MULTIPLE documents. "
            "Be explicit about which document each claim comes from.\n"
            if mode == "kb" else ""
        )

        return f"""Answer the question based on the images AND the analysis context below.
The analysis context contains findings from previous reasoning steps — treat it as authoritative.
The investigation phase is OVER and no tools are available anymore: do NOT output tool calls,
JSON actions, plans or "next steps" — write the final prose answer for the user, now.
{mode_note}
Question: {query}
{sub_q_note}
{docs_section}
{context_section}
{history_context}
{skill_note}

{LANG_INSTRUCTION}

{grounding}

{STYLE_INSTRUCTION}

Provide a clear, comprehensive answer in French."""

    def _build_allowed_citations(self, refs: list, tool_context: dict) -> str:
        """Liste EXPLICITE des (doc, node) présents dans le contexte : SEULS ces
        node ids sont citables. Injectée au rédacteur pour verrouiller les
        citations — pas d'id inventé, pas de placeholder « source »."""
        docs = (tool_context or {}).get("docs") or {}
        seen, lines = set(), []
        for ref in refs or []:
            did, nid = (ref.split("::", 1) if "::" in ref
                        else (tool_context.get("primary_doc_id"), ref))
            if (did, nid) in seen:
                continue
            seen.add((did, nid))
            fn = (docs.get(did) or {}).get("filename") or did
            lines.append(f"- node_{nid} (doc: {fn})")
        if not lines:
            return ""
        return (
            "\n【Citations autorisées — n'en cite AUCUNE autre】\n"
            "Tu ne peux citer QUE les sources ci-dessous, en reprenant le node id "
            "EXACTEMENT (verbatim) ; n'invente jamais un node id, ne modifie pas son "
            "numéro, n'utilise jamais un placeholder. Si un fait n'est couvert par "
            "aucune de ces sources, dis-le plutôt que de fabriquer une référence.\n"
            + "\n".join(lines) + "\n"
        )

    def _build_answer_prompt(self, query, sub_questions, context,
                             history_context, strategy,
                             grounding: str = GROUNDING_INSTRUCTION_SINGLE,
                             mode: str = "single",
                             docs_overview: str = "",
                             summary_mode: bool = False,
                             allowed_citations: str = "",
                             user_consignes: str = ""):
        sub_q_note = ""
        if len(sub_questions) > 1:
            sub_q_note = (
                f"\nThe question was decomposed into sub-questions: "
                f"{json.dumps(sub_questions, ensure_ascii=False)}\n"
                f"Synthesis strategy: {strategy}\n"
            )

        docs_section = ""
        if docs_overview:
            docs_section = (
                f"\n【Available documents — metadata you already know】\n"
                f"{docs_overview[:24000]}\n"
            )

        skill_section = skill_manager.build_skill_prompt()
        skill_note = (
            "\n\nFollow the output format and workflow of any matching custom skill below:\n"
            + skill_section
            if skill_section else ""
        )

        mode_note = (
            "\nYou are answering based on MULTIPLE documents. "
            "Be explicit about which document each claim comes from in every citation.\n"
            if mode == "kb" else ""
        )

        return f"""Answer the question based on the context below.
The context contains your prior reasoning trace, tool analysis results (processed by AI) and raw source text grouped per document.
The investigation phase is OVER and no tools are available anymore: do NOT output tool calls,
JSON actions, plans or "next steps" — write the final prose answer for the user, now,
from the context you have.
{mode_note}
Question: {query}
{sub_q_note}
{docs_section}
Context:
{context[:60000]}
{history_context}
{user_consignes}
{skill_note}

{LANG_INSTRUCTION}

{grounding}
{allowed_citations}
{STYLE_INSTRUCTION}

{GLOBAL_SUMMARY_INSTRUCTION if summary_mode else ""}

Provide a clear, comprehensive answer in French.
If sub-questions were used, synthesize a unified answer."""

    @staticmethod
    def _extract_json_str(text: str) -> str:
        text = text.strip()
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.rfind("```")
            if end > start:
                return text[start:end].strip()
        if "```" in text:
            start = text.find("```") + 3
            end = text.rfind("```")
            if end > start:
                return text[start:end].strip()
        brace_start = text.find("{")
        if brace_start >= 0:
            depth = 0
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return text[brace_start:i+1]
        return text
