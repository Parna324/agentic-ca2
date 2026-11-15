"""Database models using SQLAlchemy 2.0."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, JSON, create_engine
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker, Session
from typing import Generator
import os

class Base(DeclarativeBase):
    pass

class Review(Base):
    __tablename__ = "reviews"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_name = Column(String(255), nullable=True)
    language = Column(String(50), default="python")
    submission_type = Column(String(50), default="diff")
    status = Column(String(50), default="PENDING")
    merge_decision = Column(String(50), default="PENDING")
    decision_reason = Column(Text, nullable=True)
    total_findings = Column(Integer, default=0)
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    info_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    submitted_content = Column(Text)
    findings = relationship("Finding", back_populates="review", cascade="all, delete-orphan")
    agent_executions = relationship("AgentExecution", back_populates="review", cascade="all, delete-orphan")
    logs = relationship("ReviewLog", back_populates="review", cascade="all, delete-orphan")
    patches = relationship("SuggestedPatch", back_populates="review", cascade="all, delete-orphan")

class Finding(Base):
    __tablename__ = "findings"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String(36), ForeignKey("reviews.id"))
    agent = Column(String(100))
    file = Column(String(500))
    line = Column(Integer, nullable=True)
    severity = Column(String(20))
    category = Column(String(100))
    title = Column(String(500))
    description = Column(Text)
    recommendation = Column(Text)
    evidence = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    review = relationship("Review", back_populates="findings")

class AgentExecution(Base):
    __tablename__ = "agent_executions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String(36), ForeignKey("reviews.id"))
    agent_name = Column(String(100))
    status = Column(String(50))
    findings_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    tools_invoked = Column(JSON, default=list)
    duration_seconds = Column(Integer, nullable=True)
    review = relationship("Review", back_populates="agent_executions")

class SuggestedPatch(Base):
    __tablename__ = "suggested_patches"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String(36), ForeignKey("reviews.id"))
    finding_title = Column(String(500))
    before_code = Column(Text)
    after_code = Column(Text)
    explanation = Column(Text)
    expected_result = Column(Text)
    is_valid = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    review = relationship("Review", back_populates="patches")

class ReviewLog(Base):
    __tablename__ = "review_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id = Column(String(36), ForeignKey("reviews.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    agent_name = Column(String(100))
    event_type = Column(String(50))
    tool_invoked = Column(String(200), nullable=True)
    status = Column(String(50))
    details = Column(Text)
    review = relationship("Review", back_populates="logs")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./code_review.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
