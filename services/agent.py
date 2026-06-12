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
from services.tools.base import ToolRegistry
from services.tools.tree_search import TreeSearchTool
from services.tools.node_reader import NodeReaderTool
from services.tools.keyword_search import KeywordSearchTool
from services.tools.page_viewer import PageViewerTool
from services.tools.summarizer import SummarizerTool
from services.tools.list_documents import ListDocumentsTool
from services.tools.read_toc import ReadTocTool
from services.tools.cross_search import CrossSearchTool
from services.skill_manager import skill_manager

logger = logging.getLogger(__name__)

MAX_REACT_STEPS = 5
MAX_RETRY = 1
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
    "- These remain mandatory in all cases: inline citations `(node_<id>, page N)` and "
    "quotation marks around exact quotes.\n"
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
    "(e.g. `Non mentionné dans le document...`). Never fabricate facts, citations, or fill gaps from prior knowledge."
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
    "(e.g. `Le document A utilise X, le document B utilise Y`)."
)


class DocumentAgent:
    """Session-based agentic document Q&A."""

    def __init__(self, pageindex_service, store: DocumentStore,
                 sessions: SessionStore = session_store):
        self.pageindex = pageindex_service
        self.store = store
        self.sessions = sessions
        self.registry = ToolRegistry()
        self._register_tools()

    def _register_tools(self):
        # Périmètre volontairement restreint aux outils canoniques PageIndex
        # (cookbook + examples officiels) : le retrieval se fait par
        # raisonnement sur l'arbre, puis lecture des nœuds — rien d'autre.
        # keyword_search (recherche littérale) et summarize_nodes (résumé
        # intermédiaire) sont conservés dans le code mais NON enregistrés :
        # si l'arbre ne permet pas de trouver, c'est l'arbre qu'il faut
        # améliorer, pas le paradigme qu'il faut contourner.
        self.registry.register(TreeSearchTool(self.pageindex))
        self.registry.register(NodeReaderTool())
        # self.registry.register(KeywordSearchTool())          # hors paradigme
        self.registry.register(PageViewerTool(self.pageindex))
        # self.registry.register(SummarizerTool(self.pageindex))  # hors paradigme
        self.registry.register(ListDocumentsTool())
        self.registry.register(ReadTocTool())
        self.registry.register(CrossSearchTool(self.pageindex))

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

    # ============================================================ #
    #  Direction 3: Query decomposition
    # ============================================================ #
    async def decompose_query(self, query: str, context_overview: str,
                              mode: str, model_type: str = "text") -> dict:
        skill_section = skill_manager.build_skill_prompt()
        skill_hint = ""
        if skill_section:
            skill_hint = (
                "\n\nYou also have active custom skills. "
                "Consider them when decomposing:\n" + skill_section
            )

        mode_hint = (
            "Multi-document mode: the user may want to compare or aggregate across documents. "
            "A sub-question that asks about a single aspect across multiple docs (\"compare X in A and B\") "
            "counts as ONE sub-question, not one-per-document — the cross_search tool handles that."
            if mode == "kb" else
            "Single-document mode."
        )

        prompt = f"""You are an intelligent document analysis agent.
Analyze the user's question and decide whether it should be broken into simpler sub-questions.

Question: {query}

Context overview:
{context_overview[:24000]}

Mode: {mode_hint}

Rules:
- ONLY decompose if the question genuinely asks about MULTIPLE DIFFERENT topics/aspects that require searching DIFFERENT parts of the document(s).
- Do NOT decompose if the question is about a single topic, even if it seems complex.
- Do NOT decompose extraction tasks (e.g. "extract table X", "list the items in section Y").
- Do NOT decompose lookup tasks (e.g. "what is X?").
- Do NOT decompose if the answer is likely in one section/table/figure.
- When in doubt, do NOT decompose.
- Generate at most 3 sub-questions, only when truly needed.
- If a custom skill is relevant, design sub-questions to match its workflow.
{skill_hint}

{LANG_INSTRUCTION}

Output JSON only:
{{
    "needs_decomposition": true or false,
    "reasoning": "brève explication en français",
    "sub_questions": ["sous-question 1", "sous-question 2"],
    "synthesis_strategy": "compare" | "aggregate" | "sequence" | "direct"
}}"""
        try:
            raw = await self.pageindex.call_llm(prompt, 'text')
            raw = self._extract_json_str(raw)
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Decomposition failed, using original query: {e}")
            return {
                "needs_decomposition": False,
                "reasoning": "fallback",
                "sub_questions": [query],
                "synthesis_strategy": "direct",
            }

    # ============================================================ #
    #  Direction 1 & 2: ReAct step
    # ============================================================ #
    async def think_and_act(self, query: str, gathered: List[dict],
                            tool_context: dict, context_overview: str,
                            model_type: str = "text") -> dict:
        mode = tool_context.get("mode", "single")
        tool_specs = self.registry.all_specs()

        # Filter tools per-mode for clarity.
        if mode == "single":
            hidden = {"list_documents", "cross_search"}
            tool_specs = [t for t in tool_specs if t["name"] not in hidden]
        # kb mode: expose everything.

        tools_desc = "\n".join(
            f'{i+1}. {t["name"]}: {t["description"]}  '
            f'Params: {json.dumps(t["parameters"])}'
            for i, t in enumerate(tool_specs)
        )

        context_so_far = ""
        if gathered:
            trace_lines = []
            for i, g in enumerate(gathered, 1):
                thought = (g.get("thought") or "").strip()
                try:
                    input_str = json.dumps(g.get("input") or {}, ensure_ascii=False)
                except Exception:
                    input_str = str(g.get("input"))
                obs = g.get("observation") or ""
                trace_lines.append(
                    f"Thought {i}: {thought}\n"
                    f"Action  {i}: {g['tool']}({input_str})\n"
                    f"Observation {i}: {obs}"
                )
            context_so_far = (
                "Previous reasoning trace — these are actions YOU have already taken. "
                "Do NOT repeat an action with identical arguments; based on the latest "
                "Observation, advance to the next logical step (e.g. read_node / "
                "view_pages) or choose final_answer if you have enough.\n\n"
                + "\n\n".join(trace_lines)
            )

        skill_section = skill_manager.build_skill_prompt()

        mode_guide = ""
        if mode == "kb":
            mode_guide = (
                "\nKnowledge-base mode guidance:\n"
                "  1. Start with `list_documents` if you haven't seen the documents yet.\n"
                "  2. For documents that look relevant, call `read_document_toc(doc_id=...)` "
                "to see their structure before drilling in.\n"
                "  3. Use `cross_search` to find where a topic is covered across several docs, "
                "or `tree_search(query, doc_id=...)` to search a single doc.\n"
                "  4. Always pass `doc_id` to per-document tools (read_node, tree_search, view_pages).\n"
            )

        persistence_rule = """Based on the question and what you know so far, decide the next step.
If you already have enough information, choose "final_answer".
NEVER conclude that something is absent from the documents after a single empty
search: tree summaries may phrase things differently than the question. Before
answering "not found", you MUST retry `tree_search` with a reformulated query
(synonyms, the key proper nouns alone) and `read_node` the most plausible
sections to check their actual text."""

        common = f"""Question: {query}

Accessible documents overview:
{context_overview[:24000]}

{context_so_far}
{mode_guide}
{persistence_rule}
{skill_section}

{LANG_INSTRUCTION}"""

        # --- Voie nominale : function calling NATIF (aligné sur l'exemple
        # officiel PageIndex). Les modèles récents sont entraînés pour cela ;
        # c'est plus robuste que de parser du JSON écrit en texte.
        try:
            msg = await self.pageindex.call_llm_tools(
                f"You are an intelligent document analysis agent.\n\n{common}\n\n"
                f"Decide the next step and call EXACTLY ONE tool.",
                self._to_openai_tools(tool_specs), 'text',
            )
            if msg.get("tool_calls"):
                tc = msg["tool_calls"][0]
                name = (tc.get("name") or "").split('.')[-1]
                if name.startswith('tool_'):
                    name = name[5:]
                thought = (msg.get("reasoning") or msg.get("content") or "").strip()[:400]
                logger.info(f"think_and_act (natif): {name}({json.dumps(tc.get('arguments') or {}, ensure_ascii=False)[:120]})")
                return {"thought": thought,
                        "action": {"tool": name, "input": tc.get("arguments") or {}}}
            # Le modèle a répondu en texte malgré les outils : tenter le JSON.
            if (msg.get("content") or "").strip():
                return json.loads(self._extract_json_str(msg["content"]))
        except Exception as e:
            logger.warning(f"Think-and-act natif indisponible ({e}), repli JSON texte")

        # --- Repli : JSON dans le texte (serveurs sans support des outils) ---
        prompt = f"""You are an intelligent document analysis agent with access to these tools:

{tools_desc}

{len(tool_specs)+1}. final_answer: You have gathered enough information to answer. Params: {{}}

{common}

Output JSON only:
{{
    "thought": "décris ton raisonnement en français",
    "action": {{
        "tool": "tool_name",
        "input": {{ ... }}
    }}
}}"""
        try:
            raw = await self.pageindex.call_llm(prompt, 'text')
            raw = self._extract_json_str(raw)
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Think-and-act parse failed: {e}")
            # Sensible fallback: in single-doc mode tree_search; in kb mode list_documents.
            fallback_tool = "list_documents" if mode == "kb" else "tree_search"
            fallback_input = {} if mode == "kb" else {"query": query}
            return {
                "thought": "Falling back to a safe default tool",
                "action": {"tool": fallback_tool, "input": fallback_input},
            }

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
        return {"score": max(0, min(10, score)), "checks": checks}

    @staticmethod
    def _to_openai_tools(tool_specs: List[dict]) -> List[dict]:
        """Convertit les specs du registre au format `tools` de l'API
        (function calling natif), en ajoutant l'outil final_answer."""
        tools = []
        for t in tool_specs:
            props = {}
            for pname, p in (t.get("parameters") or {}).items():
                prop = {"type": p.get("type", "string"),
                        "description": p.get("description", "")}
                if prop["type"] == "array":
                    prop["items"] = {"type": "string"}
                props[pname] = prop
            tools.append({"type": "function", "function": {
                "name": t["name"],
                "description": (t.get("description") or "")[:1024],
                "parameters": {"type": "object", "properties": props},
            }})
        tools.append({"type": "function", "function": {
            "name": "final_answer",
            "description": "You have gathered enough information to answer the question.",
            "parameters": {"type": "object", "properties": {}},
        }})
        return tools

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

        # Une session Q-R réduite à UNE pièce se comporte comme le mode
        # mono-document : rien n'y justifie la boucle d'agent.
        effective_single = (mode == "single") or (len(ready_ids) == 1)
        primary = ready_ids[0] if effective_single else None
        tool_context = self._build_tool_context(mode, ready_ids, primary, model_type)

        if not tool_context["docs"]:
            yield "[Error: Échec du chargement des documents]"
            return

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

        # ---- Phase 1: Query decomposition ----
        yield "[SEARCHING]\n"
        decomposition = await self.decompose_query(query, context_overview, mode, model_type)
        yield f"[AGENT_DECOMPOSE]{json.dumps(decomposition, ensure_ascii=False)}\n"

        sub_questions = (
            decomposition.get("sub_questions", [query])
            if decomposition.get("needs_decomposition")
            else [query]
        )

        # ---- Phase 2: ReAct loop ----
        gathered: List[dict] = []
        all_nodes: List[str] = []  # qualified node refs "doc_id::node_id"

        def _qualify_nodes(obs_nodes: List[str], obs_doc_id: Optional[str],
                           per_doc_nodes: Optional[dict] = None) -> List[str]:
            # Build a reverse lookup {node_id -> doc_id} from cross_search's
            # per_doc_nodes, so bare node refs returned by multi-doc tools get
            # the correct document prefix (instead of silently defaulting to
            # the caller's obs_doc_id, which is usually None for cross_search
            # and leads to unclickable nodes on the frontend).
            #
            # If the same node_id happens to collide across documents (very
            # rare in practice since ids are per-tree), first-seen wins — the
            # qualified result is still better than leaving it bare.
            rev = {}
            if per_doc_nodes:
                for did, nids in per_doc_nodes.items():
                    if not did:
                        continue
                    for nid in (nids or []):
                        if nid and nid not in rev:
                            rev[nid] = did
            out = []
            for n in obs_nodes:
                if "::" in n:
                    out.append(n)
                elif n in rev:
                    out.append(f"{rev[n]}::{n}")
                elif obs_doc_id:
                    out.append(f"{obs_doc_id}::{n}")
                else:
                    out.append(n)
            return out

        for sq_idx, sub_q in enumerate(sub_questions):
            for step in range(MAX_REACT_STEPS):
                step_result = await self.think_and_act(
                    sub_q, gathered, tool_context, context_overview, model_type
                )

                thought = step_result.get("thought", "")
                action = step_result.get("action", {})
                tool_name = action.get("tool", "final_answer")
                tool_input = action.get("input", {}) or {}

                if tool_name == "final_answer":
                    yield self._step_marker(
                        sq_idx, step, thought, "final_answer", {}, "Ready to answer"
                    )
                    break

                tool = self.registry.get(tool_name)
                if tool:
                    try:
                        observation = await tool.execute(tool_input, tool_context)
                    except Exception as e:
                        logger.error(f"Tool {tool_name} error: {e}")
                        observation = {"summary": f"Tool error: {e}", "nodes": []}
                else:
                    observation = {"summary": f"Unknown tool: {tool_name}", "nodes": []}

                obs_nodes = observation.get("nodes", []) or []
                obs_doc_id = observation.get("doc_id") or tool_input.get("doc_id")
                per_doc_nodes = observation.get("per_doc_nodes")
                qualified = _qualify_nodes(obs_nodes, obs_doc_id, per_doc_nodes)
                all_nodes.extend(qualified)

                gathered.append({
                    "question": sub_q,
                    "thought": thought,
                    "tool": tool_name,
                    "input": tool_input,
                    "doc_id": obs_doc_id,
                    "observation": observation.get("summary", ""),
                })

                yield self._step_marker(
                    sq_idx, step, thought, tool_name, tool_input,
                    observation.get("summary", ""),
                )

        unique_nodes = list(dict.fromkeys(all_nodes))
        if unique_nodes:
            yield f"\n[NODES]{json.dumps(unique_nodes)}\n"

        # ---- Phase 3: Generate answer ----
        yield "[ANSWERING]\n"

        answer_context = self._build_answer_context(gathered, tool_context)
        history_context = self._build_history_context(session_id, use_memory)

        is_vision = model_type != "text"
        grounding = GROUNDING_INSTRUCTION_KB if mode == "kb" else GROUNDING_INSTRUCTION_SINGLE

        full_answer = ""

        if is_vision:
            priority_refs = self._get_priority_node_refs(gathered, unique_nodes)
            image_paths = self._collect_images_for_refs(priority_refs, tool_context)
            vision_prompt = self._build_vision_answer_prompt(
                query, sub_questions, history_context,
                decomposition.get("synthesis_strategy", "direct"),
                gathered_context=answer_context,
                grounding=grounding,
                mode=mode,
                docs_overview=context_overview,
            )
            if image_paths:
                async for chunk in self.pageindex.call_vlm_stream(
                    vision_prompt, image_paths, model_type
                ):
                    full_answer += chunk
                    yield chunk
            else:
                answer_prompt = self._build_answer_prompt(
                    query, sub_questions, answer_context, history_context,
                    decomposition.get("synthesis_strategy", "direct"),
                    grounding=grounding, mode=mode,
                    docs_overview=context_overview,
                )
                async for chunk in self.pageindex.call_llm_stream(answer_prompt, model_type):
                    full_answer += chunk
                    yield chunk
        else:
            answer_prompt = self._build_answer_prompt(
                query, sub_questions, answer_context, history_context,
                decomposition.get("synthesis_strategy", "direct"),
                grounding=grounding, mode=mode,
                docs_overview=context_overview,
            )
            async for chunk in self.pageindex.call_llm_stream(answer_prompt, model_type):
                full_answer += chunk
                yield chunk
        yield "[ANSWER_DONE]\n"

        # ---- Persist to session history (BEFORE reflection) ----
        # Persisting here (rather than at the very end of run_session) means:
        #   * simple questions that skip reflection still get saved
        #   * a reflection LLM error won't drop the conversation
        #   * user-initiated Stop during reflection still keeps the answer
        # If Phase 4 retry produces a better answer we overwrite in place.
        def _thinking_summary(g_list):
            return "\n".join(
                f"Step {i+1} [{g['tool']}{(' doc=' + g['doc_id']) if g.get('doc_id') else ''}]: {g['thought']}"
                for i, g in enumerate(g_list)
            )

        self.sessions.add_message(session_id, Message(role="user", content=query))
        self.sessions.add_message(session_id, Message(
            role="assistant",
            content=full_answer,
            nodes=list(dict.fromkeys(all_nodes)),
            thinking=_thinking_summary(gathered),
            quality=self._estimate_quality(full_answer, list(dict.fromkeys(all_nodes)), tool_context),
        ))

        # ---- Phase 4: Self-reflection ----
        # Fast path: if the agent chose final_answer on the very first step
        # without invoking any content tool (gathered is empty), this is a
        # trivial / meta / chit-chat question. Reflection adds latency and
        # cost but almost never flips the answer here, so skip it entirely
        # and do NOT emit [AGENT_REFLECT] (no "Auto-vérification" UI for trivial turns).
        if not gathered:
            return

        # Judge the answer against the SAME evidence the writer received —
        # not 600-char observation previews. Those previews made the judge
        # flag legitimate content as "absent from the extract" (e.g. facts
        # from the end of a node) and trigger pointless retries.
        context_summary = answer_context
        yield "[REFLECTING]\n"
        reflection = await self.reflect(
            query, full_answer, context_summary, model_type, is_vision,
            docs_overview=context_overview,
        )
        yield f"\n[AGENT_REFLECT]{json.dumps(reflection, ensure_ascii=False)}\n"
        self.sessions.update_last_message(session_id, "assistant", verification={
            "score": reflection.get("score"), "issues": reflection.get("issues") or [],
            "missing_info": reflection.get("missing_info") or [], "auto": True,
        })

        if (reflection.get("action") == "retry"
                and reflection.get("score", 10) < REFLECT_ACCEPT_THRESHOLD):
            yield "[AGENT_RETRY]\n"

            # Snapshot state BEFORE retry so we can persist the retry round
            # as a SEPARATE assistant message (continuing the conversation
            # rather than overwriting the low-score draft).
            gathered_cutoff = len(gathered)

            missing = reflection.get("missing_info", [])
            if missing:
                extra_query = "; ".join(missing)
                for step in range(MAX_REACT_STEPS):
                    step_result = await self.think_and_act(
                        extra_query, gathered, tool_context, context_overview, model_type
                    )
                    thought = step_result.get("thought", "")
                    action = step_result.get("action", {})
                    tool_name = action.get("tool", "final_answer")
                    tool_input = action.get("input", {}) or {}

                    if tool_name == "final_answer":
                        break

                    tool = self.registry.get(tool_name)
                    if tool:
                        try:
                            observation = await tool.execute(tool_input, tool_context)
                        except Exception as e:
                            observation = {"summary": f"Error: {e}", "nodes": []}
                    else:
                        observation = {"summary": "Unknown tool", "nodes": []}

                    obs_nodes = observation.get("nodes", []) or []
                    obs_doc_id = observation.get("doc_id") or tool_input.get("doc_id")
                    per_doc_nodes = observation.get("per_doc_nodes")
                    qualified = _qualify_nodes(obs_nodes, obs_doc_id, per_doc_nodes)
                    all_nodes.extend(qualified)
                    gathered.append({
                        "question": extra_query,
                        "thought": thought,
                        "tool": tool_name,
                        "input": tool_input,
                        "doc_id": obs_doc_id,
                        "observation": observation.get("summary", ""),
                    })
                    yield self._step_marker(
                        len(sub_questions), step, thought, tool_name,
                        tool_input, observation.get("summary", ""),
                    )

                answer_context = self._build_answer_context(gathered, tool_context)
                unique_nodes = list(dict.fromkeys(all_nodes))
                if unique_nodes:
                    yield f"\n[NODES]{json.dumps(unique_nodes)}\n"

                yield "[RETRY_ANSWERING]\n"

                full_answer = ""
                if is_vision:
                    retry_priority = self._get_priority_node_refs(gathered, unique_nodes)
                    retry_images = self._collect_images_for_refs(retry_priority, tool_context)
                    retry_vision_prompt = self._build_vision_answer_prompt(
                        query, sub_questions, history_context,
                        decomposition.get("synthesis_strategy", "direct"),
                        gathered_context=answer_context,
                        grounding=grounding, mode=mode,
                        docs_overview=context_overview,
                    )
                    if retry_images:
                        async for chunk in self.pageindex.call_vlm_stream(
                            retry_vision_prompt, retry_images, model_type
                        ):
                            full_answer += chunk
                            yield chunk
                    else:
                        retry_prompt = self._build_answer_prompt(
                            query, sub_questions, answer_context, history_context,
                            decomposition.get("synthesis_strategy", "direct"),
                            grounding=grounding, mode=mode,
                            docs_overview=context_overview,
                        )
                        async for chunk in self.pageindex.call_llm_stream(retry_prompt, model_type):
                            full_answer += chunk
                            yield chunk
                else:
                    retry_prompt = self._build_answer_prompt(
                        query, sub_questions, answer_context, history_context,
                        decomposition.get("synthesis_strategy", "direct"),
                        grounding=grounding, mode=mode,
                        docs_overview=context_overview,
                    )
                    async for chunk in self.pageindex.call_llm_stream(retry_prompt, model_type):
                        full_answer += chunk
                        yield chunk

            # Retry produced a (hopefully better) answer. Instead of
            # overwriting the low-score draft, APPEND it as a second
            # assistant turn so the full conversation is preserved —
            # user sees: [user] → [draft answer] → [reflect + retry steps]
            # → [improved answer], and the next turn's history_context
            # naturally continues from here.
            retry_gathered = gathered[gathered_cutoff:]
            # The retry answer is grounded in the FULL gathered context (its
            # prompt embeds answer_context built from every step), so persist
            # every source node — not just those found during the retry round,
            # which is often empty and used to strip the final message of its
            # sources (breaking the nodes box and citation resolution).
            retry_nodes = list(dict.fromkeys(all_nodes))

            def _thinking_summary_renumbered(g_list):
                return "\n".join(
                    f"Step {i+1} [{g['tool']}{(' doc=' + g['doc_id']) if g.get('doc_id') else ''}]: {g['thought']}"
                    for i, g in enumerate(g_list)
                )

            self.sessions.add_message(session_id, Message(
                role="assistant",
                content=full_answer,
                nodes=retry_nodes,
                thinking=_thinking_summary_renumbered(retry_gathered),
                quality=self._estimate_quality(full_answer, retry_nodes, tool_context),
            ))

            # Flag the low-score draft (the previous assistant message) as
            # superseded so _build_history_context skips it in subsequent
            # turns. UI history still renders it — only LLM context is
            # cleaned up. This also side-steps providers that reject two
            # consecutive assistant messages.
            self.sessions.mark_superseded_before_last(session_id, role="assistant")

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

    def _build_answer_context(self, gathered: list, tool_context: dict) -> str:
        """Assemble answer context, grouping by document in multi-doc mode.

        Output layout:
          【Trace de raisonnement】 Thought / Action / Observation of every ReAct step,
                           so Phase-3 LLM can continue from the same mental state.
          【Résultats d'analyse】   summarize_nodes outputs (already LLM-processed).
          【Texte source】          raw node texts grouped by document (grounding source).
          【Analyse visuelle】      view_pages VLM observations.
        """
        import re

        ANALYTICAL_TOOLS = {"summarize_nodes"}
        docs = tool_context.get("docs") or {}
        mode = tool_context.get("mode", "single")

        # -------- Reasoning trace (Thought / Action / Observation per step) --------
        trace_lines = []
        for i, g in enumerate(gathered, 1):
            tool = g.get("tool", "")
            did = g.get("doc_id")
            tool_input = g.get("input", {}) or {}
            try:
                input_str = json.dumps(tool_input, ensure_ascii=False)
            except Exception:
                input_str = str(tool_input)
            thought = (g.get("thought") or "").strip()
            obs = (g.get("observation") or "").strip()
            action_line = f"{tool}({input_str})"
            if did:
                action_line = f"[doc={did}] " + action_line
            trace_lines.append(
                f"Step {i}:\n"
                f"  Thought: {thought}\n"
                f"  Action:  {action_line}\n"
                f"  Observation: {obs}"
            )
        trace_block = "\n\n".join(trace_lines)

        analytically_processed = set()   # qualified node refs
        analytical_outputs = []
        seen_obs_keys = set()

        def _qual(did, nid):
            return f"{did}::{nid}" if did else nid

        for g in gathered:
            tool = g["tool"]
            if tool not in ANALYTICAL_TOOLS:
                continue
            obs = g.get("observation", "")
            if not obs:
                continue
            dedup_key = f"{tool}:{obs[:300]}"
            if dedup_key in seen_obs_keys:
                continue
            seen_obs_keys.add(dedup_key)
            analytical_outputs.append(f"[{tool}] {obs}")
            did = g.get("doc_id")
            for nid in g.get("input", {}).get("node_ids", []) or []:
                analytically_processed.add(_qual(did, nid))
            single = g.get("input", {}).get("node_id", "")
            if single:
                analytically_processed.add(_qual(did, single))

        # Collect raw texts, grouped by doc_id so the answer can cite cleanly.
        per_doc_raw: dict = {}
        visual_observations = []
        seen_refs = set()

        def _add_node_text(did, nid):
            dctx = docs.get(did) or {}
            node_map = dctx.get("node_map") or {}
            # Observations mix "node_0001" and bare "0001" spellings while the
            # node_map keys are bare — normalise before lookup.
            if nid not in node_map and nid.startswith("node_") and nid[5:] in node_map:
                nid = nid[5:]
            ref = _qual(did, nid)
            if ref in seen_refs or ref in analytically_processed:
                return
            if nid not in node_map:
                return
            info = node_map[nid]
            node = info.get("node", info)
            text = node.get("text", "") if isinstance(node, dict) else ""
            if text:
                per_doc_raw.setdefault(did, []).append(text)
                seen_refs.add(ref)

        for g in gathered:
            tool = g["tool"]
            did = g.get("doc_id")

            if tool == "read_node":
                single = g["input"].get("node_id", "")
                batch = g["input"].get("node_ids", []) or []
                for nid in ([single] if single else []) + batch:
                    _add_node_text(did, nid)

            elif tool == "tree_search":
                obs = g.get("observation", "")
                # tree_search lists nodes with bare ids ("- 0001: Title") —
                # the node_ prefix only appears if the model echoed it.
                for nid in re.findall(r"node_\S+|\b\d{4}\b", obs):
                    _add_node_text(did, nid)

            elif tool == "cross_search":
                # per_doc_nodes may be present in raw return; fall back to scanning.
                obs = g.get("observation", "")
                # Very rough: pull out "[doc_x] filename" section headers and
                # associated node_ids until next blank line.
                cur_did = None
                for line in obs.split("\n"):
                    m = re.match(r"•\s+\[(\S+)\]", line.strip())
                    if m:
                        cur_did = m.group(1)
                        continue
                    for nid in re.findall(r"node_\S+|\b\d{4}\b", line):
                        if cur_did:
                            _add_node_text(cur_did, nid)

            elif tool == "view_pages":
                obs = g.get("observation", "")
                if obs and "Visual analysis" in obs:
                    visual_observations.append(obs)

            elif tool == "keyword_search":
                obs = g.get("observation", "")
                if obs:
                    per_doc_raw.setdefault(did or "_unknown", []).append(f"[{tool}] {obs}")

        # Fallback: if nothing at all, sprinkle in a few nodes from primary doc.
        if not per_doc_raw and not analytical_outputs and not visual_observations:
            primary = tool_context.get("primary_doc_id")
            if primary and primary in docs:
                nm = docs[primary].get("node_map") or {}
                for nid in list(nm.keys())[:3]:
                    _add_node_text(primary, nid)

        parts = []
        if trace_block:
            parts.append(
                "【Trace de raisonnement de l'Agent — tes Thought/Action/Observation étape par étape, "
                "pour reprendre le fil du raisonnement】\n" + trace_block
            )
        if analytical_outputs:
            parts.append(
                "【Résultats d'analyse des outils — déjà traités par l'IA, fais-leur confiance et appuie-toi dessus pour répondre】\n"
                + "\n\n".join(analytical_outputs)
            )
        if per_doc_raw:
            doc_sections = []
            # Give each doc its own budget proportional to presence.
            budget_total = 4000 if analytical_outputs else 12000
            per_doc_budget = max(800, budget_total // max(1, len(per_doc_raw)))
            for did, texts in per_doc_raw.items():
                filename = (docs.get(did) or {}).get("filename", did)
                header = (
                    f"📄 Document [{did}] {filename}\n" if mode == "kb" else "【Extraits du texte source】\n"
                )
                combined = "\n\n".join(texts)
                if len(combined) > per_doc_budget:
                    combined = combined[:per_doc_budget] + "\n...(truncated)"
                doc_sections.append(header + combined)
            parts.append("\n\n".join(doc_sections))
        if visual_observations:
            parts.append("【Analyse visuelle】\n" + "\n\n".join(visual_observations))

        # Mode multi-documents : l'inventaire des fiches identitaires de TOUTES
        # les pièces de la session est toujours joint comme source citable.
        # Usage canonique des résumés d'arbre (l'index) : une question de
        # synthèse de corpus se répond depuis les fiches (nature, auteur,
        # destinataire, date), pas depuis 2-3 lectures partielles — et chaque
        # pièce mentionnée porte alors une vraie citation résoluble.
        if mode == "kb" and len(docs) > 1:
            inv_lines = []
            for did, dctx in docs.items():
                node_map = dctx.get("node_map") or {}
                if not node_map:
                    continue
                root_id = min(node_map.keys())
                info = node_map.get(root_id) or {}
                node = info.get("node", info)
                summary = (node.get("summary") or "").strip() if isinstance(node, dict) else ""
                if len(summary) > 700:
                    summary = summary[:700] + "…"
                s, e = info.get("start_index"), info.get("end_index")
                pages = f"pages {s}-{e}" if s and e and s != e else f"page {s or 1}"
                inv_lines.append(
                    f"📄 {dctx.get('filename', did)} (node_{root_id}, {pages})\n{summary}"
                )
            if inv_lines:
                inventory = "\n\n".join(inv_lines)
                if len(inventory) > 30000:
                    inventory = inventory[:30000] + "\n...(inventaire tronqué)"
                parts.append(
                    "【Inventaire des pièces — fiche identitaire de CHAQUE document de la session. "
                    "Source citable au même titre que les extraits : cite "
                    "`(doc: <fichier>, node_<id>, page N)` avec le fichier et le node indiqués "
                    "sur la ligne 📄 de la pièce concernée.】\n" + inventory
                )

        return "\n\n".join(parts)

    @staticmethod
    def _get_priority_node_refs(gathered: list, all_unique_nodes: list) -> list:
        """Return qualified node refs (doc::nid) from the most recent visual/search call."""
        import re
        last_visual = []
        last_search = []

        for g in reversed(gathered):
            did = g.get("doc_id")
            if g["tool"] == "view_pages" and not last_visual:
                for nid in g["input"].get("node_ids", []) or []:
                    last_visual.append(f"{did}::{nid}" if did else nid)
            if g["tool"] == "tree_search" and not last_search:
                obs = g.get("observation", "")
                for nid in re.findall(r"(node_\S+)", obs):
                    last_search.append(f"{did}::{nid}" if did else nid)
            if last_visual and last_search:
                break

        priority = last_visual or last_search
        if priority:
            seen = set()
            out = []
            for ref in priority:
                if ref not in seen:
                    seen.add(ref)
                    out.append(ref)
            return out
        return all_unique_nodes

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
