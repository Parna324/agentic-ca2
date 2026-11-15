"""
Reviewer Manager: Orchestrates all agents and produces the final review decision.
"""
import asyncio
import logging
from core.change_state import ReviewChangeState, Finding
from agents import diff_agent, style_agent, security_agent, test_coverage_agent, fix_suggestion_agent

logger = logging.getLogger(__name__)

AGENT_NAME = "Reviewer Manager"

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}


# ---------------------------------------------------------------------------
# Tool 1: aggregate_agent_findings
# ---------------------------------------------------------------------------

def aggregate_agent_findings(findings: list[dict]) -> dict:
    """
    Tool 1: Deduplicate and group findings.

    Deduplication key: (title, file, line).
    When duplicates exist, keeps the highest severity copy.

    Returns:
        {
            deduplicated: list[dict],
            by_severity: dict[str, list[dict]],
            counts: dict[str, int],
            total: int,
        }
    """
    # Deduplicate: keep highest severity for identical (title, file, line) tuples
    dedup_map: dict[tuple, dict] = {}
    for f in findings:
        key = (
            f.get("title", ""),
            f.get("file", ""),
            f.get("line"),
        )
        if key not in dedup_map:
            dedup_map[key] = f
        else:
            existing = dedup_map[key]
            # Keep higher severity (lower number)
            if SEVERITY_ORDER.get(f.get("severity", "INFO"), 99) < SEVERITY_ORDER.get(
                existing.get("severity", "INFO"), 99
            ):
                dedup_map[key] = f

    deduplicated = list(dedup_map.values())

    # Sort by severity
    deduplicated.sort(key=lambda f: SEVERITY_ORDER.get(f.get("severity", "INFO"), 99))

    # Group by severity
    by_severity: dict[str, list[dict]] = {
        "CRITICAL": [],
        "HIGH": [],
        "MEDIUM": [],
        "LOW": [],
        "INFO": [],
    }
    for f in deduplicated:
        sev = f.get("severity", "INFO")
        if sev in by_severity:
            by_severity[sev].append(f)
        else:
            by_severity["INFO"].append(f)

    counts = {sev: len(items) for sev, items in by_severity.items()}

    return {
        "deduplicated": deduplicated,
        "by_severity": by_severity,
        "counts": counts,
        "total": len(deduplicated),
    }


# ---------------------------------------------------------------------------
# Tool 2: calculate_merge_recommendation
# ---------------------------------------------------------------------------

def calculate_merge_recommendation(findings: list[dict], config: dict | None = None) -> dict:
    """
    Tool 2: Deterministic merge recommendation based on finding severity counts.

    Rules (in priority order):
      1. Any CRITICAL findings           → REQUEST_CHANGES
      2. Any HIGH Security findings      → REQUEST_CHANGES
      3. HIGH count >= high_threshold    → REQUEST_CHANGES
      4. MEDIUM count >= medium_threshold→ REQUEST_CHANGES
      5. Otherwise                       → APPROVE

    Returns:
        {decision: "APPROVE"|"REQUEST_CHANGES", reason: str, blocking_findings: list}
    """
    config = config or {}
    high_threshold = config.get("high_threshold", 3)
    medium_threshold = config.get("medium_threshold", 5)

    critical = [f for f in findings if f.get("severity") == "CRITICAL"]
    high = [f for f in findings if f.get("severity") == "HIGH"]
    medium = [f for f in findings if f.get("severity") == "MEDIUM"]
    high_security = [f for f in high if "Security" in f.get("category", "") or "Secret" in f.get("category", "")]

    blocking: list[dict] = []
    reason_parts: list[str] = []

    if critical:
        blocking.extend(critical)
        reason_parts.append(f"{len(critical)} CRITICAL finding(s) must be resolved before merge")

    if high_security:
        new_blocking = [f for f in high_security if f not in blocking]
        blocking.extend(new_blocking)
        reason_parts.append(f"{len(high_security)} HIGH-severity security finding(s) detected")

    if len(high) >= high_threshold:
        new_blocking = [f for f in high if f not in blocking]
        blocking.extend(new_blocking)
        reason_parts.append(
            f"HIGH finding count ({len(high)}) meets or exceeds threshold ({high_threshold})"
        )

    if len(medium) >= medium_threshold:
        new_blocking = [f for f in medium if f not in blocking]
        blocking.extend(new_blocking)
        reason_parts.append(
            f"MEDIUM finding count ({len(medium)}) meets or exceeds threshold ({medium_threshold})"
        )

    if blocking:
        return {
            "decision": "REQUEST_CHANGES",
            "reason": "; ".join(reason_parts),
            "blocking_findings": [f.get("id", "") for f in blocking],
            "blocking_details": blocking[:10],  # cap for readability
        }
    else:
        return {
            "decision": "APPROVE",
            "reason": "No blocking findings detected. Code passes automated review.",
            "blocking_findings": [],
            "blocking_details": [],
        }


