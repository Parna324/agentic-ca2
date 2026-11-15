"""Shared change state for multi-agent review coordination."""
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid


@dataclass
class Finding:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent: str = ""
    file: str = ""
    line: Optional[int] = None
    severity: str = "INFO"
    category: str = ""
    title: str = ""
    description: str = ""
    recommendation: str = ""
    evidence: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent": self.agent,
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
            "created_at": self.created_at.isoformat(),
        }


class ReviewChangeState:
    """Thread-safe shared state object for all agents to read and write."""

    def __init__(
        self,
        review_id: str,
        submitted_content: str,
        language: str = "python",
        repo_name: str = "",
    ):
        self.review_id = review_id
        self.submitted_content = submitted_content
        self.language = language
        self.repo_name = repo_name
        self._lock = threading.Lock()
        self._findings: list[Finding] = []
        self._agent_status: dict[str, str] = {}
        self._agent_findings: dict[str, list[Finding]] = {}
        self.metadata: dict[str, Any] = {}
        self.diff_analysis: dict[str, Any] = {}
        self.created_at = datetime.utcnow()

    def add_finding(self, finding: Finding) -> None:
        with self._lock:
            self._findings.append(finding)
            agent = finding.agent
            if agent not in self._agent_findings:
                self._agent_findings[agent] = []
            self._agent_findings[agent].append(finding)

    def update_agent_status(self, agent_name: str, status: str) -> None:
        with self._lock:
            self._agent_status[agent_name] = status

    def get_all_findings(self) -> list[Finding]:
        with self._lock:
            return list(self._findings)

    def get_agent_findings(self, agent_name: str) -> list[Finding]:
        with self._lock:
            return list(self._agent_findings.get(agent_name, []))

    def get_agent_status(self) -> dict[str, str]:
        with self._lock:
            return dict(self._agent_status)

    def set_metadata(self, key: str, value: Any) -> None:
        with self._lock:
            self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self.metadata.get(key, default)
