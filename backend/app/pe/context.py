"""A single, ordered history for both teaching and conversational skills."""
from datetime import timezone
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentTurn, Question


def epoch(value):
    return value.replace(tzinfo=value.tzinfo or timezone.utc).timestamp()


def recent_dialogue(db: Session, conversation_id: str, limit: int = 8) -> list[dict]:
    turns = db.scalars(select(AgentTurn).where(AgentTurn.conversation_id == conversation_id).order_by(AgentTurn.created_at.desc()).limit(limit)).all()
    questions = db.scalars(select(Question).where(Question.conversation_id == conversation_id, Question.intent != "HUMAN_HELP").order_by(Question.created_at.desc()).limit(limit)).all()
    history = [{"at": epoch(t.created_at), "intent": t.intent, "user": t.user_text, "assistant": t.assistant_text} for t in turns]
    history += [{"at": epoch(q.created_at), "intent": q.intent, "user": q.raw_text,
                 "assistant": f"{q.answer.direct_answer}\n{q.answer.detail}" if q.answer else "这道题还没有给出可靠答案。"} for q in questions]
    return sorted(history, key=lambda item: item["at"])[-limit:]


def learner_context(student, history: list[dict], current: str) -> dict:
    """Conversation facts override UI defaults, but do not silently change profiles."""
    context = {"region": student.region, "license_type": student.license_type, "subject": student.subject}
    for text in [item["user"] for item in history] + [current]:
        license_match = re.search(r"\b([ABC][1-6])\b", text, re.I)
        if license_match:
            context["license_type"] = license_match.group(1).upper()
        city = re.search(r"(?:我在|人在|住在|所在城市是|^)([\u4e00-\u9fff]{2,6})(?:市)?[，,]", text)
        if city and not any(word in city.group(1) for word in ("科目", "教练", "考试")):
            context["region"] = city.group(1)
        if re.search(r"(?:已经通过|通过了|已过|考过了|考完了)科目一", text):
            context["learning_stage"] = "科目一已通过"
        if "周末" in text:
            context["availability"] = "周末可练车"
    return context
