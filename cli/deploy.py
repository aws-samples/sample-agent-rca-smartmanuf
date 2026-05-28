"""Manufacturing RCA Agent — Deployment CLI.

Pure stdlib + boto3. No external CLI dependencies except `cdk` and `agentcore`.

Usage:
    uv run deploy              # full end-to-end deployment
    uv run deploy infra        # deploy CDK infrastructure only
    uv run deploy ingest       # upload data + wait for ingestion
    uv run deploy agent        # deploy AgentCore agent + permissions
    uv run deploy test         # run smoke test
    uv run deploy destroy      # tear down everything
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import boto3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STACK_NAME = "RcaKbStack"
TARGETS_FILE = PROJECT_ROOT / "agentcore" / "aws-targets.json"
AGENTCORE_JSON = PROJECT_ROOT / "agentcore" / "agentcore.json"
DATA_DIR = PROJECT_ROOT / "data"
INGESTION_TIMEOUT = 900
INGESTION_POLL_INTERVAL = 30


def _load_config() -> tuple[str, str]:
    """Load account/region from aws-targets.json, with env var overrides."""
    if not TARGETS_FILE.exists():
        _fail(f"{TARGETS_FILE} not found. Set your account/region there. See README.")

    targets = json.loads(TARGETS_FILE.read_text())
    file_account = targets[0]["account"]
    file_region = targets[0]["region"]

    account = os.environ.get("AWS_ACCOUNT_ID", file_account)
    region = os.environ.get("AWS_REGION", file_region)

    if "<" in account or not account.isdigit():
        _fail(
            f"Invalid account '{account}' in {TARGETS_FILE}.\n"
            "  Set your 12-digit AWS account ID. Find it with:\n"
            "    aws sts get-caller-identity --query Account --output text"
        )

    return account, region


def _fail(msg: str):
    print(f"\n  ✗ {msg}", file=sys.stderr)
    sys.exit(1)


def _info(msg: str):
    print(f"  {msg}")


def _header(step: str, title: str):
    print(f"\n{'='*60}")
    print(f"  [{step}] {title}")
    print(f"{'='*60}\n")


def _run(cmd: list[str], cwd: str | Path | None = None, capture: bool = False) -> str:
    """Run a subprocess, fail on error."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture,
        text=True,
    )
    if result.returncode != 0:
        if capture:
            _fail(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
        sys.exit(result.returncode)
    return result.stdout if capture else ""


def _check_prerequisites():
    """Verify required tools are installed."""
    print("Checking prerequisites...")
    missing = []

    checks = [
        ("uv", "Install: https://docs.astral.sh/uv/getting-started/installation/"),
        ("node", "Install: https://nodejs.org/ (v20+)"),
        ("cdk", "Install: npm install -g aws-cdk"),
        ("tsc", "Install: npm install -g typescript"),
    ]

    for cmd, hint in checks:
        if shutil.which(cmd):
            _info(f"✓ {cmd}")
        else:
            _info(f"✗ {cmd} — {hint}")
            missing.append(cmd)

    if missing:
        _fail("Missing prerequisites. Install the tools above and retry.")

    if shutil.which("agentcore") and subprocess.run(
        ["agentcore", "--help"], capture_output=True
    ).returncode == 0:
        _info("✓ agentcore")
    else:
        _info("⟳ agentcore not found — installing via npm...")
        _run(["npm", "install", "-g", "@aws/agentcore"])
        if subprocess.run(["agentcore", "--help"], capture_output=True).returncode == 0:
            _info("✓ agentcore (installed)")
        else:
            _fail("agentcore auto-install failed. Install manually: npm install -g @aws/agentcore")


def _get_stack_outputs(region: str) -> dict[str, str]:
    """Read CloudFormation stack outputs."""
    cfn = boto3.client("cloudformation", region_name=region)
    resp = cfn.describe_stacks(StackName=STACK_NAME)
    outputs = resp["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def _patch_agentcore_json(hybrid_kb_id: str, graphrag_kb_id: str):
    """Write KB IDs into agentcore.json."""
    config = json.loads(AGENTCORE_JSON.read_text())
    env_vars = config["runtimes"][0]["envVars"]
    for var in env_vars:
        if var["name"] == "KB_HYBRID_ID":
            var["value"] = hybrid_kb_id
        elif var["name"] == "KB_GRAPHRAG_ID":
            var["value"] = graphrag_kb_id
    AGENTCORE_JSON.write_text(json.dumps(config, indent=2) + "\n")


# =============================================================================
# Subcommands
# =============================================================================


def cmd_infra(account: str, region: str):
    """Deploy CDK infrastructure."""
    _header("infra", "Deploying infrastructure (CDK)")

    infra_dir = PROJECT_ROOT / "infra"
    _run(["uv", "sync", "--quiet"], cwd=infra_dir)
    _run(
        ["uv", "run", "cdk", "deploy", STACK_NAME,
         "-c", f"account={account}", "-c", f"region={region}",
         "--require-approval", "never"],
        cwd=infra_dir,
    )

    outputs = _get_stack_outputs(region)
    _info(f"S3 Bucket:   {outputs['DataBucketName']}")
    _info(f"Hybrid KB:   {outputs['HybridKbId']}")
    _info(f"GraphRAG KB: {outputs['GraphRagKbId']}")

    return outputs


def cmd_ingest(account: str, region: str, outputs: dict[str, str] | None = None):
    """Upload data to S3, trigger ingestion, wait for completion."""
    _header("ingest", "Uploading data and triggering ingestion")

    if outputs is None:
        outputs = _get_stack_outputs(region)

    bucket = outputs["DataBucketName"]
    hybrid_kb_id = outputs["HybridKbId"]
    hybrid_ds_id = outputs["HybridDataSourceId"]
    graphrag_kb_id = outputs["GraphRagKbId"]
    graphrag_ds_id = outputs["GraphRagDataSourceId"]

    # Upload data
    s3 = boto3.client("s3", region_name=region)
    uploaded = 0
    for file_path in DATA_DIR.rglob("*"):
        if file_path.is_dir():
            continue
        if file_path.name == ".gitkeep" or "_validation" in str(file_path):
            continue
        key = f"manufacturing-records/{file_path.relative_to(DATA_DIR)}"
        s3.upload_file(str(file_path), bucket, key)
        uploaded += 1

    _info(f"Uploaded {uploaded} files to s3://{bucket}/manufacturing-records/")

    # Trigger ingestion
    bedrock_agent = boto3.client("bedrock-agent", region_name=region)

    hybrid_job = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=hybrid_kb_id, dataSourceId=hybrid_ds_id
    )["ingestionJob"]["ingestionJobId"]

    graphrag_job = bedrock_agent.start_ingestion_job(
        knowledgeBaseId=graphrag_kb_id, dataSourceId=graphrag_ds_id
    )["ingestionJob"]["ingestionJobId"]

    _info(f"Hybrid ingestion job:  {hybrid_job}")
    _info(f"GraphRAG ingestion job: {graphrag_job}")

    # Patch agentcore.json
    _patch_agentcore_json(hybrid_kb_id, graphrag_kb_id)
    _info("Updated agentcore.json with KB IDs")

    # Wait for ingestion
    print()
    _info("Waiting for ingestion to complete...")

    _wait_for_ingestion(bedrock_agent, hybrid_kb_id, hybrid_ds_id, hybrid_job, "Hybrid")
    _wait_for_ingestion(bedrock_agent, graphrag_kb_id, graphrag_ds_id, graphrag_job, "GraphRAG")

    return outputs


def _wait_for_ingestion(client, kb_id: str, ds_id: str, job_id: str, label: str):
    """Poll ingestion job until complete."""
    start = time.time()

    while True:
        elapsed = int(time.time() - start)
        if elapsed > INGESTION_TIMEOUT:
            _fail(f"{label} ingestion timed out after {INGESTION_TIMEOUT}s")

        resp = client.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )
        status = resp["ingestionJob"]["status"]

        if status == "COMPLETE":
            mins, secs = divmod(elapsed, 60)
            _info(f"{label} KB: COMPLETE ({mins}m {secs}s)")
            return
        elif status == "FAILED":
            reason = resp["ingestionJob"].get("failureReasons", ["unknown"])
            _fail(f"{label} ingestion FAILED: {reason}")

        print(f"  {label} KB: {status} ({elapsed}s)...", end="\r", flush=True)
        time.sleep(INGESTION_POLL_INTERVAL)


