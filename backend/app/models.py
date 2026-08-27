import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    display_name: Mapped[str] = mapped_column(String, default="值班校长")
    school_id: Mapped[str] = mapped_column(String, index=True, default="pilot-school")
    role: Mapped[str] = mapped_column(String, default="coach")
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
    school_id: Mapped[str] = mapped_column(String, index=True, default="pilot-school")
    status: Mapped[str] = mapped_column(String, default=TicketStatus.QUEUED.value)
    risk_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("staff.id"), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("review_tickets.id"), index=True)
    author_type: Mapped[str] = mapped_column(String)
    author_id: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TicketEvent(Base):
    __tablename__ = "ticket_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("review_tickets.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String)
    from_status: Mapped[str | None] = mapped_column(String, nullable=True)
    to_status: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


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


class UploadedAsset(Base):
    __tablename__ = "uploaded_assets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    school_id: Mapped[str] = mapped_column(String, index=True)
    storage_key: Mapped[str] = mapped_column(String, unique=True)
    original_name: Mapped[str] = mapped_column(String)
    safe_name: Mapped[str] = mapped_column(String)
    declared_mime: Mapped[str] = mapped_column(String)
    detected_mime: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="READY")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class OCRTask(Base):
    __tablename__ = "ocr_tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("uploaded_assets.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    request_id: Mapped[str] = mapped_column(String, unique=True, default=uid)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="QUEUED", index=True)
    provider: Mapped[str] = mapped_column(String, default="dashscope")
    model_id: Mapped[str] = mapped_column(String, default="qwen-vl-ocr")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    question_type: Mapped[str] = mapped_column(String, default="unknown")
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(String, nullable=True)
    linked_question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class OCRField(Base):
    __tablename__ = "ocr_fields"
    __table_args__ = (UniqueConstraint("task_id", "field_type", "sequence"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("ocr_tasks.id"), index=True)
    field_type: Mapped[str] = mapped_column(String)
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    original_value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    needs_confirmation: Mapped[bool] = mapped_column(Boolean, default=True)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class OCRAuditLog(Base):
    __tablename__ = "ocr_audit_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey("ocr_tasks.id"), index=True)
    field_id: Mapped[str | None] = mapped_column(ForeignKey("ocr_fields.id"), nullable=True)
    actor_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    before_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
