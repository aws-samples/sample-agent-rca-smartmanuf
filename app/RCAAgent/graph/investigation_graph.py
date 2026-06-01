"""
Investigation Graph Orchestration

Coordinates the execution of Step 1 → Step 2 → Step 3 agents using
Strands multi-agent GraphBuilder.
"""

import os
import json
import logging

from strands.multiagent.graph import GraphBuilder

from agents.step1_agent import create_step1_agent
from agents.step2_agent import create_step2_agent
from agents.step3_agent import create_step3_agent
from graph.interrupt_hook import StepByStepExecutionHook

logger = logging.getLogger(__name__)

RETRIEVAL_MODE = os.environ.get("RETRIEVAL_MODE", "both")
KB_HYBRID_ID = os.environ.get("KB_HYBRID_ID", "")
KB_GRAPHRAG_ID = os.environ.get("KB_GRAPHRAG_ID", "")


def _build_kb_context() -> str:
    """Build knowledge base context instructions based on retrieval mode."""
    lines = ["\n## Knowledge Base Configuration\n"]

    if RETRIEVAL_MODE in ("hybrid", "both") and KB_HYBRID_ID:
        lines.append(
            f"- Hybrid Search KB (keyword + semantic): knowledge_base_id = {KB_HYBRID_ID}"
        )
    if RETRIEVAL_MODE in ("graphrag", "both") and KB_GRAPHRAG_ID:
        lines.append(
            f"- GraphRAG KB (semantic + graph traversal): knowledge_base_id = {KB_GRAPHRAG_ID}"
        )

    if RETRIEVAL_MODE == "both":
        lines.append(
            "\nWhen using the retrieve tool, query BOTH knowledge bases for best recall. "
            "The hybrid KB excels at keyword-precise searches; the GraphRAG KB excels at "
            "discovering related entities and cross-document relationships."
        )
    elif RETRIEVAL_MODE == "hybrid":
        lines.append(f"\nUse knowledge_base_id = {KB_HYBRID_ID} for all retrieve calls.")
    elif RETRIEVAL_MODE == "graphrag":
        lines.append(f"\nUse knowledge_base_id = {KB_GRAPHRAG_ID} for all retrieve calls.")

    return "\n".join(lines)


def create_investigation_graph() -> GraphBuilder:
    """
    Build the 3-step investigation graph.

    Returns a compiled graph: step1 → step2 → step3
    """
    kb_context = _build_kb_context()

    step1 = create_step1_agent()
    step2 = create_step2_agent()
    step3 = create_step3_agent()

    # Append KB configuration to each agent's system prompt
    for agent in (step1, step2, step3):
        agent.system_prompt = agent.system_prompt + kb_context

    builder = GraphBuilder()
    builder.add_node(step1, "step1")
    builder.add_node(step2, "step2")
    builder.add_node(step3, "step3")
    builder.add_edge("step1", "step2")
    builder.add_edge("step2", "step3")
    builder.set_entry_point("step1")

    # Use step-by-step execution hook to pause between nodes
    step_hook = StepByStepExecutionHook()
    builder.set_hook_providers([step_hook])

    return builder.build()