def cmd_agent(account: str, region: str, outputs: dict[str, str] | None = None):
    """Deploy AgentCore agent (KB permissions are managed by CDK)."""
    _header("agent", "Deploying agent (AgentCore)")

    # Sync agent deps
    _run(["uv", "sync", "--quiet"], cwd=PROJECT_ROOT / "app" / "RCAAgent")

    # Install CDK dependencies if needed
    cdk_dir = PROJECT_ROOT / "agentcore" / "cdk"
    if not (cdk_dir / "node_modules").exists():
        _info("Installing CDK dependencies...")
        _run(["npm", "install"], cwd=cdk_dir)

    # Deploy via agentcore (must run from project root)
    # CDK stack grants bedrock:Retrieve on both KBs via envVars in agentcore.json
    _run(["agentcore", "deploy", "-y"], cwd=PROJECT_ROOT)



def cmd_test(account: str, region: str):
    """Run a smoke test against the deployed agent."""
    _header("test", "Running smoke test")

    _info("Invoking step 1 with sample incident...")

    payload = json.dumps({
        "step": "step1",
        "prompt": (
            "Investigate quality deviation on product NEXUS CK MB Reference 30421. "
            "Lot 1009900940 reported calibration error B18 on S1 signal exceeding "
            "550 RFV specification limit."
        ),
    })

    try:
        result = subprocess.run(
            ["agentcore", "invoke", payload],
            capture_output=True, text=True, timeout=300,
        )
        response = result.stdout.strip()
        data = json.loads(response)
        if isinstance(data, str):
            data = json.loads(data)

        if "error" in data:
            _info(f"✗ Smoke test failed: {data['error'][:200]}")
            _info("")
            _info("Debugging hints:")
            _info(f"  - Check model access: Ensure Claude Opus 4.6 is enabled in {region}")
            _info("  - Check agent logs: agentcore obs list")
            return False

        if data.get("step") == "step1" and data.get("result"):
            _info(f"✓ Smoke test passed ({len(data['result'])} chars of analysis)")
            return True

        _info("✗ Unexpected response structure")
        return False

    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        _info(f"✗ Smoke test failed: {e}")
        return False


