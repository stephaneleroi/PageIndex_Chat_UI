"""
Node reader tool - reads the full text content of document nodes (single or batch)
"""

import logging
from .base import BaseTool, resolve_doc

logger = logging.getLogger(__name__)


class NodeReaderTool(BaseTool):
    name = "read_node"
    description = (
        "Read the full text content of one or more document nodes. "
        "Use this to get detailed information from sections you've identified. "
        "In multi-document mode you MUST specify which document via doc_id."
    )
    parameters_schema = {
        "node_id": {
            "type": "string",
            "description": "ID of a single node to read (e.g. 'node_1_2'). Use this OR node_ids.",
        },
        "node_ids": {
            "type": "array",
            "description": "List of node IDs to read in batch. Use this OR node_id.",
        },
        "doc_id": {
            "type": "string",
            "description": "(multi-doc mode) ID of the document these nodes belong to.",
        },
    }

    async def execute(self, params: dict, context: dict) -> dict:
        doc_id, doc_ctx, err = resolve_doc(params, context)
        if err:
            return {"summary": err, "nodes": []}
        node_map = doc_ctx.get("node_map", {})

        ids = params.get("node_ids") or []
        single_id = params.get("node_id", "")
        if single_id and not ids:
            ids = [single_id]

        if not ids:
            return {"summary": "No node ID provided", "nodes": []}

        results = []
        found_nodes = []
        total_chars = 0

        for nid in ids:
            if nid not in node_map:
                results.append(f"- {nid}: not found")
                continue

            node_info = node_map[nid]
            node = node_info.get("node", node_info)
            title = node.get("title", "Untitled") if isinstance(node, dict) else "Untitled"
            text = node.get("text", "") if isinstance(node, dict) else ""

            if not text:
                results.append(f"- {nid} ({title}): no text content")
                found_nodes.append(nid)
                continue

            total_chars += len(text)
            preview = text[:300] + ("..." if len(text) > 300 else "")
            results.append(f"- {nid} ({title}), {len(text)} chars: {preview}")
            found_nodes.append(nid)

        # Make it explicit to the planner that only the PREVIEW is shown here
        # while the COMPLETE text is forwarded to the final answer — otherwise
        # it mistakes the preview for a truncated read and wastes steps
        # re-reading the same node through other tools.
        summary = (
            f"[doc={doc_id}] Read {len(found_nodes)}/{len(ids)} nodes, "
            f"{total_chars} total chars. The COMPLETE text of these nodes is "
            f"already available for the final answer — no need to re-read them; "
            f"previews below are shortened for display only:\n" + "\n".join(results)
        )

        all_texts = []
        for nid in found_nodes:
            if nid in node_map:
                node_info = node_map[nid]
                node = node_info.get("node", node_info)
                text = node.get("text", "") if isinstance(node, dict) else ""
                if text:
                    all_texts.append(text)

        return {
            "summary": summary,
            "nodes": found_nodes,
            "doc_id": doc_id,
            "content": "\n\n".join(all_texts),
        }