# ---------------------------------------------------------------------------
# Main orchestration entry
# ---------------------------------------------------------------------------

async def run(state: ReviewChangeState) -> dict:
    """
    Orchestrates all agents and returns the complete review result.

    Pipeline:
      1. Diff Agent (sequential — others depend on its metadata)
      2. Style + Security + TestCoverage (concurrent)
      3. Aggregate findings
      4. Fix Suggestion Agent (uses highest severity finding)
      5. Merge Recommendation
    """
    logger.info(f"[{AGENT_NAME}] Orchestrating review {state.review_id}")
    state.update_agent_status(AGENT_NAME, "RUNNING")

    try:
        # Step 1: Diff Agent (sequential)
        logger.info("[Reviewer Manager] Running Diff Agent...")
        diff_result = await diff_agent.run(state)

        # Step 2: Concurrent agents
        logger.info("[Reviewer Manager] Running Style, Security, TestCoverage concurrently...")
        concurrent_results = await asyncio.gather(
            style_agent.run(state),
            security_agent.run(state),
            test_coverage_agent.run(state),
            return_exceptions=True,
        )
        style_result, security_result, coverage_result = concurrent_results

        # Step 3: Collect and aggregate all findings
        raw_findings = [f.to_dict() for f in state.get_all_findings()]
        aggregated = aggregate_agent_findings(raw_findings)

        # Step 4: Identify highest-severity finding
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        sorted_findings = sorted(
            aggregated["deduplicated"],
            key=lambda f: severity_order.get(f.get("severity", "INFO"), 99),
        )
        highest_finding = sorted_findings[0] if sorted_findings else None

        # Step 5: Fix Suggestion Agent
        logger.info("[Reviewer Manager] Running Fix Suggestion Agent...")
        fix_result = await fix_suggestion_agent.run(state, highest_finding)

        # Step 6: Merge Recommendation
        recommendation = calculate_merge_recommendation(aggregated["deduplicated"])

        # Store decision in state
        state.set_metadata("merge_recommendation", recommendation)
        state.set_metadata("aggregated_findings", aggregated)

        state.update_agent_status(AGENT_NAME, "COMPLETED")

        # Build complete result
        complete_result = {
            "review_id": state.review_id,
            "language": state.language,
            "decision": recommendation["decision"],
            "reason": recommendation["reason"],
            "blocking_findings": recommendation["blocking_findings"],
            "summary": {
                "total_findings": aggregated["total"],
                "by_severity": aggregated["counts"],
            },
            "agent_results": {
                "diff": diff_result,
                "style": style_result if not isinstance(style_result, Exception) else {"error": str(style_result)},
                "security": security_result if not isinstance(security_result, Exception) else {"error": str(security_result)},
                "test_coverage": coverage_result if not isinstance(coverage_result, Exception) else {"error": str(coverage_result)},
                "fix_suggestion": fix_result,
            },
            "findings": aggregated["deduplicated"],
        }

        logger.info(
            f"[{AGENT_NAME}] Review complete. Decision: {recommendation['decision']}. "
            f"Total findings: {aggregated['total']}"
        )
        return complete_result

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] Error: {e}")
        state.update_agent_status(AGENT_NAME, "FAILED")
        return {"agent": AGENT_NAME, "status": "FAILED", "error": str(e)}
