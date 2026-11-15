"""FastAPI routes for the Code Review Board API."""
import uuid
import logging
import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.database import get_db, SessionLocal, Review, Finding, AgentExecution, ReviewLog, SuggestedPatch
from models.schemas import (
    CreateReviewRequest, ReviewSummarySchema, ReviewDetailSchema,
    FindingSchema, AgentExecutionSchema, ReviewLogSchema, SuggestedPatchSchema, HealthResponse
)
from core.change_state import ReviewChangeState, Finding as StateFinding
from core.logging_service import review_logger
from core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

async def run_review_pipeline(review_id: str, state: ReviewChangeState):
    """Run the complete multi-agent review pipeline."""
    from agents import reviewer_manager
    db = SessionLocal()

    # Update status to RUNNING
    db_review = db.query(Review).filter(Review.id == review_id).first()
    if db_review:
        db_review.status = "RUNNING"
        db.commit()

    review_logger.log(review_id, "System", "STARTED", details=f"Review pipeline started for {review_id}")

    try:
        result = await reviewer_manager.run(state)

        # Save all findings to database
        # Persist the manager's deduplicated output, not intermediate duplicates.
        aggregated = result.get("findings", [])
        all_findings = [
            StateFinding(
                id=f.get("id", str(uuid.uuid4())),
                agent=f.get("agent", ""),
                file=f.get("file", ""),
                line=f.get("line"),
                severity=f.get("severity", "INFO"),
                category=f.get("category", ""),
                title=f.get("title", ""),
                description=f.get("description", ""),
                recommendation=f.get("recommendation", ""),
                evidence=f.get("evidence", ""),
            )
            for f in aggregated
        ]
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}

        for f in all_findings:
            db_finding = Finding(
                id=f.id,
                review_id=review_id,
                agent=f.agent,
                file=f.file,
                line=f.line,
                severity=f.severity,
                category=f.category,
                title=f.title,
                description=f.description,
                recommendation=f.recommendation,
                evidence=f.evidence,
                created_at=f.created_at,
            )
            db.add(db_finding)
            if f.severity in severity_counts:
                severity_counts[f.severity] += 1

        # Save agent executions
        agent_status = state.get_agent_status()
        for agent_name, status in agent_status.items():
            agent_findings = state.get_agent_findings(agent_name)
            exec_record = AgentExecution(
                id=str(uuid.uuid4()),
                review_id=review_id,
                agent_name=agent_name,
                status=status,
                findings_count=len(agent_findings),
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                tools_invoked=result.get("tools_invoked", {}).get(agent_name, []),
            )
            db.add(exec_record)

        # Save suggested patch if any
        patch_data = result.get("suggested_patch")
        if patch_data and patch_data.get("before_code"):
            db_patch = SuggestedPatch(
                id=str(uuid.uuid4()),
                review_id=review_id,
                finding_title=patch_data.get("finding_title", "Top severity finding"),
                before_code=patch_data.get("before_code", ""),
                after_code=patch_data.get("after_code", ""),
                explanation=patch_data.get("explanation", ""),
                expected_result=patch_data.get("expected_result", ""),
                is_valid=1 if patch_data.get("is_valid", True) else 0,
            )
            db.add(db_patch)

        # Save audit logs to database
        for log_entry in review_logger.get_logs_for_review(review_id):
            db_log = ReviewLog(
                id=log_entry["id"],
                review_id=review_id,
                timestamp=datetime.fromisoformat(log_entry["timestamp"]),
                agent_name=log_entry["agent_name"],
                event_type=log_entry["event_type"],
                tool_invoked=log_entry.get("tool_invoked"),
                status=log_entry["status"],
                details=log_entry["details"],
            )
            db.add(db_log)

        # Update review record
        recommendation = result.get("recommendation", {})
        if db_review:
            db_review.status = "COMPLETED"
            db_review.completed_at = datetime.utcnow()
            db_review.merge_decision = recommendation.get("decision", "PENDING")
            db_review.decision_reason = recommendation.get("reason", "")
            db_review.total_findings = len(all_findings)
            db_review.critical_count = severity_counts["CRITICAL"]
            db_review.high_count = severity_counts["HIGH"]
            db_review.medium_count = severity_counts["MEDIUM"]
            db_review.low_count = severity_counts["LOW"]
            db_review.info_count = severity_counts["INFO"]

        db.commit()

    except Exception as e:
        logger.error(f"Pipeline error for {review_id}: {e}", exc_info=True)
        if db_review:
            db_review.status = "FAILED"
            db_review.decision_reason = str(e)
            db.commit()
        review_logger.log(review_id, "System", "ERROR", status="ERROR", details=str(e))
    finally:
        db.close()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"
    return HealthResponse(
        status="ok",
        version="1.0.0",
        offline_mode=settings.offline_mode,
        database=db_status,
    )


@router.post("/reviews", response_model=ReviewSummarySchema)
async def create_review(request: CreateReviewRequest, db: Session = Depends(get_db)):
    """Submit code for review. Runs the full multi-agent pipeline."""
    review_id = str(uuid.uuid4())

    db_review = Review(
        id=review_id,
        repo_name=request.repo_name,
        language=request.language,
        submission_type=request.submission_type,
        status="PENDING",
        merge_decision="PENDING",
        created_at=datetime.utcnow(),
        submitted_content=request.diff_text,
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)

    # Create shared change state
    state = ReviewChangeState(
        review_id=review_id,
        submitted_content=request.diff_text,
        language=request.language,
        repo_name=request.repo_name or "",
    )

    # Run pipeline in background
    asyncio.create_task(run_review_pipeline(review_id, state))

    return ReviewSummarySchema(
        id=review_id,
        repo_name=request.repo_name,
        language=request.language,
        status="PENDING",
        merge_decision="PENDING",
        created_at=db_review.created_at,
    )


