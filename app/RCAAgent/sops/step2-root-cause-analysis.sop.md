# Root Cause Analysis

> This SOP is tailored for the NEXUS manufacturing sample. See templates/generic/ for a domain-agnostic starting point.

## Overview

This SOP identifies potential root causes by querying available data sources and documenting evidence. It takes the problem definition from Step 1 and produces a list of potential causes ranked by likelihood. This is Step 2 of a 3-step investigation pipeline.

## Parameters

- **problem_definition** (required): Output from Step 1 containing problem statement and affected lots.

## Steps

### 1. Query Data Sources

Search available data sources for information related to the problem.

**Constraints:**
- You MUST query multiple data source categories via the `retrieve` tool:
  - **Changes**: change control records, procedure updates, process modifications
  - **Quality Records**: deviation reports (NCRs), QC reports, trend analyses, CAPAs
  - **Equipment & Maintenance**: calibration logs, changeover records, work orders, machine stops
  - **Materials & Suppliers**: batch records, material consumption, certificates of analysis, supplier audit data
  - **Historical**: past investigations, quality reviews, FMEAs, risk analyses
- You MUST document which source categories were queried and whether results were found
- You MUST query using relevant terms from the problem definition (product reference, lot numbers, dates, symptoms)

### 2. Identify Potential Causes

Analyze query results to identify potential causes.

**Constraints:**
- A finding is a **potential cause** if ANY of these conditions are true:
  - It represents a change that occurred near the problem date
  - It describes a known risk matching the observed symptom
  - It documents a previous similar issue
  - It shows an anomaly in the affected timeframe
- You MUST assign a unique ID to each potential cause (e.g., PC-001, PC-002)
- You MUST document the evidence source for each cause (name of the document or record)
- You MUST NOT fabricate causes without supporting evidence

### 3. Categorize Causes

Assign each potential cause to a category.

**Constraints:**
- You MUST classify each cause into one of these categories:
  - **Material**: Raw materials, components, supplies (e.g., SPR cones, reagents)
  - **Equipment**: Machines, tools, instruments (e.g., assembly lines, calibration stations)
  - **Process**: Methods, procedures, parameters (e.g., changeover procedure, calibration process)
  - **Environment**: Conditions, facilities (e.g., temperature, humidity, storage)
  - **Personnel**: Training, human factors (e.g., operator error, qualification gaps)
- You SHOULD use keywords in the evidence to guide categorization

### 4. Prioritize by Likelihood

Rank potential causes by likelihood of being the root cause.

**Constraints:**
- You SHOULD consider:
  - Timing correlation with problem date
  - Strength of evidence
  - Historical frequency of similar issues
- You MUST NOT eliminate causes at this stage (verification is Step 3)

### 5. Generate Output

Compile all potential causes into structured output.

**Constraints:**
- You MUST output valid JSON with all identified causes
- You MUST preserve traceability to evidence sources
- You MUST include causes even if evidence is weak (elimination happens in Step 3)

## Output Format

```json
{
  "potential_causes": [
    {
      "id": "PC-001",
      "category": "Equipment",
      "source": "<document or record name>",
      "description": "<what might have caused the problem>",
      "evidence_summary": "<supporting information from the data>",
      "likelihood": "high|medium|low"
    }
  ]
}
```
