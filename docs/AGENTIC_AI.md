# Agentic AI Implementation Guide

## 1. Purpose

The agentic layer turns one code-review request into a coordinated set of narrow, inspectable
analyses. Each agent has one responsibility, its own tools, and a shared state contract. A
manager then consolidates those independent observations into one review outcome.

This design is deliberately transparent. The current implementation is deterministic and
offline-first: it uses diff parsing, Python-aware heuristics, regular expressions, and AST syntax
validation. It does not pretend that a language model was used when it was not. The architecture
leaves clear integration points for a future model-backed adapter without making local execution
dependent on a paid API key.

## 2. What makes this agentic

The system has the core properties of a multi-agent workflow:

- **Specialization:** security, style, coverage, diff understanding, and fix generation are
  separate responsibilities.
- **Tool use:** agents call multiple concrete analysis functions instead of returning hardcoded
  findings.
- **Shared memory:** agents read and update one `ReviewChangeState` instance.
- **Coordination:** the manager controls sequencing, parallel fan-out, aggregation, and decision
  making.
- **Structured communication:** findings and execution results use dictionaries and Pydantic
  response models rather than free-form text.
- **Traceability:** agent status, tool activity, findings, decisions, and failures are persisted
  or logged for inspection.
- **Human control:** generated fixes are suggestions only; the original submission is immutable.

The application is therefore an agentic orchestration system even though its default reasoning
tools are deterministic static analyzers rather than an external LLM.

## 3. Agent roster

### Diff Agent

**Module:** `backend/agents/diff_agent.py`

**Responsibility:** establish the review context before specialist analysis begins.

**Tools:**

1. `parse_git_diff(diff_text)` extracts changed files, additions, deletions, and hunk metadata.
2. `analyze_changed_files(diff_text, language)` identifies functions, classes, imports, and
   simple complexity indicators.

**Shared-state output:** `state.diff_analysis` and the `diff_summary` metadata entry. Other agents
   use the detected file list to attach findings to a meaningful file name.

### Style Agent

**Module:** `backend/agents/style_agent.py`

**Responsibility:** identify maintainability and readability problems without changing the source.

**Tools:**

1. `run_style_analysis(code, language)` checks long lines, unresolved TODOs, nesting, argument
   counts, missing public-function docstrings, and Python naming conventions.
2. `detect_code_duplication(code)` searches for repeated normalized blocks.

**Typical output:** `LOW` style/documentation findings and `MEDIUM` complexity/design findings.

### Security Agent

**Module:** `backend/agents/security_agent.py`

**Responsibility:** find credential exposure and dangerous code patterns.

**Tools:**

1. `scan_secrets(code)` detects passwords, tokens, API keys, private keys, and credential-bearing
   URLs. Evidence is redacted before it becomes a finding.
2. `detect_security_vulnerabilities(code, language)` checks SQL construction, shell execution,
   `eval`, `exec`, unsafe deserialization, weak hashes, unsafe XML parsing, and internal IPs.

**Safety rule:** the security agent only matches text. It never attempts to validate a credential
   by contacting a service and never executes submitted code.

### Test-Coverage Agent

**Module:** `backend/agents/test_coverage_agent.py`

**Responsibility:** identify likely gaps in tests for changed or public functions.

**Tools:**

1. `discover_test_files(code, file_list)` identifies test functions and test-like file names.
2. `analyze_test_coverage(code, diff_text, language)` estimates tested versus untested
   functions and identifies new functions without corresponding tests.

The output is explicitly marked as **estimated**. It is not a claim produced by a test runner and
must not be interpreted as measured runtime coverage.

### Fix-Suggestion Agent

**Module:** `backend/agents/fix_suggestion_agent.py`

**Responsibility:** provide one focused, advisory repair for the highest-severity finding.

**Tools:**

1. `generate_fix_patch(finding, code_context, language)` selects a safe template and produces
   before/after code plus an explanation and expected result.
2. `validate_patch_syntax(code, language)` uses `ast.parse` for Python and balanced-brace
   heuristics for JavaScript/TypeScript.

The agent stores the suggestion in shared metadata and adds an informational finding. It never
rewrites the submitted content or applies the patch.

### Reviewer Manager

**Module:** `backend/agents/reviewer_manager.py`

**Responsibility:** coordinate the workflow and make the final deterministic recommendation.

**Tools:**

1. `aggregate_agent_findings(findings)` deduplicates by title, file, and line, keeps the
   highest-severity copy, sorts findings, and calculates severity counts.
2. `calculate_merge_recommendation(findings, config)` applies the blocking policy and explains
   which findings caused `REQUEST_CHANGES`.

The manager is the only component that decides the review recommendation. Specialist agents
provide evidence; they do not independently approve or block a change.

## 4. Shared change state

`backend/core/change_state.py` defines `ReviewChangeState`, the in-memory collaboration object
created for each review. It contains:

- Immutable review identity and submitted content references.
- Language and repository metadata.
- Diff analysis metadata.
- All findings and findings grouped by agent.
- Agent statuses such as `RUNNING`, `COMPLETED`, and `FAILED`.
- Manager metadata such as the aggregate result, recommendation, and fix suggestion.

