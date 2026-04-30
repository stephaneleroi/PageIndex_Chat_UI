"""
read_document_toc — returns the table of contents of a specific document.

Progressive disclosure: list_documents gives you filenames/summaries; once you
know a document is relevant, call this to see its top-level tree (titles +
one-line summaries). Only when a particular branch looks promising should you
drill down with tree_search / read_node / view_pages.
"""

import logging
from .base import BaseTool, resolve_doc

logger = logging.getLogger(__name__)

MAX_DEPTH = 2   # how deep into the tree to show


class ReadTocTool(BaseTool):
    name = "read_document_toc"
    description = (
        "Read a document's table of contents (top levels of its tree) so you can "
        "decide which sections to explore. Returns node IDs, titles, summaries and "
        "page ranges. Use this BEFORE tree_search whenever you need to understand a "
        "document's structure."
    )
    parameters_schema = {
        "doc_id": {
            "type": "string",
            "description": "Required. The document whose TOC you want to read.",
        },
        "max_depth": {
            "type": "integer",
            "description": f"Optional. How many levels deep to show (default {MAX_DEPTH}).",
        },
    }

    async def execute(self, params: dict, context: dict) -> dict:
        doc_id, doc_ctx, err = resolve_doc(params, context)
        if err:
            return {"summary": err, "nodes": []}

        tree = doc_ctx.get("tree")
        if not tree:
            return {
                "summary": f"[doc={doc_id}] Tree not available.",
                "nodes": [],
                "doc_id": doc_id,
            }

        max_depth = int(params.get("max_depth") or MAX_DEPTH)

        filename = doc_ctx.get("filename", doc_id)
        lines = [f"TOC of [{doc_id}] {filename}:"]
        node_ids: list = []

        def walk(node, depth):
            if depth > max_depth:
                return
            if isinstance(node, list):
                for n in node:
                    walk(n, depth)
                return
            if not isinstance(node, dict):
                return
            title = node.get("title", "")
            nid = node.get("node_id", "")
            summary_txt = (node.get("summary") or "").strip().replace("\n", " ")
            if summary_txt and len(summary_txt) > 120:
                summary_txt = summary_txt[:120] + "…"
            page = node.get("start_index") or node.get("physical_index") or ""
            indent = "  " * (depth - 1) if depth > 0 else ""
            if nid:
                node_ids.append(nid)
                header = f"{indent}- [{nid}] {title}"
                if page:
                    header += f"  (p.{page})"
                lines.append(header)
                if summary_txt:
                    lines.append(f"{indent}    {summary_txt}")

            for child_key in ("nodes", "children"):
                children = node.get(child_key)
                if children:
                    walk(children, depth + 1)

        walk(tree, 1)

        return {
            "summary": "\n".join(lines),
            "nodes": node_ids,
            "doc_id": doc_id,
        }
