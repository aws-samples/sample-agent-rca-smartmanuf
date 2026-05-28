# Architecture Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the Manufacturing RCA Agent to use the AgentCore CLI for deployment, create Knowledge Bases via CDK, modernize the agent entrypoint to CLI conventions, replace the fragile graph workaround with Strands interrupts, and add evaluation support.

**Architecture:** The sample becomes two deployment units: (1) a CDK stack that provisions Bedrock Knowledge Bases (OpenSearch Serverless + Neptune Analytics) and ingests sample data, and (2) an AgentCore CLI project that deploys the agent container (arm64/Graviton, built remotely via CodeBuild) with evaluation configured. The agent keeps its step-by-step invocation model with GraphBuilder, but uses the `BeforeNodeCallEvent` interrupt mechanism instead of the `max_node_executions` hack.

**Tech Stack:** Python 3.12, Strands Agents 1.37, Bedrock AgentCore SDK, AgentCore CLI (npm `@aws/agentcore`), CDK (Python), uv, OpenSearch Serverless, Neptune Analytics

---

## File Structure

### Files to DELETE

- `stacks/__init__.py`
- `stacks/ecr_stack.py`
- `stacks/agent_runtime_stack.py`
- `app.py`
- `cdk.json`
- `scripts/build_and_push.sh`
- `scripts/deploy.sh`
- `agent/requirements.txt`
- `agent/requirements.lock`
- `requirements.txt`
- `requirements.lock`
- `pyproject.toml` (replaced by new one)
- `agent/Dockerfile` (replaced by new one)
- `agent/entrypoint.py` (replaced by `agent/main.py`)
- `tests/test_stacks.py`

### Files to CREATE

**Agent (modernized):**
- `agent/main.py` — new entrypoint (replaces `entrypoint.py`)
- `agent/pyproject.toml` — uv-managed dependencies
- `agent/Dockerfile` — new Dockerfile matching CLI conventions
- `agent/graph/interrupt_hook.py` — `BeforeNodeCallEvent` hook to pause between steps

**AgentCore CLI config:**
- `agentcore/agentcore.json` — agent definition, evaluators, online eval config
- `agentcore/aws-targets.json` — deployment target (account/region)
- `agentcore/cdk/package.json` — CDK TypeScript project deps
- `agentcore/cdk/tsconfig.json` — TypeScript config
- `agentcore/cdk/bin/cdk.ts` — CDK app entry point
- `agentcore/cdk/lib/cdk-stack.ts` — customized stack with KB permissions

**Knowledge Base CDK stack:**
- `infra/app.py` — CDK entry point for KB stack
- `infra/stacks/__init__.py`
- `infra/stacks/kb_stack.py` — OpenSearch Serverless collection + Bedrock KB (Hybrid)
- `infra/stacks/graphrag_stack.py` — Neptune Analytics graph + Bedrock KB (GraphRAG)
- `infra/stacks/data_ingestion_stack.py` — S3 bucket + data sync trigger
- `infra/cdk.json`
- `infra/pyproject.toml`

**Sample data:**
- `data/` — directory for synthetic manufacturing records (provided by user later)

**Tests:**
- `tests/test_interrupt_hook.py` — tests for the new interrupt mechanism
- `tests/test_main.py` — tests for the new entrypoint

**Docs:**
- `README.md` — rewritten for new workflow

### Files to MODIFY

- `agent/graph/investigation_graph.py` — remove `max_node_executions`, add interrupt hook
- `agent/agents/step1_agent.py` — update model ID default, no structural change
- `agent/agents/step2_agent.py` — same
- `agent/agents/step3_agent.py` — same
- `tests/test_state.py` — update imports if needed
- `tests/test_sop_loader.py` — update imports if needed

---

## Task 1: Clean up old deployment infrastructure

Remove the CDK stacks, build scripts, and deployment scripts that are being replaced.

**Files:**
- Delete: `stacks/__init__.py`, `stacks/ecr_stack.py`, `stacks/agent_runtime_stack.py`
- Delete: `app.py`, `cdk.json`
- Delete: `scripts/build_and_push.sh`, `scripts/deploy.sh`
- Delete: `requirements.txt`, `requirements.lock`
- Delete: `pyproject.toml`
- Delete: `agent/requirements.txt`, `agent/requirements.lock`
- Delete: `tests/test_stacks.py`

- [ ] **Step 1: Delete old CDK stacks and entry point**

```bash
rm -rf stacks/ app.py cdk.json
```

- [ ] **Step 2: Delete old build and deploy scripts**

```bash
rm scripts/build_and_push.sh scripts/deploy.sh
```

- [ ] **Step 3: Delete old dependency files**

```bash
rm requirements.txt requirements.lock pyproject.toml agent/requirements.txt agent/requirements.lock
```

- [ ] **Step 4: Delete stale test file**

```bash
rm tests/test_stacks.py
```

- [ ] **Step 5: Verify remaining structure is intact**

```bash
find . -type f | grep -v '.git/' | sort
```

Expected: `agent/` code, `agent/sops/`, `scripts/invoke_agent.py`, `tests/test_state.py`, `tests/test_sop_loader.py`, docs, and config files remain.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove old CDK stacks, build scripts, and dependency files

These are replaced by AgentCore CLI (deployment) and a separate KB CDK stack (infra)."
```

---

## Task 2: Modernize agent to CLI conventions (pyproject.toml + uv + Dockerfile)

Replace `requirements.txt` with `pyproject.toml` using `uv` for dependency management, and update the Dockerfile to match the AgentCore CLI scaffold pattern.

**Files:**
- Create: `agent/pyproject.toml`
- Create: `agent/Dockerfile` (rewrite)
- Create: `agent/.python-version`

- [ ] **Step 1: Create `agent/pyproject.toml`**

```toml
[project]
name = "manufacturing-rca-agent"
version = "0.1.0"
description = "AI-powered root cause analysis agent for manufacturing quality investigations"
requires-python = ">=3.12"
license = { text = "MIT-0" }

