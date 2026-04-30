"""
list_documents — exposes document-level metadata to the agent.

This is the *first* tool a KB-mode agent should call: it returns filenames,
page counts, summaries and main topics for every accessible document. It
intentionally does NOT include the table of contents or any body text —
that information is only fetched on demand via read_document_toc.
"""

import logging
from .base import BaseTool

logger = logging.getLogger(__name__)


class ListDocumentsTool(BaseTool):
    name = "list_documents"
    description = (
        "List every document currently accessible in this chat turn, along with "
        "a short summary and its main topics. Call this FIRST in knowledge-base "
        "mode to decide which documents are worth drilling into. "
        "Returns doc_id, filename, page count, summary, main_topics."
    )
    parameters_schema = {}

    async def execute(self, params: dict, context: dict) -> dict:
        docs = context.get("docs") or {}
        accessible = context.get("accessible_doc_ids") or list(docs.keys())

        if not accessible:
            return {
                "summary": "No documents accessible in this session.",
                "documents": [],
            }

        lines = []
        meta_list = []
        for doc_id in accessible:
            d = docs.get(doc_id) or {}
            filename = d.get("filename", doc_id)
            page_count = d.get("page_count", 0)
            analysis = d.get("analysis") or {}
            summary_txt = (analysis.get("summary") or "").strip()
            topics = analysis.get("main_topics") or []
            topics_s = ", ".join(topics) if topics else "—"

            line = (
                f"- {doc_id} | {filename} | {page_count} pages\n"
                f"    summary : {summary_txt or '(no analysis yet)'}\n"
                f"    topics  : {topics_s}"
            )
            lines.append(line)
            meta_list.append({
                "doc_id": doc_id,
                "filename": filename,
                "page_count": page_count,
                "summary": summary_txt,
                "main_topics": topics,
            })

        summary = (
            f"{len(accessible)} document(s) accessible:\n" + "\n".join(lines)
        )
        return {
            "summary": summary,
            "documents": meta_list,
        }
