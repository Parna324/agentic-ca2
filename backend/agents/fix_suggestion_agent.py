"""
Fix Suggestion Agent: Generates before/after fix patches for the highest-severity finding.
Advisory only — never modifies the original code.
"""
import ast
import re
import logging
from core.change_state import ReviewChangeState, Finding

logger = logging.getLogger(__name__)

AGENT_NAME = "Fix Suggestion Agent"

# ---------------------------------------------------------------------------
# Fix templates keyed by title keywords
# ---------------------------------------------------------------------------

FIX_TEMPLATES: list[tuple[str, dict]] = [
    # SQL Injection
    (
        "sql injection",
        {
            "explanation": (
                "SQL injection occurs when user input is embedded directly into SQL queries. "
                "Use parameterized queries so the database driver handles escaping safely."
            ),
            "before_pattern": r'(execute|query)\s*\(\s*f["\'](.+?)["\']',
            "before_example": 'cursor.execute(f"SELECT * FROM users WHERE id={user_id}")',
            "after_example": 'cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))',
            "expected_result": "Database engine safely escapes user input, preventing SQL injection.",
        },
    ),
    # Hardcoded Secret / Password / Token / API Key
    (
        "hardcoded secret",
        {
            "explanation": (
                "Hardcoded credentials in source code are exposed to anyone with repository access. "
                "Use environment variables or a secrets manager instead."
            ),
            "before_example": 'PASSWORD = "admin123"',
            "after_example": 'import os\nPASSWORD = os.environ.get("APP_PASSWORD")\nassert PASSWORD, "APP_PASSWORD env var is required"',
            "expected_result": "Credentials are stored securely outside the codebase.",
        },
    ),
    (
        "hardcoded password",
        {
            "explanation": (
                "Hardcoded passwords in source code are exposed to anyone with repository access. "
                "Use environment variables or a secrets manager instead."
            ),
            "before_example": 'password = "supersecret"',
            "after_example": 'import os\npassword = os.environ.get("DB_PASSWORD")\nassert password, "DB_PASSWORD env var is required"',
            "expected_result": "Credentials are stored securely outside the codebase.",
        },
    ),
    # eval usage
    (
        "eval()",
        {
            "explanation": (
                "eval() executes arbitrary Python code and is a critical security vulnerability "
                "when processing untrusted input. Use ast.literal_eval() for data, or json.loads() for JSON."
            ),
            "before_example": 'result = eval(user_input)',
            "after_example": (
                "import ast\n"
                "import json\n"
                "# For Python literals (dict, list, str, int, float, bool, None):\n"
                "result = ast.literal_eval(user_input)\n"
                "# For JSON data:\n"
                "result = json.loads(user_input)"
            ),
            "expected_result": "Only safe literal values can be parsed; arbitrary code execution is prevented.",
        },
    ),
    # exec usage
    (
        "exec()",
        {
            "explanation": (
                "exec() executes arbitrary Python code and must never be used with untrusted input."
            ),
            "before_example": 'exec(user_code)',
            "after_example": (
                "# Refactor to avoid exec. If dynamic behaviour is needed, "
                "use importlib or a predefined dispatch map:\n"
                "ALLOWED_ACTIONS = {'action_a': do_a, 'action_b': do_b}\n"
                "func = ALLOWED_ACTIONS.get(user_input)\n"
                "if func:\n"
                "    func()"
            ),
            "expected_result": "Only predefined, safe code paths can be executed.",
        },
    ),
    # subprocess shell=True
    (
        "subprocess",
        {
            "explanation": (
                "subprocess with shell=True passes the command to the OS shell, enabling "
                "command injection if any argument contains shell metacharacters. "
                "Use shell=False with a list of arguments."
            ),
            "before_example": 'subprocess.run(f"convert {filename} output.pdf", shell=True)',
            "after_example": (
                "import shlex\n"
                "# Pass arguments as a list — no shell interpretation:\n"
                "subprocess.run(['convert', filename, 'output.pdf'], shell=False, check=True)"
            ),
            "expected_result": "Arguments are passed directly to the program; shell metacharacters are not interpreted.",
        },
    ),
    # pickle.loads
    (
        "pickle",
        {
            "explanation": (
                "pickle.loads() can execute arbitrary code during deserialization when given "
                "malicious data. Use json.loads() for data exchange, or restrict pickle to "
                "trusted, internal-only data."
            ),
            "before_example": 'data = pickle.loads(raw_bytes)',
            "after_example": (
                "import json\n"
                "# For JSON-serializable data:\n"
                "data = json.loads(raw_bytes.decode('utf-8'))\n\n"
                "# If pickle is unavoidable (internal use only), verify HMAC before loading:\n"
                "import hmac, hashlib\n"
                "expected_mac = hmac.new(SECRET_KEY, raw_bytes, hashlib.sha256).digest()\n"
                "if not hmac.compare_digest(received_mac, expected_mac):\n"
                "    raise ValueError('Data integrity check failed')\n"
                "data = pickle.loads(raw_bytes)"
            ),
            "expected_result": "Deserialization is safe; arbitrary code execution is prevented.",
        },
    ),
    # Weak hashing MD5 / SHA1
    (
        "weak hashing",
        {
            "explanation": (
                "MD5 and SHA-1 are cryptographically broken and must not be used for passwords. "
                "Use hashlib.sha256 with a unique salt, or ideally bcrypt/argon2 via a dedicated library."
            ),
            "before_example": 'hashed = hashlib.md5(password.encode()).hexdigest()',
            "after_example": (
                "import hashlib, os\n"
                "# Option A: SHA-256 with salt (acceptable for non-password data):\n"
                "salt = os.urandom(32)\n"
                "hashed = hashlib.sha256(salt + password.encode()).hexdigest()\n\n"
                "# Option B (recommended for passwords): use bcrypt\n"
                "import bcrypt\n"
                "hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())"
            ),
            "expected_result": "Password hashing is resistant to brute-force and rainbow-table attacks.",
        },
    ),
]


