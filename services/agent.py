"""
Document Agent - ReAct loop, query decomposition, self-reflection, proactive analysis.

Session-based execution supporting two modes:
  * single  : one document, backwards compatible with the old UX.
  * kb      : multiple documents chosen by the user; progressive disclosure —
              the system prompt only exposes metadata, the agent must call
              list_documents / read_document_toc / tree_search to drill in.
"""

import json
import logging
import os
import re
from typing import AsyncGenerator, List, Optional

from models.document import DocumentStore
from models.session import Message, SessionStore, session_store
from services.skill_manager import skill_manager

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
GROUNDING_INSTRUCTION_SUMMARY = (
    "Grounding rules for a GLOBAL SUMMARY (MUST follow):\n"
    "1. Base the synthesis ONLY on the provided fiches; never invent facts; if a "
    "point isn't covered, say so.\n"
    "2. Support the synthesis with citations, but do NOT cite one per sentence: cite "
    "per THEME and GROUP several pieces in a single citation when they share a point "
    "(e.g. `(doc: a.pdf, node_0000, page 1 ; doc: b.pdf, node_0000, page 1)`). For a "
    "single document use `(node_<id>, page N)`. Do NOT produce one citation per piece, "
    "nor a catalogue of pieces.\n"
    "3. Use plain ASCII parentheses and the REAL node ids; never 【】 nor a "
    "placeholder like `source`.\n"
)

# System-wide grounding rules. The multi-doc clause is appended dynamically when mode=='kb'.
GROUNDING_INSTRUCTION_SINGLE = (
    "Grounding rules (MUST follow):\n"
    "1. Ground every concrete claim in the Context. Cite the source inline as "
    "`(node_<id>, page N)`, always using the REAL node id verbatim (e.g. `(node_0007, page 3)`) "
    "so it can be linked. Use plain ASCII parentheses `( )` — NEVER `【】` or other brackets — "
    "and never a placeholder like `source` in place of the node id. "
    "Preserve original numbers and units verbatim.\n"
    "2. Node text in the Context is wrapped in `<page_N>…</page_N>` markers: take the page "
    "number of each claim from its enclosing marker — NEVER guess a page. Cite the specific "
    "page for EACH claim or paragraph (not just once per section), and never echo the "
    "`<page_N>` markers themselves in your answer.\n"
    "3. If the Context does not cover the question, say so explicitly "
    "(e.g. `Non mentionné dans le document...`). Never fabricate facts, citations, or fill gaps from prior knowledge.\n"
    "4. Never attribute a role (author, signatory, recipient, doctor, police officer, magistrate...) "
    "to a person unless the Context states it explicitly. Do NOT infer or invert a relationship "
    "(author vs recipient, doctor vs investigator, parent vs child), even when two people share a name. "
    "If a role is not stated, write `non précisé` rather than guessing."
)

GROUNDING_INSTRUCTION_KB = (
    "Grounding rules (MUST follow):\n"
    "1. Ground every concrete claim in the Context. Cite the source inline as "
    "`(doc: <filename>, node_<id>, page N)`, always using the REAL node id verbatim "
    "(e.g. `(doc: rapport.pdf, node_0007, page 3)`) so the reader knows WHICH document each claim "
    "came from and the citation can be linked. Use plain ASCII parentheses `( )` — NEVER `【】` or "
    "other brackets — and never a placeholder like `source` in place of the node id. "
    "Preserve original numbers and units verbatim.\n"
    "2. Node text in the Context is wrapped in `<page_N>…</page_N>` markers: take the page "
    "number of each claim from its enclosing marker — NEVER guess a page. Cite the specific "
    "page for EACH claim or paragraph (not just once per section), and never echo the "
    "`<page_N>` markers themselves in your answer.\n"
    "3. If the Context does not cover the question, say so explicitly "
    "(e.g. `Non mentionné dans les documents sélectionnés...`). Never fabricate facts, citations, or fill gaps from prior knowledge.\n"
    "4. When comparing across documents, make the document identity unambiguous in every bullet "
    "(e.g. `Le document A utilise X, le document B utilise Y`).\n"
    "5. Never attribute a role (author, signatory, recipient, doctor, police officer, magistrate...) "
    "to a person unless the Context states it explicitly. Do NOT infer or invert a relationship "
    "(author vs recipient, doctor vs investigator, parent vs child), even when two people share a name. "
    "If a role is not stated, write `non précisé` rather than guessing."
)


