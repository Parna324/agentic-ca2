"""Pydantic v2 schemas for API request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum

class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class MergeDecision(str, Enum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    PENDING = "PENDING"

class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class FindingSchema(BaseModel):
    id: str = ""
    agent: str
    file: str
    line: Optional[int] = None
    severity: SeverityLevel
    category: str
    title: str
    description: str
    recommendation: str
    evidence: Optional[str] = None
    created_at: Optional[datetime] = None

class AgentExecutionSchema(BaseModel):
    id: str = ""
    agent_name: str
    status: str
    findings_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    tools_invoked: List[str] = []
    duration_seconds: Optional[int] = None

class SuggestedPatchSchema(BaseModel):
    id: str = ""
    finding_title: str
    before_code: str
    after_code: str
    explanation: str
    expected_result: str
    is_valid: bool = True

class ReviewLogSchema(BaseModel):
    id: str = ""
    timestamp: datetime
    agent_name: str
    event_type: str
    tool_invoked: Optional[str] = None
    status: str
    details: str

class ReviewSummarySchema(BaseModel):
    id: str
    repo_name: Optional[str] = None
    language: str
    status: ReviewStatus
    merge_decision: MergeDecision
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    created_at: datetime
    completed_at: Optional[datetime] = None

class ReviewDetailSchema(ReviewSummarySchema):
    decision_reason: Optional[str] = None
    findings: List[FindingSchema] = []
    agent_executions: List[AgentExecutionSchema] = []
    patches: List[SuggestedPatchSchema] = []

class CreateReviewRequest(BaseModel):
    diff_text: str = Field(..., description="Git diff or source code content")
    repo_name: Optional[str] = Field(None, description="Repository name")
    language: str = Field("python", description="Programming language")
    submission_type: str = Field("diff", description="'diff' or 'files'")

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    offline_mode: bool = True
    database: str = "connected"