dependencies = [
    "strands-agents>=1.37,<2.0",
    "strands-agents-tools>=0.2,<1.0",
    "bedrock-agentcore>=1.0.3,<2.0",
    "boto3>=1.42,<2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create `agent/.python-version`**

```
3.12
```

- [ ] **Step 3: Generate lock file**

```bash
cd agent && uv lock
```

Expected: creates `uv.lock` file.

- [ ] **Step 4: Rewrite `agent/Dockerfile`**

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd -m -u 1000 bedrock_agentcore

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=bedrock_agentcore:bedrock_agentcore . .
RUN uv sync --frozen --no-dev

USER bedrock_agentcore

EXPOSE 8080

CMD ["python", "-m", "main"]
```

- [ ] **Step 5: Verify uv install works locally**

```bash
cd agent && uv sync --dev
```

Expected: installs all dependencies successfully.

- [ ] **Step 6: Run existing tests to confirm nothing broke**

```bash
cd agent && uv run pytest ../tests/ -v
```

Expected: `test_state.py` and `test_sop_loader.py` pass (test_stacks.py was deleted in Task 1).

- [ ] **Step 7: Commit**

```bash
git add agent/pyproject.toml agent/.python-version agent/uv.lock agent/Dockerfile
git commit -m "build: modernize agent to uv + pyproject.toml with CLI-convention Dockerfile

Replaces requirements.txt/pip with uv for dependency management.
Dockerfile matches AgentCore CLI scaffold pattern (uv, python3.12, non-root user)."
```

---

## Task 3: Rename entrypoint to `main.py` and add `context` parameter

Rename `entrypoint.py` to `main.py` to match CLI conventions. Add the optional `context` parameter to the handler signature.

**Files:**
- Delete: `agent/entrypoint.py`
- Create: `agent/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write test for the new entrypoint handler**

```python
"""Tests for the main entrypoint handler."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))


@pytest.mark.asyncio
async def test_handler_returns_valid_json_for_step1():
    """Handler should return a JSON string with expected fields."""
    mock_graph = MagicMock()
    mock_graph.invoke_async = AsyncMock(return_value=MagicMock(
        results={"step1": MagicMock(
            result=MagicMock(message={"content": [{"text": '{"product_id": "PROD-001"}'}]})
        )}
    ))
    mock_graph.serialize_state.return_value = {
        "type": "graph",
        "status": "interrupted",
        "completed_nodes": ["step1"],
        "next_nodes_to_execute": ["step2"],
        "node_results": {},
        "execution_order": ["step1"],
    }

    with patch("main._build_graph", return_value=mock_graph):
        from main import handler
        result = await handler(
            {"step": "step1", "prompt": "Investigate BATCH-001"},
            None,
        )

    data = json.loads(result)
    assert data["step"] == "step1"
    assert data["done"] is False
    assert data["next_step"] == "step2"
    assert "result" in data


@pytest.mark.asyncio
async def test_handler_rejects_invalid_step():
    """Handler should reject invalid step names."""
    from main import handler
    result = await handler({"step": "step99"}, None)
    data = json.loads(result)
    assert "error" in data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd agent && uv run pytest ../tests/test_main.py -v
```

Expected: FAIL — `main` module not found.

- [ ] **Step 3: Create `agent/main.py`**

This is the rewritten entrypoint. Key changes from `entrypoint.py`:
- Renamed to `main.py`
- Added optional `context` parameter to handler
- Removed the `max_node_executions` state patching workaround (will be replaced by interrupt hook in Task 4)
- Kept the same request/response JSON contract

```python
"""
AgentCore Runtime Entrypoint

Handles investigation requests via Bedrock AgentCore.
Executes the investigation graph one step per invocation using
graph interrupts for step-by-step pausing.

Protocol:
  Step 1: POST {"step": "step1", "prompt": "Investigate PROD-001..."}
  Step 2: POST {"step": "step2", "prompt": "...", "graph_state": {...}}
  Step 3: POST {"step": "step3", "prompt": "...", "graph_state": {...}}

Each response returns:
  {"step": "stepN", "done": bool, "result": "...", "graph_state": {...} | null}
"""

import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("investigation-agent")

app = BedrockAgentCoreApp()

VALID_STEPS = {"step1", "step2", "step3"}

REQUIRED_STATE_KEYS = {"type", "status", "completed_nodes", "next_nodes_to_execute", "node_results"}


def _build_graph():
    """Build a fresh investigation graph."""
    from graph.investigation_graph import create_investigation_graph
    return create_investigation_graph()


def _build_prompt(payload: dict) -> str:
    """Build the investigation prompt from payload fields."""
    reference = payload.get("reference", "")
    problem = payload.get("problem", "")
    symptom = payload.get("symptom", "")
    date_reported = payload.get("date_reported", "")

    if reference and problem:
        return (
            f"Investigate product reference {reference}.\n"
            f"Problem: {problem}\n"
            f"Symptom: {symptom}\n"
            f"Date reported: {date_reported}"
        )
    return payload.get("prompt", str(payload))


def _error_response(step: str, error: Exception, graph_state=None) -> str:
    """Build a structured error response."""
    is_retryable = "throttl" in str(error).lower() or "timeout" in str(error).lower()
    return json.dumps({
        "step": step,
        "done": False,
        "error": str(error),
        "error_type": type(error).__name__,
        "retryable": is_retryable,
        "graph_state": graph_state,
    }, default=str)


@app.entrypoint
async def handler(payload, context=None) -> str:
    """Handle an investigation request — one graph step per invocation."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {"prompt": payload}

    if not isinstance(payload, dict):
        payload = {"prompt": str(payload)}

    step = payload.get("step", "step1")
    graph_state = payload.get("graph_state")
    prompt = payload.get("prompt") or _build_prompt(payload)

    if step not in VALID_STEPS:
        return json.dumps({"error": f"Invalid step: {step}. Must be one of {sorted(VALID_STEPS)}"})

    if graph_state is not None:
        if not isinstance(graph_state, dict):
            return json.dumps({"error": "graph_state must be a JSON object"})
        missing = REQUIRED_STATE_KEYS - set(graph_state.keys())
        if missing:
            return json.dumps({"error": f"graph_state missing required keys: {sorted(missing)}"})

    logger.info("Step=%s, has_graph_state=%s, prompt=%s", step, bool(graph_state), prompt[:150])

    try:
        graph = _build_graph()

        if graph_state:
            logger.info("Deserializing graph state (completed=%s, next=%s)",
                        graph_state.get("completed_nodes"), graph_state.get("next_nodes_to_execute"))
            try:
                graph.deserialize_state(graph_state)
            except Exception as e:
                logger.exception("Failed to deserialize graph state")
                return _error_response(step, ValueError(f"Invalid graph_state: {e}"))

        result = await graph.invoke_async(prompt)

    except Exception as e:
        logger.exception("Step=%s execution failed", step)
        return _error_response(step, e, graph_state)

    serialized = graph.serialize_state()
    next_nodes = serialized.get("next_nodes_to_execute", [])
    is_done = len(next_nodes) == 0

    step_result = result.results.get(step)
    if step_result and hasattr(step_result, "result") and hasattr(step_result.result, "message"):
        content = step_result.result.message.get("content", [])
        result_text = "\n".join(
            block.get("text", "") for block in content if isinstance(block, dict) and "text" in block
        )
    else:
        result_text = str(step_result) if step_result else ""

    needs_input = False
    if result_text:
        try:
            json.loads(result_text)
        except (json.JSONDecodeError, ValueError):
            needs_input = "?" in result_text

    logger.info("Step=%s complete, done=%s, next=%s, needs_input=%s, result_len=%d",
                step, is_done, next_nodes, needs_input, len(result_text))

    return json.dumps({
        "step": step,
        "done": is_done,
        "needs_input": needs_input,
        "next_step": next_nodes[0] if next_nodes else None,
        "result": result_text,
        "graph_state": None if is_done else serialized,
    }, default=str)


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 4: Delete old entrypoint**

```bash
rm agent/entrypoint.py
```

- [ ] **Step 5: Run tests**

```bash
cd agent && uv run pytest ../tests/test_main.py -v
```

Expected: both tests pass.

- [ ] **Step 6: Run all tests**

```bash
cd agent && uv run pytest ../tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add agent/main.py tests/test_main.py
git rm agent/entrypoint.py
git commit -m "refactor: rename entrypoint.py to main.py, add context parameter

Matches AgentCore CLI scaffold conventions. Removes max_node_executions
state patching workaround (interrupt hook added in next commit)."
```

---

## Task 4: Replace graph workaround with BeforeNodeCallEvent interrupt hook

Implement the interrupt-based step-by-step mechanism using Strands 1.37's `BeforeNodeCallEvent`. This cleanly pauses the graph after each node with `INTERRUPTED` status instead of hacking `FAILED` to `PENDING`.

**Files:**
- Create: `agent/graph/interrupt_hook.py`
- Modify: `agent/graph/investigation_graph.py`
- Create: `tests/test_interrupt_hook.py`

- [ ] **Step 1: Write test for the interrupt hook**

```python
"""Tests for the graph interrupt hook."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from graph.interrupt_hook import StepByStepHook


class TestStepByStepHook:
    def test_hook_allows_first_node(self):
        """The hook should allow the first node to execute."""
        hook = StepByStepHook()
        event = MagicMock()
        event.node_id = "step1"
        # First call should not raise
        hook.before_node_call(event)

    def test_hook_interrupts_second_node(self):
        """The hook should interrupt on the second node call."""
        hook = StepByStepHook()
        event1 = MagicMock()
        event1.node_id = "step1"
        hook.after_node_call(event1)

        event2 = MagicMock()
        event2.node_id = "step2"
        from strands.multiagent.graph import Interrupt
        with pytest.raises(Interrupt):
            hook.before_node_call(event2)

    def test_hook_resets_after_interrupt(self):
        """After deserialization/resume, the hook should allow next node."""
        hook = StepByStepHook()
        hook.reset()
        event = MagicMock()
        event.node_id = "step2"
        # After reset, should allow next node
        hook.before_node_call(event)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd agent && uv run pytest ../tests/test_interrupt_hook.py -v
```

Expected: FAIL — `graph.interrupt_hook` module not found.

- [ ] **Step 3: Create `agent/graph/interrupt_hook.py`**

```python
"""
Step-by-step interrupt hook for graph execution.

Uses Strands' BeforeNodeCallEvent to pause the graph after each node
completes. This replaces the fragile max_node_executions workaround.
"""

from strands.multiagent.graph import HookProvider, BeforeNodeCallEvent, AfterNodeCallEvent, Interrupt


class StepByStepHook(HookProvider):
    """Interrupts graph execution after each node, enabling step-by-step invocation."""

    def __init__(self):
        self._nodes_completed = 0

    def before_node_call(self, event: BeforeNodeCallEvent):
        if self._nodes_completed > 0:
            raise Interrupt("Step complete — pausing for next invocation")

    def after_node_call(self, event: AfterNodeCallEvent):
        self._nodes_completed += 1

    def reset(self):
        """Reset counter for resumption after deserialization."""
        self._nodes_completed = 0
```

- [ ] **Step 4: Run interrupt hook tests**

```bash
cd agent && uv run pytest ../tests/test_interrupt_hook.py -v
```

Expected: all 3 tests pass. If `Interrupt` import path differs, adjust based on actual Strands 1.37 API (check `from strands.multiagent.graph import Interrupt` or `from strands.multiagent.graph.types import Interrupt`).

- [ ] **Step 5: Update `agent/graph/investigation_graph.py`**

Replace the `max_node_executions` approach with the interrupt hook:

```python
"""
Investigation Graph Orchestration

Coordinates the execution of Step 1 → Step 2 → Step 3 agents using
Strands multi-agent GraphBuilder with interrupt-based step-by-step pausing.
"""

import os
import logging

from strands.multiagent.graph import GraphBuilder

from agents.step1_agent import create_step1_agent
from agents.step2_agent import create_step2_agent
from agents.step3_agent import create_step3_agent
from graph.interrupt_hook import StepByStepHook

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
    Build the 3-step investigation graph with interrupt-based step-by-step pausing.

    The StepByStepHook raises an Interrupt after each node completes,
    allowing the caller to serialize state and resume on next invocation.
    """
    kb_context = _build_kb_context()

    step1 = create_step1_agent()
    step2 = create_step2_agent()
    step3 = create_step3_agent()

    for agent in (step1, step2, step3):
        agent.system_prompt = agent.system_prompt + kb_context

    hook = StepByStepHook()

    builder = GraphBuilder()
    builder.add_node(step1, "step1")
    builder.add_node(step2, "step2")
    builder.add_node(step3, "step3")
    builder.add_edge("step1", "step2")
    builder.add_edge("step2", "step3")
    builder.set_entry_point("step1")
    builder.add_hook(hook)

    return builder.build()
```

- [ ] **Step 6: Update `agent/main.py` — remove workaround comments and state patching**

In `agent/main.py`, the handler already doesn't have the workaround (we wrote it clean in Task 3). Verify the serialized state handling works with `INTERRUPTED` status. The graph now serializes with `status: "interrupted"` which is correct — no patching needed.

- [ ] **Step 7: Run all tests**

```bash
cd agent && uv run pytest ../tests/ -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add agent/graph/interrupt_hook.py agent/graph/investigation_graph.py tests/test_interrupt_hook.py
git commit -m "feat: replace max_node_executions hack with BeforeNodeCallEvent interrupts

The graph now cleanly pauses between nodes with INTERRUPTED status.
No more patching serialized state or pinning to a stale Strands version."
```

---

## Task 5: Set up AgentCore CLI project configuration

Create the `agentcore/` directory with the configuration files that the AgentCore CLI expects.

**Files:**
- Create: `agentcore/agentcore.json`
- Create: `agentcore/aws-targets.json`

- [ ] **Step 1: Create `agentcore/agentcore.json`**

```json
{
  "name": "manufacturing-rca",
  "version": 1,
  "runtimes": [
    {
      "name": "RCAAgent",
      "description": "AI-powered root cause analysis agent for manufacturing quality investigations",
      "codeLocation": "../agent",
      "entrypoint": "main.py",
      "build": "Container",
      "framework": "strands",
      "environmentVariables": {
        "KB_HYBRID_ID": "",
        "KB_GRAPHRAG_ID": "",
        "RETRIEVAL_MODE": "both",
        "MODEL_ID": "us.anthropic.claude-sonnet-4-6",
        "USE_SOP": "true",
        "LOG_LEVEL": "INFO"
      }
    }
  ],
  "evaluators": [
    {
      "name": "KBUsageCheck",
      "level": "TOOL_CALL",
      "config": {
        "llmAsAJudge": {
          "model": "us.anthropic.claude-sonnet-4-5-20250514-v1:0",
          "instructions": "Evaluate whether the agent correctly selected and used the retrieve tool to query the knowledge base. The agent should use BOTH the Hybrid KB and GraphRAG KB during a complete investigation. Context: {context}. Tool turn: {tool_turn}",
          "ratingScale": {
            "categorical": [
              {"label": "Pass", "definition": "Tool was correctly selected and used with appropriate knowledge_base_id"},
              {"label": "Fail", "definition": "Tool was not used when it should have been, or wrong knowledge_base_id"}
            ]
          }
        }
      }
    }
  ],
  "onlineEvalConfigs": [
    {
      "name": "RCAMonitor",
      "agent": "RCAAgent",
      "evaluators": ["KBUsageCheck", "Builtin.ToolSelectionAccuracy"],
      "samplingRate": 100,
      "enableOnCreate": true
    }
  ]
}
```

- [ ] **Step 2: Create `agentcore/aws-targets.json`**

```json
[
  {
    "name": "default",
    "account": "",
    "region": "us-east-1"
  }
]
```

- [ ] **Step 3: Verify CLI recognizes the project**

```bash
cd agentcore && agentcore status
```

Expected: CLI recognizes the project structure and shows agent info (or prompts for missing account/region).

- [ ] **Step 4: Commit**

```bash
git add agentcore/
git commit -m "feat: add AgentCore CLI project configuration

Defines RCAAgent runtime with container build, KB usage evaluator,
and online evaluation at 100% sampling."
```

---

## Task 6: Customize AgentCore CLI's CDK stack for KB permissions

The CLI generates a CDK project under `agentcore/cdk/`. Customize it to add `bedrock:Retrieve` permissions for the agent's Knowledge Bases.

**Files:**
- Create: `agentcore/cdk/package.json`
- Create: `agentcore/cdk/tsconfig.json`
- Create: `agentcore/cdk/bin/cdk.ts`
- Create: `agentcore/cdk/lib/cdk-stack.ts`

- [ ] **Step 1: Generate the CDK scaffold via CLI**

```bash
cd agentcore && agentcore deploy --dry-run
```

This should generate the `cdk/` directory. If the CLI doesn't have `--dry-run`, run `agentcore deploy` and cancel before actual deployment, or manually scaffold based on the CLI's template.

- [ ] **Step 2: Customize `agentcore/cdk/lib/cdk-stack.ts`**

Add the KB permission policy after the `AgentCoreApplication` construct. The exact path to the runtime role depends on what the CLI generates. The pattern is:

```typescript
import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { AgentCoreApplication } from '@aws/agentcore-cdk';

export class AgentCoreStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const app = new AgentCoreApplication(this, 'RCAApp', {
      // ... CLI-generated config
    });

    // Add KB retrieval permissions to the agent's execution role
    const kbHybridId = new cdk.CfnParameter(this, 'KbHybridId', {
      type: 'String',
      description: 'Bedrock Knowledge Base ID (Hybrid search)',
    });

    const kbGraphragId = new cdk.CfnParameter(this, 'KbGraphragId', {
      type: 'String',
      description: 'Bedrock Knowledge Base ID (GraphRAG)',
    });

    app.runtimes.get('RCAAgent')!.role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'RetrieveFromKB',
        actions: ['bedrock:Retrieve', 'bedrock:RetrieveAndGenerate'],
        resources: [
          `arn:aws:bedrock:${this.region}:${this.account}:knowledge-base/${kbHybridId.valueAsString}`,
          `arn:aws:bedrock:${this.region}:${this.account}:knowledge-base/${kbGraphragId.valueAsString}`,
        ],
      })
    );
  }
}
```

Note: The exact API (`app.runtimes.get(...)`, `app.environments.get(...)`) depends on what `@aws/agentcore-cdk` exposes. Verify by checking the generated CDK construct's type definitions after step 1.

- [ ] **Step 3: Install CDK dependencies**

```bash
cd agentcore/cdk && npm install
```

- [ ] **Step 4: Verify CDK synth succeeds**

```bash
cd agentcore/cdk && npx cdk synth --no-lookups
```

Expected: synthesizes CloudFormation template without errors.

- [ ] **Step 5: Commit**

```bash
git add agentcore/cdk/
git commit -m "feat: customize AgentCore CDK stack with KB retrieval permissions