def _find_template(title: str) -> dict | None:
    """Match a finding title to the best fix template."""
    title_lower = title.lower()
    for keyword, template in FIX_TEMPLATES:
        if keyword in title_lower:
            return template
    return None


def _extract_code_context(code: str, line: int | None, context_lines: int = 10) -> str:
    """Return a snippet of code around the given line number."""
    if not line:
        return code[:500]
    lines = code.splitlines()
    start = max(0, line - 1 - context_lines // 2)
    end = min(len(lines), line - 1 + context_lines // 2)
    return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# Tool 1: generate_fix_patch
# ---------------------------------------------------------------------------

def generate_fix_patch(finding: dict, code_context: str, language: str = "python") -> dict:
    """
    Tool 1: Generate a before/after advisory patch for a finding.
    NEVER modifies original code — this is advisory only.

    Returns:
        {
            before_code: str,
            after_code: str,
            explanation: str,
            expected_result: str,
            advisory: True,   ← always set
        }
    """
    title = finding.get("title", "")
    template = _find_template(title)

    if template:
        # Try to extract actual code snippet for the 'before' from context + evidence
        evidence = finding.get("evidence", "")
        before_code = evidence if evidence else template.get("before_example", "# (see finding evidence)")
        after_code = template.get("after_example", "# No automatic fix available.")
        explanation = template.get("explanation", "See finding description.")
        expected_result = template.get("expected_result", "Vulnerability is eliminated.")
    else:
        before_code = finding.get("evidence", "# See finding at line " + str(finding.get("line", "?")))
        after_code = "# No specific fix template available. Refer to the recommendation below."
        explanation = finding.get("description", "See finding description.")
        expected_result = finding.get("recommendation", "Follow secure coding practices.")

    return {
        "advisory": True,
        "finding_id": finding.get("id", ""),
        "finding_title": title,
        "language": language,
        "before_code": before_code,
        "after_code": after_code,
        "explanation": explanation,
        "expected_result": expected_result,
        "note": "This patch is ADVISORY ONLY. Do not apply automatically without human review.",
    }


# ---------------------------------------------------------------------------
# Tool 2: validate_patch_syntax
# ---------------------------------------------------------------------------

def validate_patch_syntax(code: str, language: str = "python") -> dict:
    """
    Tool 2: Validate that a suggested patch has valid syntax.

    For Python: uses ast.parse().
    For other languages: basic heuristic checks.

    Returns:
        {valid: bool, error: str or None}
    """
    if language == "python":
        try:
            ast.parse(code)
            return {"valid": True, "error": None}
        except SyntaxError as e:
            return {"valid": False, "error": f"SyntaxError at line {e.lineno}: {e.msg}"}
        except Exception as e:
            return {"valid": False, "error": str(e)}
    else:
        # Basic heuristics for JS/TS: balanced braces
        if language in ("javascript", "typescript"):
            opens = code.count("{")
            closes = code.count("}")
            if opens != closes:
                return {
                    "valid": False,
                    "error": f"Unbalanced braces: {opens} open, {closes} close.",
                }
        return {"valid": True, "error": None}


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

async def run(state: ReviewChangeState, highest_severity_finding: dict | None = None) -> dict:
    """
    Main agent entry point.
    Generates a fix patch for the highest-severity finding.
    """
    logger.info(f"[{AGENT_NAME}] Starting for review {state.review_id}")
    state.update_agent_status(AGENT_NAME, "RUNNING")

    try:
        if not highest_severity_finding:
            # Try to pick one from state findings
            findings = state.get_all_findings()
            severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
            sorted_findings = sorted(
                findings,
                key=lambda f: severity_order.get(f.severity, 99),
            )
            if sorted_findings:
                highest_severity_finding = sorted_findings[0].to_dict()

        if not highest_severity_finding:
            state.update_agent_status(AGENT_NAME, "COMPLETED")
            return {
                "agent": AGENT_NAME,
                "status": "COMPLETED",
                "patch": None,
                "note": "No findings to generate a fix for.",
            }

        # Extract code context around the finding
        code_context = _extract_code_context(
            state.submitted_content,
            highest_severity_finding.get("line"),
        )

        patch = generate_fix_patch(highest_severity_finding, code_context, state.language)
        syntax_check = validate_patch_syntax(patch["after_code"], state.language)

        # Store patch in shared state
        state.set_metadata("fix_suggestion", {
            "finding": highest_severity_finding,
            "patch": patch,
            "syntax_valid": syntax_check["valid"],
            "syntax_error": syntax_check.get("error"),
        })

        # Add advisory finding
        fix_finding = Finding(
            agent=AGENT_NAME,
            file=highest_severity_finding.get("file", "submitted_code"),
            line=highest_severity_finding.get("line"),
            severity="INFO",
            category="Fix Suggestion",
            title=f"Fix Available: {highest_severity_finding.get('title', 'Unknown')}",
            description=(
                f"Advisory fix patch generated for [{highest_severity_finding.get('severity')}] "
                f"'{highest_severity_finding.get('title')}'. "
                f"Syntax valid: {syntax_check['valid']}."
            ),
            evidence=patch["after_code"][:500],
            recommendation=patch["explanation"],
        )
        state.add_finding(fix_finding)

        state.update_agent_status(AGENT_NAME, "COMPLETED")
        logger.info(f"[{AGENT_NAME}] Completed. Patch generated for: {highest_severity_finding.get('title')}")

        return {
            "agent": AGENT_NAME,
            "status": "COMPLETED",
            "patch": patch,
            "syntax_check": syntax_check,
        }

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] Error: {e}")
        state.update_agent_status(AGENT_NAME, "FAILED")
        return {"agent": AGENT_NAME, "status": "FAILED", "error": str(e)}
