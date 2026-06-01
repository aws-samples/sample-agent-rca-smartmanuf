"""Step 1 Agent: Problem Definition."""

import os

from strands import Agent
from strands_tools import retrieve

from prompts.sop_loader import load_step1_sop
from tools.kb_logging import KBQueryLoggingHook

MODEL_ID = os.environ.get("MODEL_ID", "eu.anthropic.claude-opus-4-6-v1")


def create_step1_agent() -> Agent:
    """Create the Step 1 agent for problem definition."""
    return Agent(
        model=MODEL_ID,
        tools=[retrieve],
        system_prompt=load_step1_sop(),
        name="step1_problem_definition",
        hooks=[KBQueryLoggingHook()],
        description=(
            "Defines the problem scope: identifies affected lots, "
            "establishes timeline, classifies lots as reference vs study."
        ),
    )
