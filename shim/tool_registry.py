"""Tool Registry -- maps tool_id to destination, method, and secret.

When an agent sends a request with ``tool_id`` instead of
``destination_url``, the shim resolves the tool from this registry.
This is the full-air-gap path: the agent never sees the real
destination URL or which secret is used.
"""

from __future__ import annotations

from typing import Optional

from .models import ToolDefinition


class ToolNotFoundError(Exception):
    """Raised when a tool_id is not in the registry."""

    pass


class ToolRegistry:
    """In-memory tool registry. Production deployments can back this
    with a database using the same interface.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register or update a tool mapping."""
        self._tools[tool.tool_id] = tool

    def get(self, tool_id: str) -> ToolDefinition:
        """Resolve a tool_id to its definition.

        Raises:
            ToolNotFoundError: If the tool_id is not registered.
        """
        tool = self._tools.get(tool_id)
        if tool is None:
            raise ToolNotFoundError(f"Tool '{tool_id}' is not registered")
        return tool

    def unregister(self, tool_id: str) -> None:
        self._tools.pop(tool_id, None)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_optional(self, tool_id: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_id)
