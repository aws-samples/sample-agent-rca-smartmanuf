# Investigation Pipeline

> This SOP is tailored for the NEXUS manufacturing sample. See templates/generic/ for a domain-agnostic starting point.

## Overview

This SOP orchestrates a complete root cause analysis investigation for manufacturing quality issues. It executes three sequential steps: Problem Definition, Root Cause Analysis, and Verification. The pipeline transforms an incident report into a structured investigation with verified root causes.

## Parameters

- **incident_description** (required): The quality issue that triggered the investigation.

## Pipeline Flow

```
Incident → Step 1: Problem Definition → Step 2: Root Cause Analysis → Step 3: Verification → Root Causes
```

## Steps

### 1. Initialize Investigation

Set up the investigation context.

**Constraints:**
- You MUST generate a unique investigation ID

### 2. Execute Step 1: Problem Definition

Run the problem definition step.

**Constraints:**
- You MUST invoke step1-problem-definition SOP
- You MUST pass incident_description to the step
- You MUST capture the structured output (problem_definition)
- You MUST NOT proceed if Step 1 fails to identify affected lots

### 3. Execute Step 2: Root Cause Analysis

Run the cause identification step.

**Constraints:**
- You MUST pass problem_definition (Step 1 output) to step2-root-cause-analysis SOP
- You MUST capture all potential causes identified (root_cause_analysis)
- You MAY proceed with zero causes (investigation completes with no findings)

### 4. Execute Step 3: Verification

Run the verification step.

**Constraints:**
- You MUST pass problem_definition and potential_causes (Step 2 output) to step3-verification SOP
- You MUST capture verified causes with verdicts (verification)
- You MUST complete verification for ALL potential causes

### 5. Generate Investigation Report

Compile complete investigation results.

**Constraints:**
- You MUST include outputs from all three steps
- You MUST highlight retained causes as root causes

## Output Format

```json
{
  "investigation_id": "<unique-id>",
  "incident": {
    "type": "quality_deviation|complaint",
    "reference": "<product reference>",
    "description": "<incident description>",
    "date_reported": "YYYY-MM-DD"
  },
  "problem_definition": { },
  "root_cause_analysis": { },
  "verification": { },
  "error": null
}
```
