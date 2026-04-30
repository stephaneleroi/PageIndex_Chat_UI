"""
Tree search tool - searches the document tree structure to find relevant sections
"""

import json
import logging
from .base import BaseTool, resolve_doc

logger = logging.getLogger(__name__)


class TreeSearchTool(BaseTool):
    name = "tree_search"
    description = (
        "Search a document's hierarchical tree to find sections relevant to a query. "
        "In single-document mode the doc_id is optional. In multi-document mode you MUST "
        "specify which document to search via doc_id."
    )
    parameters_schema = {
        "query": {
            "type": "string",
            "description": "The search query to find relevant document sections",
        },
        "doc_id": {
            "type": "string",
            "description": "(multi-doc mode) ID of the document to search. Omit in single-doc mode.",
        },
    }

    def __init__(self, pageindex_service):
        self.pageindex = pageindex_service

    async def execute(self, params: dict, context: dict) -> dict:
        query = params.get("query", "")
        doc_id, doc_ctx, err = resolve_doc(params, context)
        if err:
            return {"summary": err, "nodes": []}

        tree = doc_ctx.get("tree")
        node_map = doc_ctx.get("node_map", {})
        model_type = context.get("model_type", "text")

        if not tree or not query:
            return {"summary": "No tree or query provided", "nodes": []}

        result = await self.pageindex.tree_search(query, tree, model_type)

        node_list = result.get("node_list", [])
        thinking = result.get("thinking", "")

        node_details = []
        for nid in node_list:
            info = node_map.get(nid, {})
            node = info.get("node", info)
            if isinstance(node, dict):
                node_details.append(
                    f"- {nid}: {node.get('title', 'N/A')} "
                    f"(summary: {node.get('summary', 'N/A')[:100]})"
                )

        summary = (
            f"[doc={doc_id}] Found {len(node_list)} relevant nodes: "
            f"{', '.join(node_list)}.\n" + "\n".join(node_details)
        )

        return {
            "summary": summary,
            "nodes": node_list,
            "doc_id": doc_id,
            "thinking": thinking,
            "node_details": node_details,
        }