Access to mutable collections is protected by a `threading.Lock`. Agents therefore communicate
through explicit methods:

```python
state.add_finding(finding)
state.update_agent_status(agent_name, "COMPLETED")
state.set_metadata("diff_summary", summary)
state.get_metadata("diff_summary", {})
```

The state is the workflow memory for one execution. SQLite is the durable record used after the
pipeline completes.

## 5. Execution lifecycle

The manager implements fan-out/fan-in orchestration:

```text
request
  |
  v
create ReviewChangeState
  |
  v
Diff Agent (sequential prerequisite)
  |
  +--> Style Agent --------+
  +--> Security Agent -----+--> aggregate --> Fix Suggestion --> decision
  +--> Coverage Agent -----+
```

### Step 1: Context creation

The API creates a `Review` row with `PENDING` status and constructs a shared state object. The
pipeline runs asynchronously so the client can poll the review resource.

### Step 2: Diff analysis

The Diff Agent runs first because specialist findings should reference the changed file context.
It publishes file names and change statistics to state.

### Step 3: Specialist fan-out

Style, Security, and Test-Coverage agents run with `asyncio.gather`. They independently read the
submission and relevant diff metadata, then publish findings to the same state object.

### Step 4: Fan-in and deduplication

The manager converts state findings into structured dictionaries. Findings with the same title,
file, and line are considered duplicates. When duplicate records differ in severity, the higher
severity record wins.

### Step 5: Fix generation

The highest-severity consolidated finding is passed to the Fix-Suggestion Agent. The resulting
patch is syntax-checked and stored as advisory metadata.

### Step 6: Recommendation

The manager applies deterministic thresholds, stores the decision in state, and returns a
complete result containing summary counts, blocking IDs, agent results, and findings.

## 6. Finding contract

Every finding follows the same shape:

```json
{
  "agent": "Security Agent",
  "file": "example.py",
  "line": 12,
  "severity": "HIGH",
  "category": "Security Vulnerability",
  "title": "Command Injection",
  "description": "Explanation of the detected pattern",
  "recommendation": "Use a safe alternative",
  "evidence": "Redacted or bounded code evidence"
}
```

The API validates response shape with Pydantic models. Severity is one of `CRITICAL`, `HIGH`,
`MEDIUM`, `LOW`, or `INFO`.

## 7. Merge policy

`calculate_merge_recommendation` uses this order:

1. One or more `CRITICAL` findings blocks the merge.
2. Any `HIGH` finding in a security or secret category blocks the merge.
3. Three or more `HIGH` findings block the merge.
4. Five or more `MEDIUM` findings block the merge.
5. All other results are `APPROVE`.

The output contains both a human-readable reason and the IDs/details of blocking findings. This
separates evidence collection from policy and makes the policy straightforward to test or replace.

## 8. Persistence and auditability

The API stores:

- `Review`: submission metadata, status, counts, decision, and decision reason.
- `AgentExecution`: agent name, status, timestamps, finding count, and tools invoked.
- `Finding`: normalized agent output and evidence.
- `SuggestedPatch`: advisory before/after code and validation result.
- `ReviewLog`: append-only audit events.

The in-process `ReviewLogger` records events during execution. The API persists those entries
after the pipeline finishes. Errors update the review to `FAILED` and are recorded with an error
event; they are not silently converted into an approval.

## 9. Offline mode and future LLM integration

Offline mode is the default because it is reproducible, safe for untrusted submissions, and
usable without credentials. A future model adapter should preserve the current contracts:

1. Accept the existing `ReviewChangeState` and bounded context.
2. Return the same structured finding schema.
3. Keep deterministic policy evaluation in the manager.
4. Keep secrets redacted before prompts or external requests.
5. Record model/tool calls and failures in the audit log.
6. Never allow generated code to execute automatically.

Semantic Kernel or another supported LLM framework can be introduced behind these contracts.
Doing so should enrich explanations or prioritization, not replace the deterministic safety
checks and merge policy.

## 10. Failure handling

Each agent sets its own status and catches failures at its execution boundary. The manager uses
`return_exceptions=True` for concurrent specialists so one failed specialist does not crash the
event loop. The review persistence layer still records the overall pipeline result and agent
status.

For production hardening, the next improvements would be persistent per-agent start/end
timestamps, retry policy with bounded attempts, queue-backed execution, and a database-backed
event stream. Those are extensions, not assumptions about the current implementation.

## 11. How to extend an agent

To add a new specialist:

1. Create `backend/agents/<name>_agent.py`.
2. Define a unique `AGENT_NAME`.
3. Implement at least two deterministic tools with typed, structured returns.
4. Implement `async def run(state)` and update status on every exit path.
5. Add findings through `state.add_finding`.
6. Register it in `reviewer_manager.run`.
7. Include its tools and status in persisted execution records.
8. Add focused tests for clean input, positive detection, invalid input, and failure behavior.
9. Update the UI/report documentation if the agent changes visible output.