def cmd_destroy(account: str, region: str):
    """Tear down all deployed resources."""
    _header("destroy", "Destroying all resources")

    _info("Destroying AgentCore agent...")
    subprocess.run(["agentcore", "destroy"], cwd=PROJECT_ROOT)

    _info("Destroying CDK stack...")
    _run(
        ["uv", "run", "cdk", "destroy", "--all", "--force",
         "-c", f"account={account}", "-c", f"region={region}"],
        cwd=PROJECT_ROOT / "infra",
    )

    _info("✓ All resources destroyed.")


# =============================================================================
# Main
# =============================================================================


COMMANDS = {
    "infra": "Deploy CDK infrastructure (S3, OpenSearch, Neptune, KBs)",
    "ingest": "Upload data + trigger and wait for ingestion",
    "agent": "Deploy AgentCore agent (includes KB permissions via CDK)",
    "test": "Run smoke test",
    "destroy": "Tear down all resources",
}


def _print_usage():
    print("\nManufacturing RCA Agent — Deployment CLI\n")
    print("Usage: uv run deploy [command]\n")
    print("Commands:")
    for cmd, desc in COMMANDS.items():
        print(f"  {cmd:<10} {desc}")
    print(f"  {'(none)':<10} Run full deployment (infra + ingest + agent + test)")
    print()


def main():
    args = sys.argv[1:]

    if args and args[0] in ("-h", "--help", "help"):
        _print_usage()
        return

    command = args[0] if args else None

    if command and command not in COMMANDS:
        print(f"Unknown command: {command}")
        _print_usage()
        sys.exit(1)

    print()
    print("=" * 60)
    print("  Manufacturing RCA Agent — Deployment")
    print("=" * 60)

    _check_prerequisites()

    account, region = _load_config()
    print()
    _info(f"Target: account={account}, region={region}")

    if command == "destroy":
        cmd_destroy(account, region)
        return

    if command == "infra":
        cmd_infra(account, region)
    elif command == "ingest":
        cmd_ingest(account, region)
    elif command == "agent":
        cmd_agent(account, region)
    elif command == "test":
        cmd_test(account, region)
    else:
        # Full deployment
        outputs = cmd_infra(account, region)
        outputs = cmd_ingest(account, region, outputs)
        cmd_agent(account, region, outputs)
        cmd_test(account, region)

        print()
        print("=" * 60)
        print("  ✅ Deployment complete!")
        print("=" * 60)
        print()
        _info(f"Hybrid KB:   {outputs['HybridKbId']}")
        _info(f"GraphRAG KB: {outputs['GraphRagKbId']}")
        print()
        _info("Next steps:")
        _info("  - Interactive investigation: python scripts/invoke_agent.py")
        _info("  - Direct invoke: agentcore invoke '{\"step\": \"step1\", \"prompt\": \"...\"}'")
        _info("  - Teardown: uv run deploy destroy")
        print()