class DocumentAgent:
    """Session-based agentic document Q&A."""

    def __init__(self, pageindex_service, store: DocumentStore,
                 sessions: SessionStore = session_store):
        self.pageindex = pageindex_service
        self.store = store
        self.sessions = sessions

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
            checks.append("syntaxe technique dans la réponse")

        if not cites:
            score -= 4
            checks.append("aucune citation")
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
                    checks.append(f"{sans_doc} citation(s) sans document (ambiguës en multi-pièces)")
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
                checks.append(f"{bad_node} citation(s) hors des sources lues")
            if bad_page:
                score -= 2
                checks.append(f"{bad_page} renvoi(s) de page hors plage du nœud")
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
            checks.append(f"{broken} citation(s) mal formée(s) (placeholder « source » ou 【】)")
        return {"score": max(0, min(10, score)), "checks": checks}

    @staticmethod
    # ============================================================ #
    #  Direction 4: Self-reflection
    # ============================================================ #
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
    SIMPLE_CONTEXT_BUDGET = 60000   # caractères de texte source pour le rédacteur
    SIMPLE_MAX_NODES = 10

    # ---- Voie corpus (le dossier EST un arbre PageIndex) ----
    # Un seul tree_search sur les fiches de toutes les pièces.
    CORPUS_SELECT_BUDGET = 48000    # budget total des fiches dans l'arbre de sélection
    CORPUS_INVENTORY_BUDGET = 45000  # budget total de l'inventaire joint au rédacteur
    CORPUS_MAX_PIECES_READ = 12     # pièces lues en intégral (le reste : citable via l'inventaire)
    CORPUS_PIECE_DRILL_THRESHOLD = 20000  # au-delà, une pièce composite est sélectionnée
    #   section par section (tree_search interne) au lieu d'être lue en entier (hiérarchie niv. 2)

    def _build_simple_answer_prompt(self, query, context, history_context, grounding):
        return f"""Answer the question based on the context below — the selected sections of the
document. Their text is wrapped in <page_N>…</page_N> markers.

Question: {query}

Context:
{context}
{history_context}

{LANG_INSTRUCTION}

{grounding}

{STYLE_INSTRUCTION}

Provide a clear, comprehensive answer in French."""

    async def _run_single_simple(self, session_id, query, model_type,
                                 use_memory, tool_context, context_overview):
        """UNE recherche par raisonnement sur l'arbre → lecture des nœuds
        retenus → rédaction. Pas de décomposition, pas de boucle ReAct.
        L'auto-évaluation reste comme garde-fou, avec au plus UNE expansion
        bornée (tree_search complémentaire sur les manques signalés)."""
        # Demande de synthèse globale → vue d'ensemble transversale sur les
        # résumés de toutes les sections (pas de sélection top-k).
        if self._is_global_summary(query):
            async for chunk in self._run_global_summary(
                    session_id, query, model_type, use_memory, tool_context, context_overview):
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
            query, context, history_context, GROUNDING_INSTRUCTION_SINGLE)

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

        self.sessions.add_message(session_id, Message(role="user", content=query))
        self.sessions.add_message(session_id, Message(
            role="assistant", content=full_answer, nodes=refs,
            thinking=(f"Step 1 [tree_search]: {thinking}" if thinking else ""),
            quality=self._estimate_quality(full_answer, refs, tool_context),
        ))

        # ---- 4. Auto-évaluation CONDITIONNELLE ----
        # La réflexion est un garde-fou, pas un péage : une réponse saine
        # (substantielle, citée, sans fuite de syntaxe d'outil) rend la main
        # immédiatement. Elle ne tourne que sur signe de faiblesse.
        healthy = (
            len(full_answer) > 400
            and len(re.findall(r'\(\s*(?:doc:[^,]+,\s*)?node[_\s]*\w+\s*,\s*pages?', full_answer)) >= 2
            and '"thought"' not in full_answer
        )
        if not node_list or healthy:
            logger.info(f"voie simple: auto-évaluation sautée (réponse saine={healthy})")
            return
        yield "[REFLECTING]\n"
        reflection = await self.reflect(
            query, full_answer, context, model_type, is_vision,
            docs_overview=context_overview,
        )
        yield f"\n[AGENT_REFLECT]{json.dumps(reflection, ensure_ascii=False)}\n"
        self.sessions.update_last_message(session_id, "assistant", verification={
            "score": reflection.get("score"), "issues": reflection.get("issues") or [],
            "missing_info": reflection.get("missing_info") or [], "auto": True,
        })
        if not (reflection.get("action") == "retry"
                and reflection.get("score", 10) < REFLECT_ACCEPT_THRESHOLD):
            return

        # ---- 5. Une expansion bornée, puis réécriture (pas de boucle) ----
        yield "[AGENT_RETRY]\n"
        missing = "; ".join(reflection.get("missing_info") or []) or query
        extra, thinking2 = await _search(missing, set(node_list))
        if extra:
            yield self._step_marker(
                0, 1, thinking2, "tree_search", {"query": missing},
                f"[doc={doc_id}] {len(extra)} nœud(s) complémentaire(s) : {', '.join(extra)}",
            )
            node_list = node_list + extra
            context, _ = _assemble(node_list)
            refs = [f"{doc_id}::{n}" for n in node_list]
            yield f"\n[NODES]{json.dumps(refs)}\n"

        yield "[RETRY_ANSWERING]\n"
        issues = reflection.get("issues") or []
        issues_note = ""
        if issues:
            issues_note = ("\nA first draft was judged insufficient for these reasons — fix them:\n- "
                           + "\n- ".join(str(i) for i in issues) + "\n")
        retry_prompt = self._build_simple_answer_prompt(
            query, context, history_context + issues_note, GROUNDING_INSTRUCTION_SINGLE)
        full_answer = ""
        async for chunk in self.pageindex.call_llm_stream(retry_prompt, model_type):
            full_answer += chunk
            yield chunk
        yield "[ANSWER_DONE]\n"
        self.sessions.add_message(session_id, Message(
            role="assistant", content=full_answer, nodes=refs,
            thinking=(f"Step 1 [tree_search]: {thinking2}" if thinking2 else ""),
            quality=self._estimate_quality(full_answer, refs, tool_context),
        ))
        self.sessions.mark_superseded_before_last(session_id, role="assistant")

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

    def _piece_fiche(self, piece: dict, tool_context: dict, budget: int) -> str:
        """Fiche de sélection d'une pièce : résumé de son nœud de tête + titres
        de ses sous-sections (pour que le tree_search « voie » le contenu)."""
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
        return (fiche[:budget] + "…") if len(fiche) > budget else (fiche or "(pas de fiche)")

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

    async def _run_corpus_simple(self, session_id, query, model_type, use_memory,
                                 tool_context, context_overview):
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
        if self._is_global_summary(query):
            async for chunk in self._run_global_summary(
                    session_id, query, model_type, use_memory, tool_context, context_overview):
                yield chunk
            return

        # ---- 1. Arbre de sélection : une entrée par PIÈCE (alias court) ----
        pieces = self._extract_pieces(tool_context)
        per_fiche = max(300, self.CORPUS_SELECT_BUDGET // max(1, len(pieces)))
        children = []
        for i, pc in enumerate(pieces):
            children.append({"node_id": f"p{i}", "title": pc["title"],
                             "summary": self._piece_fiche(pc, tool_context, per_fiche)})
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
        thinking = (res.get("thinking") or "").strip()
        yield self._step_marker(
            0, 0, thinking, "tree_search", {"query": query},
            f"{len(picked)} pièce(s) retenue(s) : "
            + (", ".join(pc["title"] for pc in picked) or "—"),
        )

        # ---- 3. Lecture des pièces retenues. Hiérarchie niveau 2 : une pièce
        # COMPOSITE volumineuse est sélectionnée section par section (tree_search
        # interne) au lieu d'être lue en entier. Les refs portent le VRAI doc_id
        # de la pièce → citations `doc::node` exactes. ----
        parts, refs, used = [], [], 0
        for pc in picked:
            doc_id = pc["doc_id"]
            title = pc["title"]
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
                if not text:
                    continue
                if used + len(text) > self.SIMPLE_CONTEXT_BUDGET and parts:
                    break
                block = (f"=== {title} — Section node_{nid} ===\n"
                         + text[: self.SIMPLE_CONTEXT_BUDGET - used])
                parts.append(block)
                used += len(block)
                refs.append(f"{doc_id}::{nid}")
            if used >= self.SIMPLE_CONTEXT_BUDGET:
                break
        source_text = "\n\n".join(parts)
        logger.info(
            f"voie corpus: {len(picked)} pièce(s) retenue(s), "
            f"{len(refs)} nœud(s) lu(s), contexte={used} caractères"
        )

        if refs:
            yield f"\n[NODES]{json.dumps(refs)}\n"

        # ---- 4. Contexte de rédaction : texte lu + inventaire complet en appui ----
        inventory = self._build_corpus_inventory(tool_context)
        context = ""
        if source_text:
            context += "【Texte intégral des pièces retenues】\n" + source_text + "\n\n"
        if inventory:
            context += inventory

        # ---- 5. Rédaction ----
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
            )
            async for chunk in self.pageindex.call_llm_stream(answer_prompt, model_type):
                full_answer += chunk
                yield chunk
        yield "[ANSWER_DONE]\n"

        self.sessions.add_message(session_id, Message(role="user", content=query))
        self.sessions.add_message(session_id, Message(
            role="assistant", content=full_answer, nodes=refs,
            thinking=(f"Sélection corpus [tree_search]: {thinking}" if thinking else ""),
            quality=self._estimate_quality(full_answer, refs, tool_context),
        ))

        # ---- 6. Auto-évaluation conditionnelle (garde-fou) ----
        healthy = (
            len(full_answer) > 400
            and len(re.findall(r'\(\s*(?:doc:[^,]+,\s*)?node[_\s]*\w+\s*,\s*pages?', full_answer)) >= 2
            and '"thought"' not in full_answer
        )
        if not refs or healthy:
            logger.info(f"voie corpus: auto-évaluation sautée (réponse saine={healthy})")
            return
        yield "[REFLECTING]\n"
        reflection = await self.reflect(
            query, full_answer, context, model_type, is_vision,
            docs_overview=context_overview,
        )
        yield f"\n[AGENT_REFLECT]{json.dumps(reflection, ensure_ascii=False)}\n"
        self.sessions.update_last_message(session_id, "assistant", verification={
            "score": reflection.get("score"), "issues": reflection.get("issues") or [],
            "missing_info": reflection.get("missing_info") or [], "auto": True,
        })

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
                                  tool_context, context_overview):
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
            docs_overview=context_overview, summary_mode=True)
        full_answer = ""
        async for chunk in self.pageindex.call_llm_stream(answer_prompt, model_type):
            full_answer += chunk
            yield chunk
        yield "[ANSWER_DONE]\n"

        self.sessions.add_message(session_id, Message(role="user", content=query))
        self.sessions.add_message(session_id, Message(
            role="assistant", content=full_answer, nodes=refs,
            thinking="Synthèse globale (agrégation des fiches de toutes les pièces)",
            quality=self._estimate_quality(full_answer, refs, tool_context)))

        healthy = (
            len(full_answer) > 400
            and len(re.findall(r'\(\s*(?:doc:[^,]+,\s*)?node[_\s]*\w+\s*,\s*pages?', full_answer)) >= 2
            and '"thought"' not in full_answer
        )
        if not refs or healthy:
            logger.info(f"synthèse globale: auto-évaluation sautée (réponse saine={healthy})")
            return
        yield "[REFLECTING]\n"
        reflection = await self.reflect(
            query, full_answer, inventory, model_type, is_vision, docs_overview=context_overview)
        yield f"\n[AGENT_REFLECT]{json.dumps(reflection, ensure_ascii=False)}\n"
        self.sessions.update_last_message(session_id, "assistant", verification={
            "score": reflection.get("score"), "issues": reflection.get("issues") or [],
            "missing_info": reflection.get("missing_info") or [], "auto": True})

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

        # ---- Voie simple (mono-document) : pipeline canonique du cookbook
        # PageIndex (tree_search une fois → lecture des nœuds → rédaction),
        # sans décomposition ni boucle ReAct. La boucle d'agent reste le
        # chemin du mode kb (plusieurs documents).
        if effective_single:
            async for chunk in self._run_single_simple(
                session_id, query, model_type, use_memory,
                tool_context, context_overview,
            ):
                yield chunk
            return

        # ---- Voie corpus (kb multi-pièces) : le dossier est un arbre PageIndex.
        # UN tree_search sur les fiches de toutes les pièces, lecture intégrale
        # des pièces retenues, rédaction avec l'inventaire complet en appui.
        async for chunk in self._run_corpus_simple(
            session_id, query, model_type, use_memory,
            tool_context, context_overview,
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

    def _build_answer_prompt(self, query, sub_questions, context,
                             history_context, strategy,
                             grounding: str = GROUNDING_INSTRUCTION_SINGLE,
                             mode: str = "single",
                             docs_overview: str = "",
                             summary_mode: bool = False):
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
{skill_note}

{LANG_INSTRUCTION}

{grounding}

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
