"""
Keyword search tool - searches for exact keywords across all document nodes
"""

import logging
from .base import BaseTool, resolve_doc

logger = logging.getLogger(__name__)


class KeywordSearchTool(BaseTool):
    name = "keyword_search"
    description = (
        "Search for an exact keyword or phrase across a document's nodes. "
        "Useful for finding specific terms, numbers, names, or technical concepts. "
        "In multi-document mode specify doc_id."
    )
    parameters_schema = {
        "keyword": {
            "type": "string",
            "description": "The exact keyword or phrase to search for",
        },
        "doc_id": {
            "type": "string",
            "description": "(multi-doc mode) Document ID to search within.",
        },
    }

    async def execute(self, params: dict, context: dict) -> dict:
        doc_id, doc_ctx, err = resolve_doc(params, context)
        if err:
            return {"summary": err, "nodes": []}

        keyword = params.get("keyword", "").lower()
        node_map = doc_ctx.get("node_map", {})

        if not keyword:
            return {"summary": "No keyword provided", "nodes": []}

        matches = []
        matched_nodes = []

        for nid, info in node_map.items():
            node = info.get("node", info)
            text = node.get("text", "") if isinstance(node, dict) else ""
            title = node.get("title", "") if isinstance(node, dict) else ""

            if keyword in text.lower() or keyword in title.lower():
                pos = text.lower().find(keyword)
                if pos >= 0:
                    start = max(0, pos - 60)
                    end = min(len(text), pos + len(keyword) + 60)
                    snippet = "..." + text[start:end] + "..."
                else:
                    snippet = f"(found in title: {title})"

                matches.append(f"- {nid} ({title}): {snippet}")
                matched_nodes.append(nid)

        if not matches:
            return {
                "summary": f"[doc={doc_id}] Keyword '{keyword}' not found.",
                "nodes": [],
                "doc_id": doc_id,
            }

        summary = (
            f"[doc={doc_id}] Found '{keyword}' in {len(matches)} nodes:\n"
            + "\n".join(matches[:10])
        )
        return {
            "summary": summary,
            "nodes": matched_nodes,
            "doc_id": doc_id,
            "match_count": len(matches),
        }
