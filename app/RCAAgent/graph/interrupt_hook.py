"""
Step-by-step execution hook for investigation graph.

This hook enables controlled step-by-step execution by raising an interrupt
before each node execution (except the first). The graph pauses with
INTERRUPTED status and can be resumed to execute the next node.
"""

import logging
from typing import Any

from strands.hooks.events import BeforeNodeCallEvent
from strands.hooks.registry import HookRegistry, HookProvider

logger = logging.getLogger(__name__)


class StepByStepExecutionHook(HookProvider):
    """
    Hook that enables step-by-step execution of graph nodes.

    On the first invocation, allows the first node to execute normally.
    Before each subsequent node, raises an interrupt to pause the graph.
    After the user resumes, the next node executes, and the cycle continues.

    This ensures exactly one node executes per invocation/resume cycle.
    """

    def __init__(self) -> None:
        """Initialize the hook with an execution counter."""
        self._nodes_executed = 0

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register the before-node callback."""
        registry.add_callback(BeforeNodeCallEvent, self._on_before_node_call)

    def _on_before_node_call(self, event: BeforeNodeCallEvent) -> None:
        """
        Interrupt before executing each node (except the first).

        The counter tracks how many nodes have been allowed to execute
        in the current graph invocation. When resuming from an interrupt,
        the counter is reset, allowing the next node to execute.
        """
        logger.debug(
            "node_id=<%s>, nodes_executed=<%d> | before node call",
            event.node_id,
            self._nodes_executed,
        )

        if self._nodes_executed > 0:
            # Interrupt before the second+ node
            logger.info(
                "node_id=<%s> | interrupting before node execution (step-by-step mode)",
                event.node_id,
            )
            # Reset counter for next resume cycle
            self._nodes_executed = 0
            # Raise the interrupt - graph will pause with INTERRUPTED status
            event.interrupt(
                name="step_by_step_execution",
                reason=f"Paused before executing node '{event.node_id}'",
            )
        else:
            # Allow this node to execute
            self._nodes_executed += 1
            logger.debug(
                "node_id=<%s> | allowing node execution (nodes_executed=%d)",
                event.node_id,
                self._nodes_executed,
            )
