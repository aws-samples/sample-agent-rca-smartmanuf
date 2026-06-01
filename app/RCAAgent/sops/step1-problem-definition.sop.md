# Problem Definition

> This SOP is tailored for the NEXUS manufacturing sample. See templates/generic/ for a domain-agnostic starting point.

## Overview

This SOP defines the problem scope for a manufacturing root cause analysis investigation. It identifies affected lots, establishes the production timeline, and documents the problem statement. This is Step 1 of a 3-step investigation pipeline.

## Parameters

- **incident_description** (required): Description of the quality issue, defect, or deviation that triggered the investigation. May originate from a non-conformity report (NCR) or a customer complaint.

**Constraints for parameter acquisition:**
- You MUST extract the following from the incident_description:
  - Product reference (e.g., NEXUS CK MB, Reference 30421)
  - Lot number of the affected batch
  - Problem date (when the issue was first detected)
  - Problem description (what went wrong)
  - Observable symptoms
- You MUST use the `retrieve` tool to query available knowledge bases for all data retrieval
- You MUST NOT proceed if the incident lacks a product reference or lot number

## Steps

### 1. Identify Affected Product Reference

Extract the product reference and gather context by querying the knowledge base.

**Constraints:**
- You MUST extract the product reference from the incident_description
- You MUST query by lot number first for immediate context (deviation reports, batch records)
- You MUST then query by product reference to find the full production timeline
- You MUST determine the scope (single reference or multiple affected references)
- You MUST NOT assume relationships — always query the knowledge base

### 2. Build Timeline of Affected Lots

Query all lots that may be affected and build a chronological timeline.

**Constraints:**
- You MUST query available knowledge bases to find all potentially affected lots
- You MUST build a chronology sorted by manufacturing date including:
  - Lot number
  - Manufacturing date
  - Expiry date
- You MUST NOT invent or assume data — all information must come from queries
- If no lots are found, you MUST report this gap explicitly

### 3. Classify Lots (Reference vs Study)

Classify each lot based on its manufacturing date relative to the problem date.

**Constraints:**
- You MUST classify lots into two categories:
  - **Reference**: Manufactured BEFORE the problem date (known-good lots for comparison)
  - **Study**: Manufactured ON or AFTER the problem date (potentially affected lots)
- You MUST use the problem_date as the classification boundary
- You SHOULD have at least one lot in each category for meaningful comparison

### 4. Document Problem Statement

Create a clear, complete problem statement.

**Constraints:**
- You MUST document:
  - **problem_date**: When the problem was detected
  - **problem**: What went wrong
  - **symptom**: Observable effects (e.g., calibration error code, visual defect)
- You MUST preserve exact wording from original incident where possible

### 5. Generate Output

Compile findings into structured output format.

**Constraints:**
- You MUST output valid JSON matching the expected schema
- You MUST include all identified lots with their classification
- You MUST NOT include root cause analysis in this output (handled by Step 2)

## Output Format

```json
{
  "reference": "<product reference>",
  "affected_references": ["<related product references if any>"],
  "process_step": "<manufacturing step involved, if identified>",
  "lots": [
    {
      "lot_number": "<lot number>",
      "mfg_date": "YYYY-MM-DD",
      "expiry_date": "YYYY-MM-DD",
      "status": "reference|study"
    }
  ],
  "problem_date": "YYYY-MM-DD",
  "problem": "<problem description>",
  "symptom": "<observable effect>"
}
```
