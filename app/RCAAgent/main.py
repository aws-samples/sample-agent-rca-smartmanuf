"""
AgentCore Runtime Entrypoint

Handles investigation requests via Bedrock AgentCore.
Executes the investigation graph one step per invocation using
Strands' serialize_state / deserialize_state for resumption.

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

# Required keys in graph_state for deserialization
REQUIRED_STATE_KEYS = {"type", "status", "completed_nodes", "next_nodes_to_execute", "node_results"}


def _build_graph():
    """Build a fresh investigation graph (required for deserialize_state)."""
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
        "graph_state": graph_state if is_retryable else None,
    }, default=str)


@app.entrypoint
async def handler(payload, context=None) -> str:
    """Handle an investigation request — one graph step per invocation."""
    # Parse payload
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

    # Validate step
    if step not in VALID_STEPS:
        return json.dumps({"error": f"Invalid step: {step}. Must be one of {sorted(VALID_STEPS)}"})

    # Validate graph_state structure if provided
    if graph_state is not None:
        if not isinstance(graph_state, dict):
            return json.dumps({"error": "graph_state must be a JSON object"})
        missing = REQUIRED_STATE_KEYS - set(graph_state.keys())
        if missing:
            return json.dumps({"error": f"graph_state missing required keys: {sorted(missing)}"})

    logger.info("Step=%s, has_graph_state=%s, prompt=%s", step, bool(graph_state), prompt[:150])

    try:
        # Build fresh graph for each request
        graph = _build_graph()

        # Resume from previous state if provided
        if graph_state:
            logger.info("Deserializing graph state (completed=%s, next=%s)",
                         graph_state.get("completed_nodes"), graph_state.get("next_nodes_to_execute"))
            try:
                graph.deserialize_state(graph_state)
            except Exception as e:
                logger.exception("Failed to deserialize graph state")
                return _error_response(step, ValueError(f"Invalid graph_state: {e}"))

        # When resuming from an interrupt, pass interrupt responses instead of a string
        if graph_state:
            internal = graph_state.get("_internal_state", {})
            interrupt_state = internal.get("interrupt_state", {})
            interrupts = interrupt_state.get("interrupts", {})
            invoke_input = [
                {"interruptResponse": {"interruptId": iid, "response": "continue"}}
                for iid in interrupts
            ]
            result = await graph.invoke_async(invoke_input)
        else:
            result = await graph.invoke_async(prompt)

    except Exception as e:
        logger.exception("Step=%s execution failed", step)
        return _error_response(step, e, graph_state)

    # Serialize state for next step
    serialized = graph.serialize_state()
    next_nodes = serialized.get("next_nodes_to_execute", [])
    is_done = len(next_nodes) == 0

    # Extract this step's result text
    step_result = result.results.get(step)
    if step_result and hasattr(step_result, "result") and hasattr(step_result.result, "message"):
        content = step_result.result.message.get("content", [])
        result_text = "\n".join(
            block.get("text", "") for block in content if isinstance(block, dict) and "text" in block
        )
    else:
        result_text = str(step_result) if step_result else ""

    logger.info("Step=%s complete, done=%s, next=%s, result_len=%d",
                step, is_done, next_nodes, len(result_text))

    return json.dumps({
        "step": step,
        "done": is_done,
        "next_step": next_nodes[0] if next_nodes else None,
        "result": result_text,
        "graph_state": None if is_done else serialized,
    }, default=str)


if __name__ == "__main__":
    app.run()
