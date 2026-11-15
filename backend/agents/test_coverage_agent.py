"""
Test Coverage Agent: Estimates test coverage from code and diff.
Works fully offline — no test runner required.
"""
import re
import logging
from core.change_state import ReviewChangeState, Finding

logger = logging.getLogger(__name__)

AGENT_NAME = "Test Coverage Agent"


# ---------------------------------------------------------------------------
# Tool 1: discover_test_files
# ---------------------------------------------------------------------------

def discover_test_files(code: str, file_list: list[str] | None = None) -> dict:
    """
    Tool 1: Discover test functions and identify untested functions.

    - Looks for test_ prefix functions in the code.
    - Identifies functions that are defined but have no corresponding test_ function.
    - Checks if test files appear to exist based on naming patterns in file_list.

    Returns:
        {
            test_functions: list[str],
            source_functions: list[str],
            untested_functions: list[str],
            test_files_detected: list[str],
            has_test_coverage: bool,
        }
    """
    file_list = file_list or []

    # Extract all function definitions
    all_func_pattern = re.compile(r"^(?:async\s+)?def\s+(\w+)\s*\(", re.MULTILINE)
    all_funcs = all_func_pattern.findall(code)

    # Separate test functions from source functions
    test_funcs = [f for f in all_funcs if f.startswith("test_")]
    source_funcs = [f for f in all_funcs if not f.startswith("test_") and not f.startswith("_")]

    # Determine which source functions have a corresponding test
    tested_set = set()
    for tf in test_funcs:
        # test_foo → foo, test_foo_bar → foo or foo_bar
        candidate = tf[len("test_"):]
        tested_set.add(candidate)
        # Also match partial: test_get_user_by_id → get_user, get_user_by_id, etc.
        parts = candidate.split("_")
        for i in range(1, len(parts) + 1):
            tested_set.add("_".join(parts[:i]))

    untested = [f for f in source_funcs if f not in tested_set]

    # Detect test files from file_list
    test_file_patterns = [
        re.compile(r"test_.*\.py$"),
        re.compile(r".*_test\.py$"),
        re.compile(r"spec\.py$"),
        re.compile(r".*\.spec\.(js|ts)$"),
        re.compile(r".*\.test\.(js|ts)$"),
    ]
    test_files_detected = [
        f for f in file_list
        if any(p.search(f) for p in test_file_patterns)
    ]

    return {
        "test_functions": test_funcs,
        "source_functions": source_funcs,
        "untested_functions": untested,
        "test_files_detected": test_files_detected,
        "has_test_coverage": len(test_funcs) > 0 or len(test_files_detected) > 0,
    }


# ---------------------------------------------------------------------------
# Tool 2: analyze_test_coverage
# ---------------------------------------------------------------------------

