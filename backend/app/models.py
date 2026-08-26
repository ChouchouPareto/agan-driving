import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


def uid() -> str:
    return str(uuid.uuid4())


class QuestionStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    ROUTING = "ROUTING"
    RETRIEVING = "RETRIEVING"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    ANSWERED = "ANSWERED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REFUSED = "REFUSED"
    FAILED = "FAILED"


class TicketStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    REPLIED = "REPLIED"
    CLOSED = "CLOSED"


class InvitationCode(Base):
    __tablename__ = "invitation_codes"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    code_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    school_id: Mapped[str] = mapped_column(String, default="pilot-school")
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id"), nullable=True)


class Student(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    anonymous_id: Mapped[str] = mapped_column(String, unique=True, index=True, default=uid)
    school_id: Mapped[str] = mapped_column(String, default="pilot-school")
    subject: Mapped[str] = mapped_column(String, default="科目一")
    license_type: Mapped[str] = mapped_column(String, default="C1")
    region: Mapped[str] = mapped_column(String, default="全国")
    session_token_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    request_id: Mapped[str] = mapped_column(String, unique=True, index=True, default=uid)
    raw_text: Mapped[str] = mapped_column(Text)
    route: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default=QuestionStatus.SUBMITTED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    answer: Mapped["Answer | None"] = relationship(back_populates="question", uselist=False)


class Answer(Base):
    __tablename__ = "answers"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), unique=True)
    version: Mapped[str] = mapped_column(String, default="1")
    direct_answer: Mapped[str] = mapped_column(Text)
    short_reason: Mapped[str] = mapped_column(Text)
    detail: Mapped[str] = mapped_column(Text)
    common_mistake: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="VALID")
    question: Mapped[Question] = relationship(back_populates="answer")
    evidence: Mapped[list["Evidence"]] = relationship(cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answers.id"), index=True)
    source_type: Mapped[str] = mapped_column(String)
    source_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)
    excerpt: Mapped[str] = mapped_column(Text)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answers.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    type: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewTicket(Base):
    __tablename__ = "review_tickets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    status: Mapped[str] = mapped_column(String, default=TicketStatus.QUEUED.value)
    risk_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class AITrace(Base):
    __tablename__ = "ai_traces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    model_id: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String)
    workflow_version: Mapped[str] = mapped_column(String)
    latency_ms: Mapped[int] = mapped_column(default=0)
    token_usage: Mapped[int] = mapped_column(default=0)
    error_type: Mapped[str | None] = mapped_column(String, nullable=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)