Adds bedrock:Retrieve and bedrock:RetrieveAndGenerate on the Hybrid
and GraphRAG Knowledge Base ARNs to the agent execution role."
```

---

## Task 7: Create Knowledge Base CDK stack (OpenSearch Serverless + Hybrid KB)

Create the CDK infrastructure that provisions an OpenSearch Serverless collection and a Bedrock Knowledge Base with hybrid search.

**Files:**
- Create: `infra/app.py`
- Create: `infra/cdk.json`
- Create: `infra/pyproject.toml`
- Create: `infra/stacks/__init__.py`
- Create: `infra/stacks/kb_stack.py`

- [ ] **Step 1: Create `infra/pyproject.toml`**

```toml
[project]
name = "rca-kb-infra"
version = "0.1.0"
description = "CDK infrastructure for Bedrock Knowledge Bases (Hybrid + GraphRAG)"
requires-python = ">=3.11"
license = { text = "MIT-0" }

dependencies = [
    "aws-cdk-lib>=2.170.0",
    "constructs>=10.0.0,<11.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create `infra/cdk.json`**

```json
{
  "app": "python3 app.py",
  "context": {
    "@aws-cdk/core:bootstrapQualifier": "hnb659fds"
  }
}
```

- [ ] **Step 3: Create `infra/stacks/__init__.py`**

```python
from .kb_stack import HybridKbStack
from .graphrag_stack import GraphRagKbStack
from .data_ingestion_stack import DataIngestionStack
```

- [ ] **Step 4: Create `infra/stacks/kb_stack.py`**

```python
"""CDK Stack: OpenSearch Serverless collection + Bedrock Knowledge Base (Hybrid search)."""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    CustomResource,
    Duration,
    aws_opensearchserverless as aoss,
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct


class HybridKbStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket for KB data source
        self.data_bucket = s3.Bucket(
            self,
            "KbDataBucket",
            bucket_name=f"rca-kb-data-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            enforce_ssl=True,
        )

        # OpenSearch Serverless encryption policy
        encryption_policy = aoss.CfnSecurityPolicy(
            self,
            "EncryptionPolicy",
            name="rca-hybrid-enc",
            type="encryption",
            policy=cdk.Fn.sub(
                '{"Rules":[{"ResourceType":"collection","Resource":["collection/rca-hybrid"]}],"AWSOwnedKey":true}'
            ),
        )

        # Network policy (public access for simplicity in sample)
        network_policy = aoss.CfnSecurityPolicy(
            self,
            "NetworkPolicy",
            name="rca-hybrid-net",
            type="network",
            policy='[{"Rules":[{"ResourceType":"collection","Resource":["collection/rca-hybrid"]},{"ResourceType":"dashboard","Resource":["collection/rca-hybrid"]}],"AllowFromPublic":true}]',
        )

        # OpenSearch Serverless collection
        self.collection = aoss.CfnCollection(
            self,
            "HybridCollection",
            name="rca-hybrid",
            type="SEARCH",
            description="Manufacturing RCA data for hybrid search",
        )
        self.collection.add_dependency(encryption_policy)
        self.collection.add_dependency(network_policy)

        # Data access policy — grants Bedrock KB service access
        data_access_policy = aoss.CfnAccessPolicy(
            self,
            "DataAccessPolicy",
            name="rca-hybrid-access",
            type="data",
            policy=cdk.Fn.sub(
                '[{"Rules":[{"ResourceType":"index","Resource":["index/rca-hybrid/*"],"Permission":["aoss:CreateIndex","aoss:UpdateIndex","aoss:DescribeIndex","aoss:ReadDocument","aoss:WriteDocument"]},'
                '{"ResourceType":"collection","Resource":["collection/rca-hybrid"],"Permission":["aoss:CreateCollectionItems","aoss:DescribeCollectionItems","aoss:UpdateCollectionItems"]}],'
                '"Principal":["arn:aws:iam::${AWS::AccountId}:root"]}]'
            ),
        )
        data_access_policy.add_dependency(self.collection)

        # Bedrock Knowledge Base
        kb_role = iam.Role(
            self,
            "KbRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
        )
        kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=[self.collection.attr_arn],
            )
        )
        self.data_bucket.grant_read(kb_role)

        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "HybridKB",
            name="rca-hybrid-kb",
            role_arn=kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0",
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=self.collection.attr_arn,
                    vector_index_name="rca-hybrid-index",
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        vector_field="embedding",
                        text_field="text",
                        metadata_field="metadata",
                    ),
                ),
            ),
        )
        self.knowledge_base.node.add_dependency(data_access_policy)

        # Data source pointing at S3
        bedrock.CfnDataSource(
            self,
            "HybridDataSource",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            name="rca-s3-source",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=self.data_bucket.bucket_arn,
                ),
            ),
        )

        CfnOutput(self, "HybridKbId", value=self.knowledge_base.attr_knowledge_base_id)
        CfnOutput(self, "DataBucketName", value=self.data_bucket.bucket_name)
        CfnOutput(self, "CollectionEndpoint", value=self.collection.attr_collection_endpoint)
```

- [ ] **Step 5: Run CDK synth to verify**

```bash
cd infra && pip install -e . && cdk synth RcaHybridKbStack --no-lookups
```

Expected: synthesizes successfully. There may be warnings about the AOSS data access policy — this is where the propagation issue will surface. If CDK complains about dependencies, add explicit `node.add_dependency()` calls.

- [ ] **Step 6: Commit**

```bash
git add infra/
git commit -m "feat: add CDK stack for Hybrid Knowledge Base (OpenSearch Serverless)

Creates AOSS collection, encryption/network/data-access policies,
Bedrock KB with S3 data source, and supporting IAM role."
```

---

## Task 8: Create GraphRAG Knowledge Base CDK stack (Neptune Analytics)

Create the CDK stack for the Neptune Analytics-backed GraphRAG Knowledge Base.

**Files:**
- Create: `infra/stacks/graphrag_stack.py`

- [ ] **Step 1: Create `infra/stacks/graphrag_stack.py`**

```python
"""CDK Stack: Neptune Analytics graph + Bedrock Knowledge Base (GraphRAG)."""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_neptunegraph as neptune,
    aws_s3 as s3,
)
from constructs import Construct


class GraphRagKbStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        data_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Neptune Analytics graph
        self.graph = neptune.CfnGraph(
            self,
            "RcaGraph",
            graph_name="rca-graphrag",
            provisioned_memory=128,
            deletion_protection=False,
            public_connectivity=True,
            vector_search_configuration=neptune.CfnGraph.VectorSearchConfigurationProperty(
                vector_search_dimension=1024,
            ),
        )

        # IAM role for Bedrock KB to access Neptune
        kb_role = iam.Role(
            self,
            "GraphRagKbRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
        )
        kb_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "neptune-graph:GetGraph",
                    "neptune-graph:ReadDataViaQuery",
                    "neptune-graph:WriteDataViaQuery",
                    "neptune-graph:DeleteDataViaQuery",
                ],
                resources=[self.graph.attr_graph_arn],
            )
        )
        data_bucket.grant_read(kb_role)

        # Bedrock Knowledge Base (GraphRAG)
        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "GraphRagKB",
            name="rca-graphrag-kb",
            role_arn=kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0",
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="NEPTUNE_ANALYTICS",
                neptune_analytics_configuration=bedrock.CfnKnowledgeBase.NeptuneAnalyticsConfigurationProperty(
                    graph_arn=self.graph.attr_graph_arn,
                    vector_index_name="rca-graphrag-index",
                    field_mapping=bedrock.CfnKnowledgeBase.NeptuneAnalyticsFieldMappingProperty(
                        text_field="text",
                        metadata_field="metadata",
                    ),
                ),
            ),
        )

        # Data source pointing at same S3 bucket
        bedrock.CfnDataSource(
            self,
            "GraphRagDataSource",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            name="rca-graphrag-s3-source",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=data_bucket.bucket_arn,
                ),
            ),
        )

        CfnOutput(self, "GraphRagKbId", value=self.knowledge_base.attr_knowledge_base_id)
        CfnOutput(self, "NeptuneGraphId", value=self.graph.attr_graph_id)
```

- [ ] **Step 2: Verify CDK synth**

```bash
cd infra && cdk synth --no-lookups
```

Expected: both stacks synthesize without errors.

- [ ] **Step 3: Commit**

```bash
git add infra/stacks/graphrag_stack.py
git commit -m "feat: add CDK stack for GraphRAG Knowledge Base (Neptune Analytics)

Creates Neptune Analytics graph, Bedrock KB with Neptune storage,
and S3 data source pointing at the shared data bucket."
```

---

## Task 9: Create data ingestion stack

Create a stack that uploads sample data to S3 and triggers KB sync.

**Files:**
- Create: `infra/stacks/data_ingestion_stack.py`
- Modify: `infra/app.py`

- [ ] **Step 1: Create `infra/stacks/data_ingestion_stack.py`**

```python
"""CDK Stack: Upload sample data to S3 and trigger KB sync."""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    CfnOutput,
    aws_s3_deployment as s3deploy,
    aws_s3 as s3,
    aws_iam as iam,
    custom_resources as cr,
)
from constructs import Construct


class DataIngestionStack(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        data_bucket: s3.IBucket,
        hybrid_kb_id: str,
        hybrid_data_source_id: str,
        graphrag_kb_id: str,
        graphrag_data_source_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Upload sample data to S3
        s3deploy.BucketDeployment(
            self,
            "UploadSampleData",
            sources=[s3deploy.Source.asset("../data")],
            destination_bucket=data_bucket,
            destination_key_prefix="manufacturing-records/",
        )

        # Trigger KB sync for Hybrid KB
        sync_hybrid = cr.AwsCustomResource(
            self,
            "SyncHybridKb",
            on_create=cr.AwsSdkCall(
                service="BedrockAgent",
                action="startIngestionJob",
                parameters={
                    "knowledgeBaseId": hybrid_kb_id,
                    "dataSourceId": hybrid_data_source_id,
                },
                physical_resource_id=cr.PhysicalResourceId.of("sync-hybrid-kb"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["bedrock:StartIngestionJob"],
                    resources=["*"],
                ),
            ]),
        )

        # Trigger KB sync for GraphRAG KB
        sync_graphrag = cr.AwsCustomResource(
            self,
            "SyncGraphRagKb",
            on_create=cr.AwsSdkCall(
                service="BedrockAgent",
                action="startIngestionJob",
                parameters={
                    "knowledgeBaseId": graphrag_kb_id,
                    "dataSourceId": graphrag_data_source_id,
                },
                physical_resource_id=cr.PhysicalResourceId.of("sync-graphrag-kb"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["bedrock:StartIngestionJob"],
                    resources=["*"],
                ),
            ]),
        )

        CfnOutput(self, "DataUploaded", value="true")
```

- [ ] **Step 2: Create `infra/app.py`**

```python
#!/usr/bin/env python3
"""CDK app entry point for Knowledge Base infrastructure.

Deploy with:
    cd infra && cdk deploy --all
"""

import aws_cdk as cdk
from stacks.kb_stack import HybridKbStack
from stacks.graphrag_stack import GraphRagKbStack
from stacks.data_ingestion_stack import DataIngestionStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or None,
)

hybrid_stack = HybridKbStack(app, "RcaHybridKbStack", env=env)

graphrag_stack = GraphRagKbStack(
    app,
    "RcaGraphRagKbStack",
    data_bucket=hybrid_stack.data_bucket,
    env=env,
)

# Data ingestion depends on both KB stacks being deployed.
# KB IDs and data source IDs come from stack outputs.
# NOTE: This stack should be deployed after KBs are created.
# For first-time deployment, run:
#   cdk deploy RcaHybridKbStack RcaGraphRagKbStack
#   cdk deploy RcaDataIngestionStack

app.synth()
```

Note: The `DataIngestionStack` requires KB IDs from the other stacks' outputs. This creates a deployment ordering constraint — document this in the README as a two-step deploy (`cdk deploy RcaHybridKbStack RcaGraphRagKbStack` first, then `cdk deploy RcaDataIngestionStack`). Alternatively, use `CfnOutput` + cross-stack references, which CDK handles via exports.

- [ ] **Step 3: Verify CDK synth**

```bash
cd infra && cdk synth --no-lookups
```

Expected: all three stacks synthesize. The `DataIngestionStack` may need adjustment since it depends on runtime values from the other stacks — use CDK cross-stack references.

- [ ] **Step 4: Commit**

```bash
git add infra/
git commit -m "feat: add data ingestion stack with S3 upload and KB sync triggers

Uploads sample data from data/ directory to S3, then triggers
Bedrock ingestion jobs for both Hybrid and GraphRAG Knowledge Bases."
```

---

## Task 10: Add KB query logging

Log which `knowledge_base_id` is queried on each `retrieve` call so users can verify both KBs are being used.

**Files:**
- Create: `agent/tools/__init__.py`
- Create: `agent/tools/logged_retrieve.py`
- Modify: `agent/agents/step1_agent.py`
- Modify: `agent/agents/step2_agent.py`
- Modify: `agent/agents/step3_agent.py`

- [ ] **Step 1: Create `agent/tools/__init__.py`**

```python
from .logged_retrieve import logged_retrieve
```

- [ ] **Step 2: Create `agent/tools/logged_retrieve.py`**

This wraps the `retrieve` tool with logging of which KB was queried:

```python
"""Wrapper around strands_tools.retrieve that logs KB usage."""

import logging
from functools import wraps

from strands_tools import retrieve

logger = logging.getLogger("investigation-agent.kb")


def logged_retrieve(knowledge_base_id: str, query: str, **kwargs):
    """Retrieve from a Bedrock Knowledge Base with logging."""
    logger.info("KB_QUERY knowledge_base_id=%s query=%s", knowledge_base_id, query[:100])
    result = retrieve(knowledge_base_id=knowledge_base_id, query=query, **kwargs)
    logger.info("KB_RESULT knowledge_base_id=%s results_count=%d", knowledge_base_id, len(result) if result else 0)
    return result
```

Note: The exact implementation depends on how `strands_tools.retrieve` works as a tool (it may be a decorated function or a class). If `retrieve` is a Strands tool object that can't be directly wrapped, instead add logging in the agent's system prompt instructing it to log, or use Strands' tool hooks. Verify the `retrieve` tool's interface and adjust accordingly.

- [ ] **Step 3: Update agent imports to use logged_retrieve**

In `agent/agents/step1_agent.py`, `step2_agent.py`, and `step3_agent.py`, replace:

```python
from strands_tools import retrieve
```

with:

```python
from tools.logged_retrieve import logged_retrieve as retrieve
```

Note: If `retrieve` is a Strands tool object that must be passed as-is to `Agent(tools=[...])`, this wrapping approach may not work. In that case, use Strands' hook system to intercept tool calls and log them. Check the Strands tools API before implementing.

- [ ] **Step 4: Run tests**

```bash
cd agent && uv run pytest ../tests/ -v
```

Expected: all tests pass. The SOP loader tests don't invoke the retrieve tool, so the import change shouldn't break anything.

- [ ] **Step 5: Commit**

```bash
git add agent/tools/ agent/agents/step1_agent.py agent/agents/step2_agent.py agent/agents/step3_agent.py
git commit -m "feat: add KB query logging to verify both KBs are used

Wraps retrieve tool with logging of knowledge_base_id on every call.
Helps verify GraphRAG KB is actually being queried during investigations."
```

---

## Task 11: Update invoke script for new AgentCore CLI

Update `scripts/invoke_agent.py` to work with the new AgentCore CLI's invoke mechanism.

**Files:**
- Modify: `scripts/invoke_agent.py`

- [ ] **Step 1: Check how `agentcore invoke` works**

```bash
agentcore invoke --help
```

Determine the invocation pattern — does it use the same `bedrock-agentcore` boto3 client, or a different API? The CLI likely still calls the same AgentCore runtime API under the hood.

- [ ] **Step 2: Update the client setup in `invoke_agent.py`**

The existing script uses `boto3.client("bedrock-agentcore")`. This should still work — the AgentCore runtime API is the same regardless of how the agent was deployed. The only change needed is:
- Remove `--agent-arn` as required arg — fetch it from `agentcore status` or stack outputs
- Add option to get the ARN automatically from the CLI's deployed state

Update the argument parsing:

```python
parser.add_argument("--agent-arn", required=False,
                    help="AgentCore runtime ARN. If not provided, fetched from agentcore CLI state.")
```

Add helper to fetch ARN:

```python
import subprocess

def get_agent_arn_from_cli() -> str:
    """Fetch the agent ARN from agentcore CLI deployed state."""
    result = subprocess.run(
        ["agentcore", "status", "--json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError("Failed to get agent ARN from agentcore CLI. Pass --agent-arn explicitly.")
    import json
    state = json.loads(result.stdout)
    # Extract ARN from status output — structure depends on CLI version
    runtimes = state.get("runtimes", [])
    if runtimes:
        return runtimes[0].get("arn", "")
    raise RuntimeError("No deployed runtimes found. Run 'agentcore deploy' first.")
```

- [ ] **Step 3: Test the script still works with explicit ARN**

```bash
python scripts/invoke_agent.py --agent-arn <test-arn> --region us-east-1
```

Expected: script starts, shows welcome banner, prompts for input.

- [ ] **Step 4: Commit**

```bash
git add scripts/invoke_agent.py
git commit -m "feat: update invoke script to auto-detect agent ARN from CLI state

Falls back to --agent-arn flag if agentcore CLI state is unavailable."
```

---

## Task 12: Create sample data placeholder and README

Set up the `data/` directory structure and rewrite the README for the new workflow.

**Files:**
- Create: `data/.gitkeep`
- Rewrite: `README.md`

- [ ] **Step 1: Create data directory placeholder**

```bash
mkdir -p data
touch data/.gitkeep
```

The actual synthetic data will be added later when the user provides it.

- [ ] **Step 2: Rewrite `README.md`**

```markdown
# Manufacturing RCA Agent

An AI-powered root cause analysis agent for manufacturing quality investigations. Built on AWS Bedrock AgentCore with the Strands Agents framework.

## Architecture

![Architecture Diagram](architecture.png)

## How It Works

The agent runs a 3-step investigation pipeline:

```
Incident → Step 1: Problem Definition → Step 2: Root Cause Analysis → Step 3: Verification → Root Causes
```

1. **Problem Definition** — Identifies affected items, establishes timeline, classifies items as reference (known good) vs study (potentially affected)
2. **Root Cause Analysis** — Queries data sources to identify potential causes with supporting evidence
3. **Verification** — Verifies each cause by comparing reference vs study items, determining RETAINED or ELIMINATED verdict

The methodology is defined in SOP files (`agent/sops/`) that you can customize for your domain.

## Prerequisites

- AWS account with Bedrock model access enabled (Claude Sonnet, Titan Embeddings)
- AWS CLI configured with valid credentials
- CDK bootstrapped (`cdk bootstrap aws://ACCOUNT_ID/REGION`)
- [AgentCore CLI](https://github.com/aws/agentcore-cli) installed (`npm install -g @aws/agentcore`)
- Node.js 20+ (for AgentCore CLI and CDK)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Quick Start

### 1. Deploy Knowledge Bases

```bash
cd infra
uv sync
cdk deploy RcaHybridKbStack RcaGraphRagKbStack
```

Note the KB IDs from the stack outputs.

### 2. Upload sample data and trigger ingestion

```bash
cdk deploy RcaDataIngestionStack
```

### 3. Configure and deploy the agent

Edit `agentcore/agentcore.json` — set `KB_HYBRID_ID` and `KB_GRAPHRAG_ID` environment variables to the IDs from step 1.

Edit `agentcore/aws-targets.json` — set your account and region.

```bash
agentcore deploy
```

### 4. Test the agent

```bash
agentcore invoke '{"step": "step1", "prompt": "Investigate defect in batch BATCH-001"}'
```

Or use the interactive CLI:

```bash
python scripts/invoke_agent.py
```

## Local Development

```bash
cd agent
uv sync --dev
agentcore dev
```

## Customization

### SOPs (Standard Operating Procedures)

The investigation methodology is defined in `agent/sops/*.sop.md` files. To customize:

1. Edit the SOP files to match your investigation methodology
2. Update data source references to match your systems
3. Modify constraints (MUST/SHOULD/MAY) as needed

### State Schema

`agent/state/investigation_state.py` defines the data structures used during investigation. Customize:

- `CauseCategory` enum — match your RCA framework
- `AffectedItem` fields — add domain-specific attributes

### Graph Orchestration

The pipeline is defined in `agent/graph/investigation_graph.py` using Strands `GraphBuilder`. You can:

- Add/remove steps
- Add conditional edges (e.g., skip verification if no causes found)
- Add parallel steps

## Evaluation

The agent includes online evaluation via AgentCore's built-in evaluator support:

- **ToolSelectionAccuracy** — verifies the agent uses the correct tools
- **KBUsageCheck** — verifies both Knowledge Bases (Hybrid + GraphRAG) are queried

View evaluation results:

```bash
agentcore logs evals
```

## Project Structure

```
.
├── agent/                      # Agent application code
│   ├── main.py                 # AgentCore runtime entrypoint
│   ├── Dockerfile              # Container build (arm64/Graviton)
│   ├── pyproject.toml          # Python dependencies (uv)
│   ├── agents/                 # Step agents (1, 2, 3)
│   ├── graph/                  # Pipeline orchestration + interrupt hook
│   ├── prompts/                # SOP loader
│   ├── sops/                   # Investigation methodology (customize these)
│   ├── state/                  # Data structures
│   └── tools/                  # Tool wrappers (KB logging)
├── agentcore/                  # AgentCore CLI configuration
│   ├── agentcore.json          # Agent definition + evaluators
│   ├── aws-targets.json        # Deployment targets
│   └── cdk/                    # Customized CDK stack (KB permissions)
├── infra/                      # Knowledge Base infrastructure (CDK)
│   ├── stacks/kb_stack.py      # Hybrid KB (OpenSearch Serverless)
│   ├── stacks/graphrag_stack.py # GraphRAG KB (Neptune Analytics)
│   └── stacks/data_ingestion_stack.py # Data upload + KB sync
├── data/                       # Sample manufacturing data
├── scripts/invoke_agent.py     # Interactive CLI
└── tests/
```

## Teardown

```bash
agentcore destroy                    # Remove agent runtime
cd infra && cdk destroy --all        # Remove Knowledge Bases and data
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This sample code is made available under the MIT-0 license. See the [LICENSE](LICENSE) file.

> **Disclaimer:** This is sample code for demonstration and educational purposes only, not for production use.
```

- [ ] **Step 3: Commit**

```bash
git add data/.gitkeep README.md
git commit -m "docs: rewrite README for new AgentCore CLI + KB CDK workflow

Documents the new deployment flow: deploy KBs via CDK, then deploy
agent via agentcore CLI. Includes evaluation and local dev instructions."
```

---

## Task 13: Create root-level pyproject.toml for development

Create a workspace-level `pyproject.toml` for development tooling (linting, formatting, test config).

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "agent-rca-smartmanufacturing"
version = "0.1.0"
description = "Manufacturing RCA Agent - workspace root"
requires-python = ">=3.12"
license = { text = "MIT-0" }

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py312"
line-length = 120
```

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add root pyproject.toml for dev tooling config"
```

---

## Task 14: Final verification

Run all tests and verify the project structure is complete and consistent.

- [ ] **Step 1: Run all tests**

```bash
cd agent && uv run pytest ../tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Verify agent builds locally**

```bash
cd agent && agentcore dev
```

Expected: local dev server starts on port 8080.

- [ ] **Step 3: Verify CDK infra synthesizes**

```bash
cd infra && cdk synth --no-lookups
```

Expected: all three stacks synthesize.

- [ ] **Step 4: Verify project structure matches README**

```bash
find . -type f | grep -v '.git/' | grep -v 'node_modules/' | grep -v '__pycache__/' | sort
```

Compare against the project structure in README.

- [ ] **Step 5: Final commit if any cleanup needed**

```bash
git status
```

If clean, no commit needed.

---

## Execution Notes

### Ordering constraints

- **Task 1** must be first (removes old files)
- **Task 2** must follow Task 1 (creates new dependency management)
- **Task 3** depends on Task 2 (new entrypoint uses uv)
- **Task 4** depends on Task 3 (modifies graph, requires main.py to exist)
- **Tasks 5-6** (AgentCore CLI) can run in parallel with Tasks 7-9 (KB CDK)
- **Task 10** (KB logging) depends on Task 2
- **Task 11** depends on Task 5 (needs CLI deployed to test)
- **Task 12** depends on all other tasks (documents final state)
- **Task 13** is independent
- **Task 14** must be last

### Unknowns to resolve during implementation

1. **Strands interrupt API** — the exact import paths for `BeforeNodeCallEvent`, `AfterNodeCallEvent`, and `Interrupt` need verification against Strands 1.37. Check `from strands.multiagent.graph import ...` or explore the package.
2. **AgentCore CLI CDK customization** — the exact property path to the runtime role (e.g., `app.runtimes.get('RCAAgent').role`) depends on what `@aws/agentcore-cdk` exports. Verify after generating the scaffold.
3. **`logged_retrieve` wrapping** — the `strands_tools.retrieve` tool may be a decorated function or a class. If it can't be wrapped directly, use Strands hooks instead.
4. **AOSS policy propagation** — the OpenSearch Serverless data access policy may need a wait/custom-resource to handle eventual consistency. If CDK deployment fails on first try, add a `CfnWaitCondition` or custom resource with retry logic.
5. **Neptune Analytics CDK** — the `aws_neptunegraph` L1 constructs may have slightly different property names. Verify against current CDK docs.
6. **Sample data format** — placeholder until user provides synthetic manufacturing records.
