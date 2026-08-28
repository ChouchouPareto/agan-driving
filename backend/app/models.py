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
    subject: Mapped[str] = mapped_column(String, default="subject-1")
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


class AgentTurn(Base):
    __tablename__ = "agent_turns"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    user_text: Mapped[str] = mapped_column(Text)
    assistant_text: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String, index=True)
    skill_id: Mapped[str] = mapped_column(String)
    model_id: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String)
    token_usage: Mapped[int] = mapped_column(Integer, default=0)
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    request_id: Mapped[str] = mapped_column(String, unique=True, index=True, default=uid)
    raw_text: Mapped[str] = mapped_column(Text)
    resolved_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[str] = mapped_column(String, default="QUESTION_ANSWER")
    prompt_version: Mapped[str] = mapped_column(String, default="pe-v1.0")
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


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    supplier: Mapped[str] = mapped_column(String)
    license_scope: Mapped[str] = mapped_column(String, default="test-only")
    source_hash: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    source_id: Mapped[str] = mapped_column(ForeignKey("knowledge_sources.id"), index=True)
    school_id: Mapped[str] = mapped_column(String, index=True)
    version_label: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="VALIDATING", index=True)
    region: Mapped[str] = mapped_column(String, default="全国")
    license_type: Mapped[str] = mapped_column(String, default="C1")
    schema_version: Mapped[str] = mapped_column(String, default="1")
    normalizer_version: Mapped[str] = mapped_column(String, default="1")
    embedding_model: Mapped[str] = mapped_column(String, default="text-embedding-v4")
    embedding_dimensions: Mapped[int] = mapped_column(Integer, default=1024)
    collection_name: Mapped[str | None] = mapped_column(String, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StandardQuestion(Base):
    __tablename__ = "standard_questions"
    __table_args__ = (UniqueConstraint("knowledge_version_id", "external_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    knowledge_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_versions.id"), index=True)
    school_id: Mapped[str] = mapped_column(String, index=True)
    external_id: Mapped[str] = mapped_column(String)
    stem: Mapped[str] = mapped_column(Text)
    normalized_stem: Mapped[str] = mapped_column(Text)
    stem_fingerprint: Mapped[str] = mapped_column(String, index=True)
    options: Mapped[list[dict]] = mapped_column(JSON, default=list)
    options_fingerprint: Mapped[str] = mapped_column(String, index=True)
    standard_answer: Mapped[str] = mapped_column(String)
    explanation: Mapped[str] = mapped_column(Text)
    knowledge_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    question_type: Mapped[str] = mapped_column(String)
    region: Mapped[str] = mapped_column(String, default="全国")
    license_type: Mapped[str] = mapped_column(String, default="C1")
    status: Mapped[str] = mapped_column(String, default="VALID", index=True)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    question_id: Mapped[str] = mapped_column(ForeignKey("standard_questions.id"), unique=True, index=True)
    knowledge_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_versions.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String, index=True)
    embedding_status: Mapped[str] = mapped_column(String, default="PENDING")
    vector_record_id: Mapped[str | None] = mapped_column(String, nullable=True)


class KnowledgeValidationIssue(Base):
    __tablename__ = "knowledge_validation_issues"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    knowledge_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_versions.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issue_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    safe_message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="OPEN")
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RetrievalTrace(Base):
    __tablename__ = "retrieval_traces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id"), nullable=True, index=True)
    knowledge_version_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_versions.id"), nullable=True)
    query_hash: Mapped[str] = mapped_column(String, index=True)
    match_type: Mapped[str] = mapped_column(String)
    candidate_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    final_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AdvisoryKnowledgeDocument(Base):
    __tablename__ = "advisory_knowledge_documents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    external_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    topic: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    source_org: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(Text)
    document_no: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str] = mapped_column(String, default="全国", index=True)
    license_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(String, nullable=True)
    effective_at: Mapped[str | None] = mapped_column(String, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status: Mapped[str] = mapped_column(String, default="ACTIVE", index=True)


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    version_label: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("evaluation_datasets.id"), index=True)
    input_text: Mapped[str] = mapped_column(Text)
    expected_external_id: Mapped[str] = mapped_column(String)
    expected_answer: Mapped[str] = mapped_column(String)
    region: Mapped[str] = mapped_column(String, default="全国")
    license_type: Mapped[str] = mapped_column(String, default="C1")
    severity: Mapped[str] = mapped_column(String, default="P0")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("evaluation_datasets.id"), index=True)
    knowledge_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_versions.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="RUNNING", index=True)
    embedding_model: Mapped[str] = mapped_column(String)
    rerank_model: Mapped[str] = mapped_column(String)
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    p0_errors: Mapped[int] = mapped_column(Integer, default=0)
    top1_rate: Mapped[float] = mapped_column(Float, default=0)
    answer_accuracy: Mapped[float] = mapped_column(Float, default=0)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvaluationCaseResult(Base):
    __tablename__ = "evaluation_case_results"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("evaluation_cases.id"), index=True)
    matched_question_id: Mapped[str | None] = mapped_column(ForeignKey("standard_questions.id"), nullable=True)
    actual_answer: Mapped[str | None] = mapped_column(String, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    match_type: Mapped[str] = mapped_column(String, default="none")


class KnowledgeActivationEvent(Base):
    __tablename__ = "knowledge_activation_events"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    school_id: Mapped[str] = mapped_column(String, index=True)
    actor_id: Mapped[str] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String)
    from_version_id: Mapped[str | None] = mapped_column(ForeignKey("knowledge_versions.id"), nullable=True)
    to_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_versions.id"), index=True)
    request_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StudentQuestionProgress(Base):
    __tablename__ = "student_question_progress"
    __table_args__ = (UniqueConstraint("student_id", "standard_question_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    standard_question_id: Mapped[str] = mapped_column(ForeignKey("standard_questions.id"), index=True)
    knowledge_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_versions.id"), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_attempts: Mapped[int] = mapped_column(Integer, default=0)
    wrong_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_answer: Mapped[str | None] = mapped_column(String, nullable=True)
    last_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    last_answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