def analyze_test_coverage(code: str, diff_text: str, language: str = "python") -> dict:
    """
    Tool 2: Estimate test coverage from code and diff.

    NOTE: This is ESTIMATED coverage based on static analysis only.
    It is NOT measured by a test runner (e.g. pytest-cov, nyc, coverage.py).
    Actual runtime coverage may differ significantly.

    Returns:
        {
            estimated: True,  ← always set to indicate this is not measured
            coverage_percent: float,
            total_functions: int,
            tested_functions: int,
            untested_functions: list[str],
            new_functions_without_tests: list[str],
            assessment: str,
        }
    """
    discovery = discover_test_files(code, [])

    total = len(discovery["source_functions"])
    untested = discovery["untested_functions"]
    tested_count = total - len(untested)

    coverage_pct = (tested_count / total * 100) if total > 0 else 0.0

    # Identify NEW functions added in the diff (lines starting with +)
    new_funcs: list[str] = []
    if diff_text:
        added_lines = [l[1:] for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++")]
        added_code = "\n".join(added_lines)
        all_new = re.findall(r"^(?:async\s+)?def\s+(\w+)\s*\(", added_code, re.MULTILINE)
        new_funcs = [f for f in all_new if not f.startswith("test_") and not f.startswith("_")]

    new_without_tests = [f for f in new_funcs if f in untested]

    if coverage_pct >= 80:
        assessment = "Good coverage — most functions appear to have tests."
    elif coverage_pct >= 50:
        assessment = "Moderate coverage — several functions lack tests."
    elif total == 0:
        assessment = "No source functions detected."
    else:
        assessment = "Low coverage — many functions lack corresponding tests."

    return {
        "estimated": True,
        "note": "ESTIMATED via static analysis only. Run pytest-cov for actual coverage.",
        "coverage_percent": round(coverage_pct, 1),
        "total_functions": total,
        "tested_functions": tested_count,
        "untested_functions": untested,
        "new_functions_in_diff": new_funcs,
        "new_functions_without_tests": new_without_tests,
        "assessment": assessment,
    }


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

async def run(state: ReviewChangeState) -> dict:
    """Main agent entry point for test coverage estimation."""
    logger.info(f"[{AGENT_NAME}] Starting analysis for review {state.review_id}")
    state.update_agent_status(AGENT_NAME, "RUNNING")

    try:
        code = state.submitted_content
        language = state.language
        diff_text = code  # submitted content may be a diff

        diff_summary = state.get_metadata("diff_summary", {})
        file_list = diff_summary.get("files_changed", [])
        primary_file = file_list[0] if file_list else "submitted_code"

        # Run analysis
        discovery = discover_test_files(code, file_list)
        coverage = analyze_test_coverage(code, diff_text, language)

        findings_added = 0

        # Finding: overall coverage estimate
        severity = (
            "HIGH" if coverage["coverage_percent"] < 30 and coverage["total_functions"] > 0
            else "MEDIUM" if coverage["coverage_percent"] < 60 and coverage["total_functions"] > 0
            else "INFO"
        )
        overall_finding = Finding(
            agent=AGENT_NAME,
            file=primary_file,
            severity=severity,
            category="Test Coverage",
            title="Estimated Test Coverage",
            description=(
                f"ESTIMATED coverage: {coverage['coverage_percent']}% "
                f"({coverage['tested_functions']}/{coverage['total_functions']} functions). "
                f"{coverage['assessment']} "
                "⚠ This is a static estimate only — run pytest-cov for actual coverage."
            ),
            evidence=(
                f"Untested functions: {', '.join(coverage['untested_functions'][:10]) or 'none'}"
            ),
            recommendation="Add unit tests for all public functions. Aim for >80% coverage.",
        )
        state.add_finding(overall_finding)
        findings_added += 1

        # Finding: new functions in diff without tests
        if coverage["new_functions_without_tests"]:
            new_finding = Finding(
                agent=AGENT_NAME,
                file=primary_file,
                severity="MEDIUM",
                category="Test Coverage",
                title="New Functions Without Tests",
                description=(
                    f"{len(coverage['new_functions_without_tests'])} new function(s) in this change "
                    "appear to have no corresponding test functions: "
                    f"{', '.join(coverage['new_functions_without_tests'][:10])}."
                ),
                evidence=f"New untested: {', '.join(coverage['new_functions_without_tests'][:10])}",
                recommendation=(
                    "Write tests for all new functions before merging. "
                    "Consider test-driven development (TDD) for future changes."
                ),
            )
            state.add_finding(new_finding)
            findings_added += 1

        # Finding: no test files at all
        if not discovery["has_test_coverage"] and coverage["total_functions"] > 0:
            no_test_finding = Finding(
                agent=AGENT_NAME,
                file=primary_file,
                severity="HIGH",
                category="Test Coverage",
                title="No Test Files Detected",
                description=(
                    "No test functions (test_* prefix) or test files were found in the submission. "
                    f"{coverage['total_functions']} source function(s) are unverified."
                ),
                evidence="No functions with test_ prefix found.",
                recommendation=(
                    "Create a test file (e.g. test_<module>.py) using pytest. "
                    "Add at least one test per public function."
                ),
            )
            state.add_finding(no_test_finding)
            findings_added += 1

        state.update_agent_status(AGENT_NAME, "COMPLETED")
        logger.info(f"[{AGENT_NAME}] Completed. {findings_added} findings. Coverage est: {coverage['coverage_percent']}%")

        return {
            "agent": AGENT_NAME,
            "status": "COMPLETED",
            "findings_count": findings_added,
            "coverage_estimate": coverage,
        }

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] Error: {e}")
        state.update_agent_status(AGENT_NAME, "FAILED")
        return {"agent": AGENT_NAME, "status": "FAILED", "error": str(e)}
