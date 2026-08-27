import hashlib
import json
import secrets
import time

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AITrace, Answer, Conversation, Evidence, InvitationCode, Question, QuestionStatus, Student
from app.schemas import AnswerPayload, EvidenceOut
from app.knowledge.service import retrieve
from app.pe.prompts import SYSTEM_PROMPT, TEACHING_EXPLANATION_PROMPT


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


QUESTION_BANK = {
    "驾驶机动车通过没有交通信号的交叉路口怎样行驶": {
        "answer": "减速慢行，并让右方道路来车先行。",
        "reason": "无信号路口要先降低速度，再按让行规则观察通行。",
        "detail": "进入没有交通信号控制的交叉路口前，应减速或停车观察；在没有交通标志、标线控制时，让右方道路的来车先行。",
        "mistake": "只记得减速，却忽略了右方来车的优先关系。",
        "source_id": "seed-q-001",
        "title": "科目一高频标准题",
        "excerpt": "没有交通标志、标线控制的，让右方道路的来车先行。",
    },
    "机动车在道路上发生故障难以移动时首先应当持续开启危险报警闪光灯": {
        "answer": "正确。",
        "reason": "车辆难以移动时，首先要让其他交通参与者尽早发现危险。",
        "detail": "应持续开启危险报警闪光灯，并在来车方向设置警告标志；夜间还应开启示廓灯和后位灯。",
        "mistake": "只放警告标志但忘记先开启危险报警闪光灯。",
        "source_id": "seed-q-002",
        "title": "科目一高频标准题",
        "excerpt": "机动车在道路上发生故障，需要停车排除故障时，应当立即开启危险报警闪光灯。",
    },
}


