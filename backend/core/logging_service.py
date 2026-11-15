"""Append-only audit log service for tracking all agent actions."""
import uuid
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List

logger = logging.getLogger(__name__)

@dataclass
class ReviewLogEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    review_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    agent_name: str = ""
    event_type: str = ""  # STARTED, COMPLETED, ERROR, TOOL_INVOKED, FINDING_ADDED, DECISION_MADE
    tool_invoked: Optional[str] = None
    status: str = "SUCCESS"
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "review_id": self.review_id,
            "timestamp": self.timestamp.isoformat(),
            "agent_name": self.agent_name,
            "event_type": self.event_type,
            "tool_invoked": self.tool_invoked,
            "status": self.status,
            "details": self.details,
        }

class ReviewLogger:
    """Append-only logger. Never deletes or overwrites entries."""

    def __init__(self):
        self._logs: List[ReviewLogEntry] = []

    def log(self, review_id: str, agent_name: str, event_type: str,
            status: str = "SUCCESS", details: str = "", tool_invoked: Optional[str] = None) -> ReviewLogEntry:
        entry = ReviewLogEntry(
            review_id=review_id,
            agent_name=agent_name,
            event_type=event_type,
            tool_invoked=tool_invoked,
            status=status,
            details=details,
        )
        self._logs.append(entry)  # append-only, never deletes
        logger.info(f"[AUDIT] {review_id} | {agent_name} | {event_type} | {status}")
        return entry

    def get_logs_for_review(self, review_id: str) -> List[dict]:
        return [e.to_dict() for e in self._logs if e.review_id == review_id]

    def get_all_logs(self) -> List[dict]:
        return [e.to_dict() for e in self._logs]

# Global logger instance
review_logger = ReviewLogger()
