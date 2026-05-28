#!/usr/bin/env python3
"""CDK app entry point for Knowledge Base infrastructure.

Deploys:
  - Hybrid KB (OpenSearch Serverless) — vector + keyword search
  - GraphRAG KB (Neptune Analytics) — entity relationship graph
  - Shared S3 data bucket
"""

import aws_cdk as cdk
from stacks.kb_stack import RcaKbStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or None,
    region=app.node.try_get_context("region") or None,
)

RcaKbStack(app, "RcaKbStack", env=env)

app.synth()
