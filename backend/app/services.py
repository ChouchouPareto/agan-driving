import hashlib
import json
import secrets
import time
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AITrace, Answer, Evidence, InvitationCode, Question, QuestionStatus, Student
from app.schemas import AnswerPayload, EvidenceOut


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


class AIService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def answer(self, text: str, match: dict | None, explain_again: bool = False) -> AnswerPayload:
        if match:
            detail = match["detail"]
            if explain_again:
                detail = f"换个说法：先把路口想成排队通行。没有信号时先慢下来，再确认谁应先走。{match['detail']}"
            return AnswerPayload(
                direct_answer=match["answer"],
                short_reason=match["reason"],
                detail=detail,
                common_mistake=match["mistake"],
                evidence=[EvidenceOut(source_type="question_bank", source_id=match["source_id"], title=match["title"], version="seed-v1", excerpt=match["excerpt"])],
                route="standard_question",
            )
        if self.settings.mock_ai:
            return AnswerPayload(
                direct_answer="这个问题目前没有命中经过审核的可靠依据。",
                short_reason="为避免给出看似流畅但可能错误的答案，系统不会猜测。",
                detail="你可以补充完整题干、选项、车型或适用地区；也可以提交给校长核查。",
                common_mistake="不要把没有来源的网络说法当作现行考试规则。",
                evidence=[],
                route="open_theory",
                risk_codes=["NO_TRUSTED_MATCH"],
            )
        return self._call_dify(text, explain_again)

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
    match = standard_match(question.raw_text)
    question.route = "standard_question" if match else "open_theory"
    question.status = QuestionStatus.RETRIEVING.value
    db.commit()
    try:
        question.status = QuestionStatus.GENERATING.value
        db.commit()
        payload = AIService().answer(question.raw_text, match, explain_again)
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
        db.add(AITrace(question_id=question.id, model_id=get_settings().main_model_id, prompt_version="v1", workflow_version="mock-v1" if get_settings().mock_ai else get_settings().dify_workflow_id, latency_ms=int((time.monotonic() - started) * 1000), token_usage=0, is_mock=get_settings().mock_ai))
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

