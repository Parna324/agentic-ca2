"""
Security Agent: Detects secrets, vulnerabilities, and insecure patterns.
Works fully offline via regex pattern matching.
"""
import re
import logging
from core.change_state import ReviewChangeState, Finding

logger = logging.getLogger(__name__)

AGENT_NAME = "Security Agent"

# ---------------------------------------------------------------------------
# Secret patterns — (name, regex, severity)
# ---------------------------------------------------------------------------
SECRET_PATTERNS = [
    (
        "Hardcoded Password",
        re.compile(r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{3,}["\']'),
        "CRITICAL",
    ),
    (
        "Hardcoded Secret",
        re.compile(r'(?i)secret\s*=\s*["\'][^"\']{3,}["\']'),
        "CRITICAL",
    ),
    (
        "Hardcoded Token",
        re.compile(r'(?i)token\s*=\s*["\'][^"\']{6,}["\']'),
        "CRITICAL",
    ),
    (
        "API Key Assignment",
        re.compile(r'(?i)api[_\-]?key\s*=\s*["\'][A-Za-z0-9\-_]{10,}["\']'),
        "CRITICAL",
    ),
    (
        "OpenAI Secret Key",
        re.compile(r'sk-[A-Za-z0-9]{20,}'),
        "CRITICAL",
    ),
    (
        "Bearer Token",
        re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]{20,}'),
        "HIGH",
    ),
    (
        "Database URL with Credentials",
        re.compile(r'(?i)(postgresql|mysql|mongodb|redis)://[^:]+:[^@]+@'),
        "CRITICAL",
    ),
    (
        "RSA Private Key",
        re.compile(r'-----BEGIN RSA PRIVATE KEY-----'),
        "CRITICAL",
    ),
    (
        "Private Key",
        re.compile(r'-----BEGIN PRIVATE KEY-----'),
        "CRITICAL",
    ),
    (
        "AWS Access Key ID",
        re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
        "CRITICAL",
    ),
    (
        "AWS Secret Access Key",
        re.compile(r'(?i)AWS_SECRET_ACCESS_KEY\s*=\s*["\']?[A-Za-z0-9/+]{20,}["\']?'),
        "CRITICAL",
    ),
]

# ---------------------------------------------------------------------------
# Vulnerability patterns — (name, regex, severity, recommendation)
# ---------------------------------------------------------------------------
VULN_PATTERNS = [
    (
        "SQL Injection via f-string",
        re.compile(
            r'(?i)(execute|query|raw)\s*\(\s*f["\'].*?(SELECT|INSERT|UPDATE|DELETE|DROP)',
            re.DOTALL,
        ),
        "CRITICAL",
        "Use parameterized queries: cursor.execute('SELECT ... WHERE id=?', (user_id,))",
    ),
    (
        "SQL Injection via % formatting",
        re.compile(
            r'(?i)(execute|query|raw)\s*\(\s*["\'].*?(SELECT|INSERT|UPDATE|DELETE|DROP).*?%\s*\(',
            re.DOTALL,
        ),
        "CRITICAL",
        "Use parameterized queries instead of string formatting.",
    ),
    (
        "SQL Injection via .format()",
        re.compile(
            r'(?i)["\'].*?(SELECT|INSERT|UPDATE|DELETE|DROP).*?["\']\.format\s*\(',
            re.DOTALL,
        ),
        "CRITICAL",
        "Use parameterized queries. Never format SQL strings with user input.",
    ),
    (
        "Command Injection — subprocess shell=True",
        re.compile(r'subprocess\.(run|call|Popen|check_output)\s*\([^)]*shell\s*=\s*True'),
        "HIGH",
        "Use shell=False with a list of arguments: subprocess.run(['cmd', arg], shell=False)",
    ),
    (
        "eval() Usage",
        re.compile(r'\beval\s*\('),
        "CRITICAL",
        "Replace eval() with ast.literal_eval() for data, or json.loads() for JSON.",
    ),
    (
        "exec() Usage",
        re.compile(r'\bexec\s*\('),
        "CRITICAL",
        "Avoid exec(). Refactor to use importlib or subprocess with controlled inputs.",
    ),
    (
        "pickle.loads — Insecure Deserialization",
        re.compile(r'\bpickle\.loads?\s*\('),
        "CRITICAL",
        "Replace pickle with json.loads() or a safe serialization library.",
    ),
    (
        "Weak Hashing — MD5",
        re.compile(r'\bhashlib\.md5\s*\('),
        "HIGH",
        "Use hashlib.sha256 with a unique salt for password hashing, or use bcrypt/argon2.",
    ),
    (
        "Weak Hashing — SHA1",
        re.compile(r'\bhashlib\.sha1\s*\('),
        "HIGH",
        "SHA-1 is deprecated for cryptographic use. Use sha256 or stronger.",
    ),
    (
        "os.system() Usage",
        re.compile(r'\bos\.system\s*\('),
        "HIGH",
        "Use subprocess.run() with a list of arguments and shell=False.",
    ),
    (
        "XML Parsing without defusedxml",
        re.compile(r'\b(?:xml\.etree|xml\.dom|minidom|ElementTree)\.parse\s*\('),
        "MEDIUM",
        "Use defusedxml to prevent XXE attacks: import defusedxml.ElementTree as ET.",
    ),
    (
        "Hardcoded Internal IP",
        re.compile(r'(?:http://|https://|["\'])(?:192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)'),
        "MEDIUM",
        "Move internal service URLs to environment variables.",
    ),
]


def _redact(match_text: str) -> str:
    """Replace the value portion of a secret with [REDACTED]."""
    # Try to redact after = sign
    redacted = re.sub(r'(=\s*["\']?)[^"\')\s]{3,}(["\']?)', r'\1[REDACTED]\2', match_text)
    if redacted == match_text:
        # Fallback: redact last 60% of string
        pivot = max(4, len(match_text) // 2)
        redacted = match_text[:pivot] + "[REDACTED]"
    return redacted


def scan_secrets(code: str) -> list[dict]:
    """
    Tool 1: Scan code for hardcoded secrets and credentials.
    Secrets are NEVER included in evidence — replaced with [REDACTED].
    Returns list of issue dicts.
    """
    issues: list[dict] = []
    lines = code.splitlines()

    for lineno, line in enumerate(lines, start=1):
        for secret_name, pattern, severity in SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                issues.append(
                    {
                        "line": lineno,
                        "severity": severity,
                        "category": "Secret Exposure",
                        "title": f"Hardcoded Secret: {secret_name}",
                        "description": (
                            f"Potential hardcoded secret detected at line {lineno}: {secret_name}. "
                            "Hardcoded credentials expose systems to unauthorized access."
                        ),
                        "evidence": _redact(match.group(0)),
                        "recommendation": (
                            "Move credentials to environment variables: "
                            "os.environ.get('SECRET_NAME') or use a secrets manager."
                        ),
                    }
                )
                break  # One secret per line is enough

    return issues


def detect_security_vulnerabilities(code: str, language: str = "python") -> list[dict]:
    """
    Tool 2: Detect security vulnerability patterns in code.
    Returns list of issue dicts with line numbers.
    """
    issues: list[dict] = []
    lines = code.splitlines()

    for vuln_name, pattern, severity, recommendation in VULN_PATTERNS:
        # Search line-by-line for accurate line numbers
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                issues.append(
                    {
                        "line": lineno,
                        "severity": severity,
                        "category": "Security Vulnerability",
                        "title": vuln_name,
                        "description": (
                            f"Potential {vuln_name} detected at line {lineno}. "
                            "This pattern is associated with exploitable security vulnerabilities."
                        ),
                        "evidence": line.strip()[:200],
                        "recommendation": recommendation,
                    }
                )
        else:
            # Also search multi-line for patterns that span lines (e.g., long SQL strings)
            full_match = pattern.search(code)
            if full_match:
                # Compute line number from character offset
                lineno = code[: full_match.start()].count("\n") + 1
                # Avoid duplicate if already found line-by-line
                already = any(
                    i["title"] == vuln_name and i["line"] == lineno for i in issues
                )
                if not already:
                    issues.append(
                        {
                            "line": lineno,
                            "severity": severity,
                            "category": "Security Vulnerability",
                            "title": vuln_name,
                            "description": (
                                f"Potential {vuln_name} detected near line {lineno}. "
                                "This pattern is associated with exploitable security vulnerabilities."
                            ),
                            "evidence": full_match.group(0)[:200],
                            "recommendation": recommendation,
                        }
                    )

    return issues


async def run(state: ReviewChangeState) -> dict:
    """Main agent entry point for security analysis."""
    logger.info(f"[{AGENT_NAME}] Starting analysis for review {state.review_id}")
    state.update_agent_status(AGENT_NAME, "RUNNING")

    try:
        code = state.submitted_content
        language = state.language

        # Run both tools
        secret_issues = scan_secrets(code)
        vuln_issues = detect_security_vulnerabilities(code, language)

        all_issues = secret_issues + vuln_issues
        findings_added = 0

        # Determine file name from diff analysis
        diff_summary = state.get_metadata("diff_summary", {})
        files = diff_summary.get("files_changed", ["submitted_code"])
        primary_file = files[0] if files else "submitted_code"

        for issue in all_issues:
            finding = Finding(
                agent=AGENT_NAME,
                file=primary_file,
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

        state.update_agent_status(AGENT_NAME, "COMPLETED")
        logger.info(f"[{AGENT_NAME}] Completed. {findings_added} security findings.")

        return {
            "agent": AGENT_NAME,
            "status": "COMPLETED",
            "findings_count": findings_added,
            "secrets_found": len(secret_issues),
            "vulnerabilities_found": len(vuln_issues),
        }

    except Exception as e:
        logger.error(f"[{AGENT_NAME}] Error: {e}")
        state.update_agent_status(AGENT_NAME, "FAILED")
        return {"agent": AGENT_NAME, "status": "FAILED", "error": str(e)}