def normalize(text: str) -> str:
    return "".join(ch for ch in text.strip().lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def standard_match(text: str) -> dict | None:
    normalized = normalize(text)
    for key, value in QUESTION_BANK.items():
        key_normalized = normalize(key)
        if normalized == key_normalized or key_normalized in normalized:
            return value
    return None


class AIServiceError(RuntimeError):
    pass


class TeachingExplanation(BaseModel):
    short_reason: str = Field(min_length=4, max_length=240)
    detail: str = Field(min_length=8, max_length=1200)
    common_mistake: str = Field(min_length=4, max_length=300)


class AIService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_id = "deterministic-fallback"
        self.token_usage = 0
        self.is_mock = True
        self.error_type: str | None = None

    def answer(self, text: str, match: dict | None, explain_again: bool = False) -> AnswerPayload:
        if match:
            explanation = None
            if self.settings.dashscope_api_key:
                try:
                    explanation = self._call_dashscope_teaching(text, match, explain_again)
                except AIServiceError:
                    self.error_type = "TEACHING_MODEL_FALLBACK"
            detail = explanation.detail if explanation else match["detail"]
            if explain_again and not explanation:
                detail = f"换个说法：先把路口想成排队通行。没有信号时先慢下来，再确认谁应先走。{match['detail']}"
            return AnswerPayload(
                direct_answer=match["answer"],
                short_reason=explanation.short_reason if explanation else match["reason"],
                detail=detail,
                common_mistake=explanation.common_mistake if explanation else match["mistake"],
                evidence=[EvidenceOut(source_type="question_bank", source_id=match["source_id"], title=match["title"], version=match.get("knowledge_version", "seed-v1"), excerpt=match["excerpt"])],
                route="standard_question",
            )
        return AnswerPayload(
            direct_answer="这个问题目前没有命中经过审核的可靠依据。",
            short_reason="为避免给出看似流畅但可能错误的答案，系统不会猜测。",
            detail="你可以补充完整题干、选项、车型或适用地区；也可以提交给校长核查。",
            common_mistake="不要把没有来源的网络说法当作现行考试规则。",
            evidence=[], route="open_theory", risk_codes=["NO_TRUSTED_MATCH"],
        )

    def _call_dashscope_teaching(self, text: str, match: dict, explain_again: bool) -> TeachingExplanation:
        request = {
            "messages": [
                {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{TEACHING_EXPLANATION_PROMPT}"},
                {"role": "user", "content": json.dumps({
                    "question": text,
                    "locked_standard_answer": match["answer"],
                    "evidence": {"title": match["title"], "excerpt": match["excerpt"], "version": match.get("knowledge_version", "seed-v1")},
                    "explanation_mode": "alternative" if explain_again else "first",
                }, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 600,
            "enable_thinking": False,
        }
        last_error: Exception | None = None
        model_candidates = [self.settings.main_model_id] if explain_again else list(dict.fromkeys([self.settings.light_model_id, self.settings.main_model_id]))
        for model_id in model_candidates:
            request["model"] = model_id
            for _ in range(self.settings.model_max_retries + 1):
                try:
                    response = httpx.post(
                        f"{self.settings.dashscope_base_url.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {self.settings.dashscope_api_key}"},
                        json=request, timeout=self.settings.model_timeout_seconds,
                    )
                    response.raise_for_status()
                    body = response.json()
                    content = str(body["choices"][0]["message"]["content"]).strip()
                    if content.startswith("```"):
                        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    parsed = TeachingExplanation.model_validate_json(content)
                    self.model_id = model_id
                    self.token_usage = int(body.get("usage", {}).get("total_tokens", 0))
                    self.is_mock = False
                    return parsed
                except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError) as exc:
                    last_error = exc
        raise AIServiceError("DashScope teaching explanation failed") from last_error

    def _call_dify(self, text: str, explain_again: bool) -> AnswerPayload:
        url = f"{self.settings.dify_base_url.rstrip('/')}/v1/workflows/run"
        body = {"inputs": {"question": text, "explain_again": explain_again}, "response_mode": "blocking", "user": "anonymous-student"}
        try:
            with httpx.Client(timeout=self.settings.model_timeout_seconds) as client:
                response = client.post(url, headers={"Authorization": f"Bearer {self.settings.dify_api_key}"}, json=body)
                response.raise_for_status()
                outputs = response.json().get("data", {}).get("outputs", {})
                return AnswerPayload.model_validate(outputs)
        except (httpx.HTTPError, ValueError) as exc:
            raise AIServiceError("Dify workflow failed") from exc


def create_answer(db: Session, question: Question, explain_again: bool = False) -> AnswerPayload:
    started = time.monotonic()
    question.status = QuestionStatus.ROUTING.value
    db.commit()
    conversation = db.get(Conversation, question.conversation_id)
    student = db.get(Student, conversation.student_id) if conversation else None
    query_text = question.resolved_text or question.raw_text
    knowledge_license = "C1" if student and student.license_type in {"C1", "C2"} and student.subject in {"subject-1", "subject-4", "科目一", "科目四"} else student.license_type if student else "C1"
    match = retrieve(db, query_text, student.school_id, student.region, knowledge_license, question.id) if student and get_settings().rag_enabled else None
    match = match or standard_match(query_text)
    question.route = "standard_question" if match else "open_theory"
    question.status = QuestionStatus.RETRIEVING.value
    db.commit()
    try:
        question.status = QuestionStatus.GENERATING.value
        db.commit()
        service = AIService()
        payload = service.answer(query_text, match, explain_again or question.intent == "FOLLOW_UP")
        question.status = QuestionStatus.VALIDATING.value
        db.commit()
        if payload.route == "standard_question" and (not match or payload.direct_answer != match["answer"]):
            raise AIServiceError("standard answer consistency failed")
        if not payload.evidence:
            question.status = QuestionStatus.NEEDS_REVIEW.value
        else:
            question.status = QuestionStatus.ANSWERED.value
        answer = question.answer
        if answer is None:
            answer = Answer(question_id=question.id, direct_answer=payload.direct_answer, short_reason=payload.short_reason, detail=payload.detail, common_mistake=payload.common_mistake)
            db.add(answer)
            db.flush()
        else:
            answer.version = str(int(answer.version) + 1)
            answer.direct_answer = payload.direct_answer
            answer.short_reason = payload.short_reason
            answer.detail = payload.detail
            answer.common_mistake = payload.common_mistake
            for item in list(answer.evidence):
                db.delete(item)
        for item in payload.evidence:
            db.add(Evidence(answer_id=answer.id, **item.model_dump()))
        db.add(AITrace(question_id=question.id, model_id=service.model_id, prompt_version=question.prompt_version, workflow_version="agent-loop-v1", latency_ms=int((time.monotonic() - started) * 1000), token_usage=service.token_usage, error_type=service.error_type, is_mock=service.is_mock))
        db.commit()
        payload.id = answer.id
        return payload
    except Exception:
        question.status = QuestionStatus.FAILED.value
        db.commit()
        raise


def seed(db: Session) -> None:
    if not db.scalar(select(InvitationCode).limit(1)):
        db.add(InvitationCode(code_hash=digest("INVITE_CODE_REMOVED")))
        db.commit()


def authenticate_invitation(db: Session, code: str) -> tuple[Student, str] | None:
    invitation = db.scalar(select(InvitationCode).where(InvitationCode.code_hash == digest(code.strip())))
    if not invitation or invitation.status != "ACTIVE":
        return None
    if invitation.student_id:
        student = db.get(Student, invitation.student_id)
        token = secrets.token_urlsafe(32)
        student.session_token_hash = digest(token)
    else:
        token = secrets.token_urlsafe(32)
        student = Student(school_id=invitation.school_id, session_token_hash=digest(token))
        db.add(student)
        db.flush()
        invitation.student_id = student.id
    db.commit()
    return student, token
