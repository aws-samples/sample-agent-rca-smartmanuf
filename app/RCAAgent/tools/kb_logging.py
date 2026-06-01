"""Knowledge Base Query Logging Hook."""

import logging
from typing import Any

from strands.hooks.events import AfterToolCallEvent
from strands.hooks.registry import HookRegistry, HookProvider

logger = logging.getLogger("investigation-agent")


class KBQueryLoggingHook(HookProvider):
    """Logs every Knowledge Base query via the retrieve tool."""

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(AfterToolCallEvent, self._on_after_tool_call)

    def _on_after_tool_call(self, event: AfterToolCallEvent) -> None:
        if event.tool_use.get("name") != "retrieve":
            return

        tool_input = event.tool_use.get("input", {})
        kb_id = tool_input.get("knowledgeBaseId", "UNKNOWN")
        query = tool_input.get("text", "")[:100]

        if event.exception:
            logger.warning("KB query FAILED: kb_id=%s, query=%s, error=%s", kb_id, query, event.exception)
        else:
            logger.info("KB query: kb_id=%s, query=%s", kb_id, query)
