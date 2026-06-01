# Verification

> This SOP is tailored for the NEXUS manufacturing sample. See templates/generic/ for a domain-agnostic starting point.

## Overview

This SOP verifies each potential cause by comparing reference lots (known good) against study lots (potentially affected). For each cause, it determines a verdict of RETAINED (confirmed as root cause) or ELIMINATED (ruled out). This is Step 3 of a 3-step investigation pipeline.

## Parameters

- **problem_definition** (required): Output from Step 1 with reference and study lots.
- **potential_causes** (required): Output from Step 2 with causes to verify.

## Steps

### 1. Prepare Comparison Sets

Identify reference and study lots for comparison.

**Constraints:**
- You MUST have at least one reference lot and one study lot
- If comparison sets are empty, you MUST note this limitation
- You SHOULD select representative lots from each set

### 2. Verify Each Cause

For each potential cause, gather evidence and determine verdict.

**Constraints:**
- You MUST verify EVERY potential cause — do not skip any
- For each cause, you MUST:
  - Query relevant data for BOTH reference and study lots
  - Compare the results to identify differences
  - Document the comparison evidence
- You MUST determine verdict based on comparison:
  - **RETAINED**: Difference found between reference and study lots
  - **ELIMINATED**: No difference found (same conditions for both)
- You MUST NOT eliminate without evidence — if uncertain, RETAIN

### 3. Verify by Category

Apply category-specific verification strategies.

**Material Causes:**
- Query material/component records for reference vs study lots
- Compare: supplier, lot numbers, specifications, inspection results
- RETAIN if different materials used; ELIMINATE if same

**Equipment Causes:**
- Query equipment records for the timeframe
- Compare: maintenance events, calibration status, usage logs
- RETAIN if equipment issue correlates with study lots; ELIMINATE if not

**Process Causes:**
- Query process parameters and measurements
- Compare: parameter values, trends, deviations
- RETAIN if process difference found; ELIMINATE if same

**Environment Causes:**
- Query environmental monitoring data
- Compare: conditions during reference vs study production
- RETAIN if environmental difference found; ELIMINATE if same

**Personnel Causes:**
- Query training records, shift logs
- Compare: operator assignments, qualifications
- RETAIN if personnel difference found; ELIMINATE if same

### 4. Document Evidence

Record evidence supporting each verdict.

**Constraints:**
- You MUST document for BOTH retained and eliminated causes:
  - What was compared
  - What was found
  - Why the verdict was reached
- You MUST preserve exact values/references from queries

### 5. Generate Output

Compile verification results.

**Constraints:**
- You MUST output valid JSON with all verified causes
- You MUST include verdict and evidence for each cause
- RETAINED causes are the final root causes of the investigation

## Output Format

```json
{
  "verified_causes": [
    {
      "id": "PC-001",
      "category": "Equipment",
      "verdict": "RETAINED|ELIMINATED",
      "evidence": "<what was compared and found>",
      "reason": "<why this verdict>"
    }
  ]
}
```
