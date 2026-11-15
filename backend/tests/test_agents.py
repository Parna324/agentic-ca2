"""Focused tests for the offline specialist tools."""
from agents.diff_agent import parse_git_diff
from agents.security_agent import scan_secrets, detect_security_vulnerabilities
from agents.fix_suggestion_agent import validate_patch_syntax


def test_diff_parser_extracts_files_and_counts():
    result = parse_git_diff("--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,2 @@\n+value = 1\n")
    assert result["files_changed"] == ["app.py"]
    assert result["total_additions"] == 1


def test_security_scanner_redacts_secret():
    findings = scan_secrets('password = "supersecret"')
    assert findings
    assert "supersecret" not in findings[0]["evidence"]
    assert "[REDACTED]" in findings[0]["evidence"]


def test_security_scanner_detects_shell_execution():
    findings = detect_security_vulnerabilities("import subprocess\nsubprocess.run(cmd, shell=True)")
    assert any("subprocess" in finding["title"] for finding in findings)


def test_patch_validator_rejects_invalid_python():
    assert validate_patch_syntax("def broken(:", "python")["valid"] is False
