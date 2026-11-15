"""Deterministic recommendation tests."""
from agents.reviewer_manager import aggregate_agent_findings, calculate_merge_recommendation


def test_critical_finding_requests_changes():
    result = calculate_merge_recommendation([
        {"id": "1", "severity": "CRITICAL", "category": "Security", "title": "Unsafe", "file": "a.py"}
    ])
    assert result["decision"] == "REQUEST_CHANGES"


def test_clean_review_is_approved():
    result = calculate_merge_recommendation([
        {"id": "1", "severity": "LOW", "category": "Style", "title": "Minor", "file": "a.py"}
    ])
    assert result["decision"] == "APPROVE"


def test_duplicate_findings_keep_highest_severity():
    result = aggregate_agent_findings([
        {"severity": "LOW", "title": "Same", "file": "a.py", "line": 2},
        {"severity": "HIGH", "title": "Same", "file": "a.py", "line": 2},
    ])
    assert result["total"] == 1
    assert result["deduplicated"][0]["severity"] == "HIGH"
