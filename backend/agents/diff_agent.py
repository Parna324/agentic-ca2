"""
Diff Agent: Parses git diffs and analyzes changed files.
Produces structured change metadata for other agents.
"""
import re
import logging
from core.change_state import ReviewChangeState, Finding

logger = logging.getLogger(__name__)

AGENT_NAME = "Diff Agent"


def parse_git_diff(diff_text: str) -> dict:
    """
    Tool 1: Parse a git diff and extract structured metadata.
    Returns: files_changed, additions, deletions, hunks, modified_lines
    """
    result = {
        "files_changed": [],
        "total_additions": 0,
        "total_deletions": 0,
        "hunks": [],
    }

    current_file = None
    for line in diff_text.splitlines():
        if line.startswith("--- a/") or line.startswith("--- /dev/null"):
            pass
        elif line.startswith("+++ b/"):
            current_file = line[6:].strip()
            if current_file not in result["files_changed"]:
                result["files_changed"].append(current_file)
        elif line.startswith("+++ /dev/null"):
            current_file = "(deleted)"
        elif line.startswith("@@"):
            # Parse hunk header like @@ -1,5 +1,10 @@
            match = re.search(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if match and current_file:
                result["hunks"].append(
                    {
                        "file": current_file,
                        "old_start": int(match.group(1)),
                        "old_count": int(match.group(2) or 1),
                        "new_start": int(match.group(3)),
                        "new_count": int(match.group(4) or 1),
                    }
                )
        elif line.startswith("+") and not line.startswith("+++"):
            result["total_additions"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            result["total_deletions"] += 1

    return result


def analyze_changed_files(diff_text: str, language: str = "python") -> dict:
    """
    Tool 2: Analyze the changed files for functions and classes.
    Returns: functions_modified, classes_modified, complexity_indicators
    """
    result = {
        "functions_modified": [],
        "classes_modified": [],
        "imports_added": [],
        "language": language,
        "complexity_indicators": [],
    }

    added_lines = []
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])

    added_code = "\n".join(added_lines)

    if language == "python":
        func_pattern = re.compile(r"^def\s+(\w+)\s*\(", re.MULTILINE)
        class_pattern = re.compile(r"^class\s+(\w+)", re.MULTILINE)
        import_pattern = re.compile(r"^(?:import|from)\s+(\S+)", re.MULTILINE)

        result["functions_modified"] = func_pattern.findall(added_code)
        result["classes_modified"] = class_pattern.findall(added_code)
        result["imports_added"] = import_pattern.findall(added_code)

        # Complexity: nested loops and long functions
        if added_code.count("for ") + added_code.count("while ") > 3:
            result["complexity_indicators"].append("Multiple loops detected")
        if any(len(line) > 120 for line in added_lines):
            result["complexity_indicators"].append("Long lines detected (>120 chars)")

    elif language in ("javascript", "typescript"):
        func_pattern = re.compile(
            r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()", re.MULTILINE
        )
        matches = func_pattern.findall(added_code)
        result["functions_modified"] = [m[0] or m[1] for m in matches if m[0] or m[1]]

    return result


async def run(state: ReviewChangeState) -> dict:
    """
    Main agent entry point. Analyzes the submitted diff/code and
    updates the shared change state with metadata.
    """
    logger.info(f"[{AGENT_NAME}] Starting analysis for review {state.review_id}")
    state.update_agent_status(AGENT_NAME, "RUNNING")

    try:
        content = state.submitted_content
        language = state.language

        # Run both tools
        diff_meta = parse_git_diff(content)
        file_analysis = analyze_changed_files(content, language)

        # Store analysis results in shared state for other agents
        analysis_result = {**diff_meta, **file_analysis}
        state.diff_analysis = analysis_result
        state.set_metadata(
            "diff_summary",
            {
                "files_changed": diff_meta["files_changed"],
                "total_additions": diff_meta["total_additions"],
                "total_deletions": diff_meta["total_deletions"],
                "functions_modified": file_analysis["functions_modified"],
                "classes_modified": file_analysis["classes_modified"],
                "imports_added": file_analysis["imports_added"],
            },
        )

        # Create an informational summary finding
        if diff_meta["files_changed"]:
            files_str = ", ".join(diff_meta["files_changed"][:5])
            finding = Finding(
                agent=AGENT_NAME,
                file=diff_meta["files_changed"][0] if diff_meta["files_changed"] else "unknown",
                severity="INFO",
                category="Diff Analysis",
                title="Change Summary",
                description=(
                    f"Changed {len(diff_meta['files_changed'])} file(s): {files_str}. "
                    f"+{diff_meta['total_additions']} additions, -{diff_meta['total_deletions']} deletions."
                ),
                recommendation="Review all changed files for correctness.",
                evidence=f"Functions modified: {', '.join(file_analysis['functions_modified']) or 'none'}",
            )
            state.add_finding(finding)
        else:
            # No diff markers — treat as plain code submission
            lines = content.splitlines()
            finding = Finding(
                agent=AGENT_NAME,
                file="submitted_code",
                severity="INFO",
                category="Diff Analysis",
                title="Plain Code Submission",
                description=(
                    f"No git diff markers detected. Treating as plain code submission "
                    f"({len(lines)} lines, language={language})."
                ),
                recommendation="Submit as a git diff for file-level change tracking.",
                evidence=f"First 3 lines: {chr(10).join(lines[:3])}",
            )
            state.add_finding(finding)

        state.update_agent_status(AGENT_NAME, "COMPLETED")
        logger.info(f"[{AGENT_NAME}] Completed. Files: {len(diff_meta['files_changed'])}")

        return {
            "agent": AGENT_NAME,
            "status": "COMPLETED",
            "result": analysis_result,
        }

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] Error: {e}")
        state.update_agent_status(AGENT_NAME, "FAILED")
        return {"agent": AGENT_NAME, "status": "FAILED", "error": str(e)}
