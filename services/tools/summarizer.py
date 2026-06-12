"""
Summarizer tool - generates LLM-powered summaries of document sections
"""

import logging
from .base import BaseTool, resolve_doc

logger = logging.getLogger(__name__)


class SummarizerTool(BaseTool):
    name = "summarize_nodes"
    description = (
        "Generate a concise summary of one or more document nodes' content. "
        "Useful when you have a lot of text and need a quick overview. "
        "In multi-document mode specify doc_id."
    )
    parameters_schema = {
        "node_ids": {
            "type": "array",
            "description": "List of node IDs to summarize",
        },
        "doc_id": {
            "type": "string",
            "description": "(multi-doc mode) Document ID.",
        },
    }

    def __init__(self, pageindex_service):
        self.pageindex = pageindex_service

    async def execute(self, params: dict, context: dict) -> dict:
        doc_id, doc_ctx, err = resolve_doc(params, context)
        if err:
            return {"summary": err, "nodes": []}

        node_ids = params.get("node_ids", [])
        node_map = doc_ctx.get("node_map", {})
        model_type = context.get("model_type", "text")

        if not node_ids:
            return {"summary": "No node IDs provided", "nodes": []}

        texts = []
        for nid in node_ids:
            info = node_map.get(nid, {})
            node = info.get("node", info)
            title = node.get("title", nid) if isinstance(node, dict) else nid
            text = node.get("text", "") if isinstance(node, dict) else ""
            if text:
                texts.append(f"[{title}]\n{text[:8000]}")

        if not texts:
            return {
                "summary": f"[doc={doc_id}] No text content in the specified nodes.",
                "nodes": node_ids,
                "doc_id": doc_id,
            }

        combined = "\n\n---\n\n".join(texts)
        prompt = (
            "Summarize the following document sections concisely (max 300 words).\n"
            "The text contains <page_N>…</page_N> markers: annotate every fact you keep "
            "with its source page as `(page N)`, taken from the fact's enclosing marker "
            "— never guess a page and never echo the markers themselves.\n\n"
            f"{combined}"
        )

        try:
            result = await self.pageindex.call_llm(prompt, 'text')
            return {
                "summary": f"[doc={doc_id}] {result}",
                "nodes": node_ids,
                "doc_id": doc_id,
            }
        except Exception as e:
            logger.error(f"Summarizer error: {e}")
            return {
                "summary": f"[doc={doc_id}] Error generating summary: {e}",
                "nodes": node_ids,
                "doc_id": doc_id,
            }
