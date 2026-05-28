"""Step 3 Agent: Verification."""

import os

from strands import Agent
from strands_tools import retrieve

from prompts.sop_loader import load_step3_sop
from tools.kb_logging import KBQueryLoggingHook

MODEL_ID = os.environ.get("MODEL_ID", "eu.anthropic.claude-opus-4-6-v1")


def create_step3_agent() -> Agent:
    """Create the Step 3 agent for verification."""
    return Agent(
        model=MODEL_ID,
        tools=[retrieve],
        system_prompt=load_step3_sop(),
        name="step3_verification",
        hooks=[KBQueryLoggingHook()],
        description=(
            "Verifies each potential cause by comparing reference vs study "
            "lots, determining RETAINED or ELIMINATED verdict."
        ),
    )
