"""Step 2 Agent: Root Cause Analysis."""

import os

from strands import Agent
from strands_tools import retrieve

from prompts.sop_loader import load_step2_sop
from tools.kb_logging import KBQueryLoggingHook

MODEL_ID = os.environ.get("MODEL_ID", "eu.anthropic.claude-opus-4-6-v1")


def create_step2_agent() -> Agent:
    """Create the Step 2 agent for root cause analysis."""
    return Agent(
        model=MODEL_ID,
        tools=[retrieve],
        system_prompt=load_step2_sop(),
        name="step2_root_cause_analysis",
        hooks=[KBQueryLoggingHook()],
        description=(
            "Identifies potential root causes by querying data sources "
            "and documenting evidence for each finding."
        ),
    )
