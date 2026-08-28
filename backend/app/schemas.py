from typing import Literal

from pydantic import BaseModel, Field


class InvitationVerify(BaseModel):
    code: str = Field(min_length=4, max_length=64)


class AuthResult(BaseModel):
    access_token: str
    student_id: str
    anonymous_id: str


class ConversationCreate(BaseModel):
    pass


class QuestionCreate(BaseModel):
    conversation_id: str
    text: str = Field(min_length=2, max_length=2000)


class QuestionCreated(BaseModel):
    id: str
    request_id: str
    status: str


class AgentMessageCreate(BaseModel):
    conversation_id: str | None = None
    text: str = Field(min_length=1, max_length=2000)
    license_type: str = Field(default="C1", max_length=3)
    subject: str = Field(default="subject-1", max_length=16)


class LearningContextPatch(BaseModel):
    license_type: str = Field(max_length=3)
    subject: str = Field(max_length=16)


class AgentMessageResult(BaseModel):
    conversation_id: str
    intent: str
    action: Literal["ANSWER", "NAVIGATE", "RESPOND"]
    question_id: str | None = None
    destination: str | None = None
    assistant_message: str | None = None
    prompt_version: str


class EvidenceOut(BaseModel):
    source_type: str
    source_id: str
    title: str
    version: str
    excerpt: str


class AnswerPayload(BaseModel):
    id: str | None = None
    direct_answer: str
    short_reason: str
    detail: str
    common_mistake: str
    evidence: list[EvidenceOut]
    route: str
    risk_codes: list[str] = []


class FeedbackCreate(BaseModel):
    type: Literal["resolved", "not_understood", "disputed"]


class TicketCreate(BaseModel):
    question_id: str
    risk_codes: list[str] = []


class TicketClaim(BaseModel):
    version: int = Field(ge=1)


class TicketReply(BaseModel):
    version: int = Field(ge=1)
    content: str = Field(min_length=2, max_length=4000)


class TicketAcknowledge(BaseModel):
    version: int = Field(ge=1)


class OCRTaskCreate(BaseModel):
    asset_id: str


class OCRFieldPatch(BaseModel):
    field_id: str
    value: str = Field(min_length=1, max_length=4000)


class OCRFieldsPatch(BaseModel):
    version: int = Field(ge=1)
    fields: list[OCRFieldPatch] = Field(min_length=1, max_length=10)


class OCRConfirm(BaseModel):
    conversation_id: str | None = None


class PracticeAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=16)


class FavoritePatch(BaseModel):
    is_favorite: bool


class MockExamAnswer(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=16)


class MockExamSubmit(BaseModel):
    answers: list[MockExamAnswer] = Field(min_length=1, max_length=100)