@router.post("/reviews/diff", response_model=ReviewSummarySchema)
async def create_review_from_diff(request: CreateReviewRequest, db: Session = Depends(get_db)):
    """Submit a git diff specifically. Alias for POST /reviews."""
    return await create_review(request, db)


@router.get("/reviews", response_model=List[ReviewSummarySchema])
async def list_reviews(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    reviews = db.query(Review).order_by(Review.created_at.desc()).offset(offset).limit(limit).all()
    return [ReviewSummarySchema(
        id=r.id, repo_name=r.repo_name, language=r.language,
        status=r.status, merge_decision=r.merge_decision,
        total_findings=r.total_findings, critical_count=r.critical_count,
        high_count=r.high_count, medium_count=r.medium_count,
        low_count=r.low_count, info_count=r.info_count,
        created_at=r.created_at, completed_at=r.completed_at,
    ) for r in reviews]


@router.get("/reviews/{review_id}", response_model=ReviewDetailSchema)
async def get_review(review_id: str, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")
    return ReviewDetailSchema(
        id=r.id, repo_name=r.repo_name, language=r.language,
        status=r.status, merge_decision=r.merge_decision,
        decision_reason=r.decision_reason,
        total_findings=r.total_findings, critical_count=r.critical_count,
        high_count=r.high_count, medium_count=r.medium_count,
        low_count=r.low_count, info_count=r.info_count,
        created_at=r.created_at, completed_at=r.completed_at,
        findings=[FindingSchema(
            id=f.id, agent=f.agent, file=f.file, line=f.line,
            severity=f.severity, category=f.category, title=f.title,
            description=f.description, recommendation=f.recommendation,
            evidence=f.evidence, created_at=f.created_at,
        ) for f in r.findings],
        agent_executions=[AgentExecutionSchema(
            id=ae.id, agent_name=ae.agent_name, status=ae.status,
            findings_count=ae.findings_count, started_at=ae.started_at,
            completed_at=ae.completed_at, error_message=ae.error_message,
            tools_invoked=ae.tools_invoked or [],
        ) for ae in r.agent_executions],
        patches=[SuggestedPatchSchema(
            id=p.id, finding_title=p.finding_title, before_code=p.before_code,
            after_code=p.after_code, explanation=p.explanation,
            expected_result=p.expected_result, is_valid=bool(p.is_valid),
        ) for p in r.patches],
    )


@router.get("/reviews/{review_id}/findings", response_model=List[FindingSchema])
async def get_review_findings(review_id: str, severity: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Finding).filter(Finding.review_id == review_id)
    if severity:
        q = q.filter(Finding.severity == severity.upper())
    findings = q.order_by(Finding.severity).all()
    return [FindingSchema(
        id=f.id, agent=f.agent, file=f.file, line=f.line,
        severity=f.severity, category=f.category, title=f.title,
        description=f.description, recommendation=f.recommendation,
        evidence=f.evidence, created_at=f.created_at,
    ) for f in findings]


@router.get("/reviews/{review_id}/agents", response_model=List[AgentExecutionSchema])
async def get_review_agents(review_id: str, db: Session = Depends(get_db)):
    executions = db.query(AgentExecution).filter(AgentExecution.review_id == review_id).all()
    return [AgentExecutionSchema(
        id=ae.id, agent_name=ae.agent_name, status=ae.status,
        findings_count=ae.findings_count, started_at=ae.started_at,
        completed_at=ae.completed_at, error_message=ae.error_message,
        tools_invoked=ae.tools_invoked or [],
    ) for ae in executions]


@router.get("/reviews/{review_id}/logs", response_model=List[ReviewLogSchema])
async def get_review_logs(review_id: str, db: Session = Depends(get_db)):
    logs = db.query(ReviewLog).filter(ReviewLog.review_id == review_id).order_by(ReviewLog.timestamp).all()
    return [ReviewLogSchema(
        id=l.id, timestamp=l.timestamp, agent_name=l.agent_name,
        event_type=l.event_type, tool_invoked=l.tool_invoked,
        status=l.status, details=l.details,
    ) for l in logs]


@router.get("/reviews/{review_id}/report")
async def get_review_report(review_id: str, db: Session = Depends(get_db)):
    """Get complete review report as JSON."""
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")
    findings = db.query(Finding).filter(Finding.review_id == review_id).all()
    patches = db.query(SuggestedPatch).filter(SuggestedPatch.review_id == review_id).all()
    logs = db.query(ReviewLog).filter(ReviewLog.review_id == review_id).all()

    return {
        "review_id": review_id,
        "repo_name": r.repo_name,
        "language": r.language,
        "status": r.status,
        "merge_decision": r.merge_decision,
        "decision_reason": r.decision_reason,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "summary": {
            "total": r.total_findings,
            "critical": r.critical_count,
            "high": r.high_count,
            "medium": r.medium_count,
            "low": r.low_count,
            "info": r.info_count,
        },
        "findings": [{
            "id": f.id, "agent": f.agent, "file": f.file, "line": f.line,
            "severity": f.severity, "category": f.category, "title": f.title,
            "description": f.description, "recommendation": f.recommendation,
            "evidence": f.evidence,
        } for f in findings],
        "suggested_patches": [{
            "finding_title": p.finding_title, "before_code": p.before_code,
            "after_code": p.after_code, "explanation": p.explanation,
            "expected_result": p.expected_result, "is_valid": bool(p.is_valid),
        } for p in patches],
        "audit_log": [{
            "timestamp": l.timestamp.isoformat(), "agent_name": l.agent_name,
            "event_type": l.event_type, "tool_invoked": l.tool_invoked,
            "status": l.status, "details": l.details,
        } for l in logs],
    }
