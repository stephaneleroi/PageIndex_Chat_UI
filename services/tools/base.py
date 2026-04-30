"""
Base tool interface and registry for the Agent tool system
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


def resolve_doc(params: dict, context: dict) -> Tuple[Optional[str], dict, Optional[str]]:
    """Resolve which document a tool call should act on.

    Returns (doc_id, doc_ctx, error_message).
    If error_message is set, doc_id/doc_ctx are best-effort.

    Rules:
      - ``context['docs']`` is a dict keyed by doc_id, each value holds
        {'tree', 'node_map', 'page_images', 'filename'}.
      - params['doc_id'] wins when provided and accessible.
      - otherwise we fall back to ``context['primary_doc_id']``.
      - the chosen doc_id must be in ``context['accessible_doc_ids']``
        (if that list is present).
    """
    docs = context.get("docs") or {}
    accessible = context.get("accessible_doc_ids")

    requested = (params or {}).get("doc_id")
    primary = context.get("primary_doc_id")

    doc_id = requested or primary

    if accessible is not None and doc_id and doc_id not in accessible:
        return (
            doc_id,
            {},
            f"Document '{doc_id}' is not in the accessible set {sorted(accessible)}. "
            "You can only operate on documents listed by list_documents.",
        )

    if not doc_id:
        return (
            None,
            {},
            "No doc_id specified and no primary document available. "
            "Use list_documents first, then pass doc_id explicitly.",
        )

    doc_ctx = docs.get(doc_id)
    if not doc_ctx:
        return (
            doc_id,
            {},
            f"Document '{doc_id}' is not loaded in this turn. "
            "Check list_documents for the current accessible set.",
        )

    return doc_id, doc_ctx, None


class BaseTool(ABC):
    """Abstract base class for all agent tools"""

    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}

    def get_spec(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
        }

    @abstractmethod
    async def execute(self, params: dict, context: dict) -> dict:
        """
        Execute the tool.

        Args:
            params: Tool-specific parameters (from LLM action output)
            context: Shared context. Expected keys:
                - mode: 'single' | 'kb'
                - primary_doc_id: str | None
                - accessible_doc_ids: list[str]
                - docs: { doc_id: {tree, node_map, page_images, filename, analysis, page_count} }
                - model_type: 'text' | 'vision'

        Returns:
            dict with at least a 'summary' key for the agent to consume,
            and optionally 'nodes', 'doc_id', 'content', 'pages', etc.
        """
        raise NotImplementedError


class ToolRegistry:
    """Registry that manages all available tools"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def all_specs(self) -> List[dict]:
        return [t.get_spec() for t in self._tools.values()]

    def all_names(self) -> List[str]:
        return list(self._tools.keys())
