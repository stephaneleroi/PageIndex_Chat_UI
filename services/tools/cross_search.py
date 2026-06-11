"""
cross_search — tree_search across multiple documents in parallel.

Useful when the agent wants to find out where a concept is covered across
a set of candidate documents without calling tree_search N times manually.
"""

import asyncio
import logging
import re
from .base import BaseTool

logger = logging.getLogger(__name__)

# Recherche littérale de secours quand tree_search ne trouve rien.
# Désactivée : on reste sur le retrieval par raisonnement pur (PageIndex).
LITERAL_FALLBACK = False

# Chaque document fouillé = un appel LLM ; sur un dossier de 50 pièces, un
# cross_search non ciblé coûterait 50 appels séquentiels sur Ollama. Au-delà
# de ce plafond, on traite les premiers documents et on demande à l'agent de
# cibler via list_documents + doc_ids.
MAX_DOCS_PER_CALL = 12


class CrossSearchTool(BaseTool):
    name = "cross_search"
    description = (
        "Search the same query across MULTIPLE documents in parallel. "
        "Returns, per document, the matching nodes (IDs + titles + summaries). "
        "Use this to locate which documents cover a topic before drilling in. "
        "Each searched document costs one LLM call: on large corpora, FIRST "
        "narrow the candidates with list_documents (their summaries identify "
        "each piece) and pass an explicit doc_ids list (max 12 per call)."
    )
    parameters_schema = {
        "query": {
            "type": "string",
            "description": "What to search for across documents.",
        },
        "doc_ids": {
            "type": "array",
            "description": "Optional list of document IDs to search. Defaults to all accessible.",
        },
    }

    def __init__(self, pageindex_service):
        self.pageindex = pageindex_service

    async def _search_one(self, doc_id: str, query: str, docs: dict, model_type: str) -> dict:
        ctx = docs.get(doc_id) or {}
        tree = ctx.get("tree")
        node_map = ctx.get("node_map", {})
        filename = ctx.get("filename", doc_id)
        if not tree:
            return {"doc_id": doc_id, "filename": filename, "nodes": [], "error": "tree not loaded"}
        try:
            result = await self.pageindex.tree_search(query, tree, model_type)
        except Exception as e:
            return {"doc_id": doc_id, "filename": filename, "nodes": [], "error": str(e)}

        node_list = result.get("node_list", []) or []
        if not node_list and LITERAL_FALLBACK:
            # Repli littéral (DÉSACTIVÉ — hors paradigme PageIndex, conservé
            # à titre de référence) : balayage du texte brut des nœuds quand
            # le raisonnement sur l'arbre ne trouve rien. Le bon correctif
            # est d'enrichir les résumés de nœuds, pas de contourner l'arbre.
            q = query.lower()
            words = [w for w in re.split(r"\W+", q) if len(w) >= 4]
            for nid, info in node_map.items():
                node = info.get("node", info)
                if not isinstance(node, dict):
                    continue
                hay = ((node.get("text") or "") + " " + (node.get("title") or "")).lower()
                if q in hay or any(w in hay for w in words):
                    node_list.append(nid)
            node_list = node_list[:5]
        details = []
        for nid in node_list:
            info = node_map.get(nid, {})
            node = info.get("node", info)
            if isinstance(node, dict):
                details.append({
                    "node_id": nid,
                    "title": node.get("title", ""),
                    "summary": (node.get("summary") or "")[:150],
                })
        return {
            "doc_id": doc_id,
            "filename": filename,
            "nodes": node_list,
            "details": details,
        }

    async def execute(self, params: dict, context: dict) -> dict:
        query = params.get("query", "")
        if not query:
            return {"summary": "No query provided", "nodes": []}

        docs = context.get("docs") or {}
        accessible = context.get("accessible_doc_ids") or list(docs.keys())
        requested = params.get("doc_ids") or accessible
        doc_ids = [d for d in requested if d in set(accessible)]

        if not doc_ids:
            return {
                "summary": "No accessible documents to search.",
                "nodes": [],
            }

        capped_note = ""
        if len(doc_ids) > MAX_DOCS_PER_CALL:
            capped_note = (
                f"\n⚠ {len(doc_ids)} documents requested but only the first "
                f"{MAX_DOCS_PER_CALL} were searched (one LLM call each). "
                f"Narrow the candidates with list_documents (their summaries "
                f"identify each piece) and call cross_search again with an "
                f"explicit doc_ids list for the remaining relevant ones."
            )
            doc_ids = doc_ids[:MAX_DOCS_PER_CALL]

        model_type = context.get("model_type", "text")
        results = await asyncio.gather(*[
            self._search_one(d, query, docs, model_type) for d in doc_ids
        ])

        lines = [f"cross_search('{query}') across {len(doc_ids)} documents:" + capped_note]
        all_nodes = []
        per_doc_nodes = {}
        for r in results:
            doc_id = r["doc_id"]
            filename = r["filename"]
            if r.get("error"):
                lines.append(f"\n• [{doc_id}] {filename}: error — {r['error']}")
                continue
            nodes = r.get("nodes", [])
            per_doc_nodes[doc_id] = nodes
            if not nodes:
                lines.append(f"\n• [{doc_id}] {filename}: no matches")
                continue
            lines.append(f"\n• [{doc_id}] {filename} — {len(nodes)} match(es):")
            for d in r.get("details", []):
                lines.append(f"    - {d['node_id']}: {d['title']}  — {d['summary']}")
            all_nodes.extend(nodes)

        return {
            "summary": "\n".join(lines),
            "nodes": list(dict.fromkeys(all_nodes)),
            "per_doc_nodes": per_doc_nodes,
        }
