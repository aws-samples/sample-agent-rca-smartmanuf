#!/usr/bin/env python3
"""
Interactive investigation agent CLI.

Provides a conversational interface for quality engineers to describe
problems in natural language. The agent runs the 3-step investigation
pipeline (Problem Definition, Root Cause Analysis, Verification) and
supports follow-up questions.

Usage:
    python scripts/invoke_agent.py
    python scripts/invoke_agent.py --agent-arn <arn> --region us-east-1
"""

import argparse
import json
import subprocess
import sys
import threading
import time
import uuid

import boto3
from botocore.config import Config


STEP_LABELS = {
    "step1": "Step 1: Problem Definition",
    "step2": "Step 2: Root Cause Analysis",
    "step3": "Step 3: Verification",
}

MAX_RETRIES = 3

WELCOME_BANNER = """
\033[1m======================================================================
  Manufacturing RCA Agent
======================================================================\033[0m

  Describe a quality issue and I will investigate it using
  a 3-step root cause analysis methodology.

  \033[2mExamples:\033[0m
    "Defect found in production batch BATCH-2026-001"
    "Quality deviation on assembly line 3, reported 2026-03-10"
    "Customer complaint about product ABC-123"

  Type \033[1mquit\033[0m to exit.
======================================================================
"""


def get_agent_arn_and_region_from_cli() -> tuple[str, str]:
    """Fetch the agent ARN and region from agentcore CLI deployed state."""
    try:
        result = subprocess.run(
            ["agentcore", "status", "--json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return "", ""
        # Strip ANSI escape sequences appended by the CLI
        raw = result.stdout.strip()
        json_end = raw.rfind("}") + 1
        data = json.loads(raw[:json_end])
        region = data.get("targetRegion", "")
        for resource in data.get("resources", []):
            if resource.get("resourceType") == "agent":
                return resource.get("identifier", ""), region
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return "", ""


class Spinner:
    """Animated spinner with elapsed time, runs in a background thread."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Processing"):
        self._message = message
        self._stop_event = threading.Event()
        self._thread = None
        self._start_time = None

    def _spin(self):
        idx = 0
        while not self._stop_event.is_set():
            elapsed = time.time() - self._start_time
            frame = self.FRAMES[idx % len(self.FRAMES)]
            mins, secs = divmod(int(elapsed), 60)
            time_str = f"{mins}:{secs:02d}" if mins else f"{secs}s"
            sys.stdout.write(f"\r  {frame} {self._message} ({time_str})")
            sys.stdout.flush()
            idx += 1
            self._stop_event.wait(0.1)

    def start(self):
        self._start_time = time.time()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, clear: bool = True):
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        if clear:
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()


def invoke_step(client, agent_arn: str, session_id: str, payload: dict) -> dict:
    """Invoke one step of the investigation with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.invoke_agent_runtime(
                agentRuntimeArn=agent_arn,
                runtimeSessionId=session_id,
                payload=json.dumps(payload),
            )

            body = response["response"].read()
            data = json.loads(body)
            if isinstance(data, str):
                data = json.loads(data)

            if "error" in data:
                if data.get("retryable") and attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt * 5
                    print(f"  Retryable error: {data['error'][:100]}. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                return data

            return data

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt * 5
                print(f"  Error: {str(e)[:100]}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                return {"step": payload.get("step", "?"), "error": str(e), "done": True}

    return {"step": payload.get("step", "?"), "error": "Max retries exceeded", "done": True}


def run_investigation(client, agent_arn: str, session_id: str, prompt: str):
    """Run the full 3-step investigation pipeline."""
    graph_state = None
    steps = ["step1", "step2", "step3"]
    step_idx = 0
    total_start = time.time()

    while step_idx < len(steps):
        step = steps[step_idx]
        label = STEP_LABELS.get(step, step)
        print(f"\n\033[1m{'='*70}")
        print(f"  {label}")
        print(f"{'='*70}\033[0m")

        payload = {"step": step, "prompt": prompt}
        if graph_state:
            payload["graph_state"] = graph_state

        spinner = Spinner(f"Agent is working on {label}...")
        spinner.start()
        start = time.time()
        resp = invoke_step(client, agent_arn, session_id, payload)
        elapsed = time.time() - start
        spinner.stop()

        if "error" in resp:
            print(f"\n  \033[31mERROR: {resp['error']}\033[0m")
            print(f"  [{elapsed:.0f}s]")
            return

        result = resp.get("result", "(no result)")
        print(result)

        print(f"\n  \033[2m[{elapsed:.0f}s]\033[0m", end="")

        if resp.get("done"):
            print(" -- Investigation complete.")
            break

        next_step = resp.get("next_step", "?")
        print(f" -- Next: {next_step}")
        graph_state = resp.get("graph_state")
        step_idx += 1

    total = time.time() - total_start
    print(f"\n\033[1m{'='*70}")
    print(f"  Investigation finished in {total:.0f}s.")
    print(f"{'='*70}\033[0m\n")


def main():
    parser = argparse.ArgumentParser(description="Interactive Manufacturing RCA Agent")
    parser.add_argument("--agent-arn", required=False,
                        help="AgentCore runtime ARN (e.g. arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/NAME)")
    parser.add_argument("--region", default=None)
    args = parser.parse_args()

    agent_arn = args.agent_arn
    region = args.region
    if not agent_arn:
        agent_arn, detected_region = get_agent_arn_and_region_from_cli()
        if not region and detected_region:
            region = detected_region
    if not region:
        region = "us-east-1"
    if not agent_arn:
        print("Error: Could not determine agent ARN.")
        print("Either pass --agent-arn or run 'agentcore deploy' first.")
        sys.exit(1)

    config = Config(read_timeout=600, connect_timeout=30, retries={"max_attempts": 3})
    client = boto3.client("bedrock-agentcore", region_name=region, config=config)
    session_id = str(uuid.uuid4())

    print(WELCOME_BANNER)

    while True:
        try:
            user_input = input("\033[1mYou>\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        session_id = str(uuid.uuid4())
        run_investigation(client, agent_arn, session_id, user_input)
        print("  Type another incident to start a new investigation, or \033[1mquit\033[0m to exit.\n")


if __name__ == "__main__":
    main()
