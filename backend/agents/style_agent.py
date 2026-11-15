"""
Style Agent: Static analysis for code style and quality issues.
Uses regex and AST-based heuristics — works fully offline.
"""
import re
import logging
from collections import defaultdict
from core.change_state import ReviewChangeState, Finding

logger = logging.getLogger(__name__)

AGENT_NAME = "Style Agent"

# Severity thresholds
LONG_LINE_LIMIT = 120
MAX_ARGS = 5
MAX_INDENT_LEVELS = 4


# ---------------------------------------------------------------------------
# Tool 1: run_style_analysis
# ---------------------------------------------------------------------------

def run_style_analysis(code: str, language: str = "python") -> list[dict]:
    """
    Runs static style analysis on code.
    Returns a list of issue dicts with keys:
        line, severity, category, title, description, evidence, recommendation
    """
    issues: list[dict] = []
    lines = code.splitlines()

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")

        # 1. Very long lines
        if len(line) > LONG_LINE_LIMIT:
            issues.append(
                {
                    "line": lineno,
                    "severity": "LOW",
                    "category": "Style",
                    "title": "Line Too Long",
                    "description": f"Line {lineno} is {len(line)} characters (limit {LONG_LINE_LIMIT}).",
                    "evidence": line[:160] + ("..." if len(line) > 160 else ""),
                    "recommendation": f"Break this line to stay under {LONG_LINE_LIMIT} characters.",
                }
            )

        # 2. TODO / FIXME comments
        if re.search(r"#\s*(TODO|FIXME|HACK|XXX|BUG)\b", line, re.IGNORECASE):
            match = re.search(r"#\s*(TODO|FIXME|HACK|XXX|BUG).*", line, re.IGNORECASE)
            issues.append(
                {
                    "line": lineno,
                    "severity": "LOW",
                    "category": "Maintainability",
                    "title": "Unresolved TODO/FIXME",
                    "description": f"Unresolved annotation at line {lineno}.",
                    "evidence": match.group(0).strip() if match else line.strip(),
                    "recommendation": "Resolve the issue or create a ticket and remove the comment.",
                }
            )

        # 3. Deeply nested code (> MAX_INDENT_LEVELS * 4 spaces)
        indent = len(line) - len(line.lstrip())
        if indent > MAX_INDENT_LEVELS * 4 and line.strip():
            issues.append(
                {
                    "line": lineno,
                    "severity": "MEDIUM",
                    "category": "Complexity",
                    "title": "Excessive Nesting",
                    "description": f"Line {lineno} has {indent // 4} levels of indentation (limit {MAX_INDENT_LEVELS}).",
                    "evidence": line[:160],
                    "recommendation": "Refactor nested logic into helper functions or use early returns.",
                }
            )

    # 4. Functions with too many arguments (Python-specific)
    if language == "python":
        func_def_pattern = re.compile(r"^(\s*)def\s+(\w+)\s*\(([^)]*)\)\s*:", re.MULTILINE)
        for match in func_def_pattern.finditer(code):
            func_name = match.group(2)
            args_str = match.group(3).strip()
            if not args_str:
                args = []
            else:
                # Count args (handle defaults and type annotations roughly)
                args = [a.strip() for a in args_str.split(",") if a.strip()]
            # Strip self/cls
            real_args = [a for a in args if not a.startswith("self") and not a.startswith("cls")]
            if len(real_args) > MAX_ARGS:
                lineno = code[: match.start()].count("\n") + 1
                issues.append(
                    {
                        "line": lineno,
                        "severity": "MEDIUM",
                        "category": "Design",
                        "title": "Too Many Function Arguments",
                        "description": (
                            f"Function '{func_name}' has {len(real_args)} arguments "
                            f"(limit {MAX_ARGS}). Consider using a dataclass or config object."
                        ),
                        "evidence": f"def {func_name}({args_str})",
                        "recommendation": "Group related parameters into a dataclass or dict.",
                    }
                )

        # 5. Missing docstrings on public functions
        func_body_pattern = re.compile(
            r"^(\s*)def\s+((?!_)\w+)\s*\([^)]*\)\s*:(.*?)(?=^\1def\s|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        for match in func_body_pattern.finditer(code):
            func_name = match.group(2)
            body = match.group(3)
            # Look for docstring as first statement
            stripped = body.lstrip()
            has_docstring = stripped.startswith('"""') or stripped.startswith("'''") or stripped.startswith('r"""')
            if not has_docstring:
                lineno = code[: match.start()].count("\n") + 1
                issues.append(
                    {
                        "line": lineno,
                        "severity": "LOW",
                        "category": "Documentation",
                        "title": "Missing Docstring",
                        "description": f"Public function '{func_name}' has no docstring.",
                        "evidence": f"def {func_name}(...)",
                        "recommendation": "Add a docstring describing purpose, parameters, and return value.",
                    }
                )

        # 6. Naming convention violations (non-snake_case function/variable names)
        camel_case_pattern = re.compile(r"\bdef\s+([a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*)\s*\(")
        for match in camel_case_pattern.finditer(code):
            func_name = match.group(1)
            lineno = code[: match.start()].count("\n") + 1
            issues.append(
                {
                    "line": lineno,
                    "severity": "LOW",
                    "category": "Naming",
                    "title": "Non-snake_case Function Name",
                    "description": f"Function '{func_name}' uses camelCase instead of snake_case.",
                    "evidence": f"def {func_name}(...)",
                    "recommendation": f"Rename to '{_to_snake_case(func_name)}'.",
                }
            )

    return issues


def _to_snake_case(name: str) -> str:
    """Convert camelCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


# ---------------------------------------------------------------------------
# Tool 2: detect_code_duplication
# ---------------------------------------------------------------------------

def detect_code_duplication(code: str, min_block_lines: int = 3) -> list[dict]:
    """
    Tool 2: Find duplicated blocks of min_block_lines or more lines.
    Returns list of dicts with: block, occurrences (list of starting line numbers), severity
    """
    lines = code.splitlines()
    n = len(lines)
    duplicates: list[dict] = []

    # Build a map from (normalized block tuple) → list of starting line indices
    block_map: dict[tuple, list[int]] = defaultdict(list)

    for i in range(n - min_block_lines + 1):
        block_lines = lines[i : i + min_block_lines]
        # Normalize: strip whitespace for comparison, skip blank/comment-only blocks
        normalized = tuple(l.strip() for l in block_lines if l.strip() and not l.strip().startswith("#"))
        if len(normalized) >= min_block_lines:
            block_map[normalized].append(i + 1)  # 1-indexed

    seen: set[tuple] = set()
    for block_key, occurrences in block_map.items():
        if len(occurrences) > 1 and block_key not in seen:
            seen.add(block_key)
            duplicates.append(
                {
                    "block": "\n".join(block_key),
                    "occurrences": occurrences,
                    "count": len(occurrences),
                    "severity": "MEDIUM" if len(occurrences) >= 3 else "LOW",
                    "description": (
                        f"Duplicate code block ({min_block_lines}+ lines) found "
                        f"{len(occurrences)} times at lines {occurrences}."
                    ),
                }
            )

    # Sort by count descending
    duplicates.sort(key=lambda x: -x["count"])
    return duplicates


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

async def run(state: ReviewChangeState) -> dict:
    """Main agent entry point for style analysis."""
    logger.info(f"[{AGENT_NAME}] Starting analysis for review {state.review_id}")
    state.update_agent_status(AGENT_NAME, "RUNNING")

    try:
        code = state.submitted_content
        language = state.language

        # Run both tools
        style_issues = run_style_analysis(code, language)
        duplication_issues = detect_code_duplication(code)

        findings_added = 0

        # Convert style issues to Findings
        for issue in style_issues:
            finding = Finding(
                agent=AGENT_NAME,
                file=state.get_metadata("diff_summary", {}).get("files_changed", ["unknown"])[0]
                if state.get_metadata("diff_summary") else "submitted_code",
                line=issue.get("line"),
                severity=issue["severity"],
                category=issue["category"],
                title=issue["title"],
                description=issue["description"],
                evidence=issue.get("evidence", ""),
                recommendation=issue.get("recommendation", ""),
            )
            state.add_finding(finding)
            findings_added += 1

        # Convert duplication issues to Findings
        for dup in duplication_issues:
            finding = Finding(
                agent=AGENT_NAME,
                file="submitted_code",
                line=dup["occurrences"][0] if dup["occurrences"] else None,
                severity=dup["severity"],
                category="Duplication",
                title="Duplicate Code Block Detected",
                description=dup["description"],
                evidence=dup["block"][:300],
                recommendation="Extract duplicated logic into a shared function or class.",
            )
            state.add_finding(finding)
            findings_added += 1

        state.update_agent_status(AGENT_NAME, "COMPLETED")
        logger.info(f"[{AGENT_NAME}] Completed. {findings_added} findings.")

        return {
            "agent": AGENT_NAME,
            "status": "COMPLETED",
            "findings_count": findings_added,
            "style_issues": len(style_issues),
            "duplication_issues": len(duplication_issues),
        }

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] Error: {e}")
        state.update_agent_status(AGENT_NAME, "FAILED")
        return {"agent": AGENT_NAME, "status": "FAILED", "error": str(e)}
