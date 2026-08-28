import json
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AgentTurn, Conversation, Student
from app.pe.prompts import COMPANION_CONVERSATION_PROMPT, PROMPT_VERSION
from app.skills.advisory import advisory_response


def _invalid_reply(reply: str) -> bool:
    return bool(re.search(r"肯定能过|下次一定|一定能过|费不了多少钱|没什么大不了|靠(?:语感|常识|猜)|系统识别|网络波动|信号没传|更清晰的指令|我一直在线", reply))


def _fallback(intent: str, user_text: str, evidence: list[dict] | None, history: list[AgentTurn]) -> str:
    if intent == "MNEMONIC_HELP":
        if evidence and evidence[0].get("summary"):
            return f"有，这道可以这样记：{evidence[0]['summary']} 口诀是帮你回想规则的，做题时还是要看清题干条件。"
        return "可以，你把那道题或者想记的知识点发给我，我帮你找一句不容易记错的口诀。"
    if intent in {"EMOTIONAL_SUPPORT", "INDUSTRY_KNOWLEDGE", "LEARNING_PROCESS", "POLICY_REGULATION", "LICENSE_TIMELINE"}:
        return advisory_response(intent, user_text, evidence)
    if intent == "GREETING":
        return "嗨，我在。今天是想聊聊学车的事，还是直接问我一个问题？"
    if intent == "THANKS":
        return "不用客气。你想接着聊刚才的事，或者换个话题都行。"
    if intent == "PRACTICAL_TRAINING":
        return "可以一起拆。你把练的项目和最容易乱的那个动作告诉我，我先帮你整理成下一次上车能直接试的一小步。"
    if history:
        return "我记得我们刚才聊到的情况。你可以接着说具体哪里最难受或最卡，我会结合前面一起回应。"
    return "我在。和学车有关的困惑、进度、考试压力或者驾校沟通，都可以直接说。"


def generate_conversation_reply(
    db: Session,
    conversation: Conversation,
    student: Student,
    intent: str,
    skill_id: str,
    user_text: str,
    evidence: list[dict] | None = None,
) -> str:
    settings = get_settings()
    history = list(db.scalars(
        select(AgentTurn)
        .where(AgentTurn.conversation_id == conversation.id)
        .order_by(AgentTurn.created_at.desc())
        .limit(8)
    ))[::-1]
    messages: list[dict[str, str]] = [{"role": "system", "content": COMPANION_CONVERSATION_PROMPT}]
    for turn in history:
        messages.extend([
            {"role": "user", "content": turn.user_text},
            {"role": "assistant", "content": turn.assistant_text},
        ])
    context = {
        "current_intent": intent,
        "student_context": {"region": student.region, "license_type": student.license_type, "subject": student.subject},
        "authoritative_evidence": evidence or [],
        "user_message": user_text,
    }
    messages.append({"role": "user", "content": json.dumps(context, ensure_ascii=False)})

    reply = ""
    model_id = "local-safe-fallback"
    token_usage = 0
    is_fallback = True
    if settings.dashscope_api_key:
        try:
            for attempt in range(2):
                response = httpx.post(
                    f"{settings.dashscope_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
                    json={
                        "model": settings.light_model_id,
                        "messages": messages,
                        "temperature": 0.55 if attempt else 0.65,
                        "max_tokens": 500,
                        "enable_thinking": False,
                    },
                    timeout=settings.model_timeout_seconds,
                )
                response.raise_for_status()
                body = response.json()
                reply = str(body["choices"][0]["message"]["content"]).strip()
                if reply and not _invalid_reply(reply):
                    model_id = settings.light_model_id
                    token_usage += int(body.get("usage", {}).get("total_tokens", 0))
                    is_fallback = False
                    break
                token_usage += int(body.get("usage", {}).get("total_tokens", 0))
                messages.extend([
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": "这段草稿包含无依据保证、淡化处境或猜题暗示。请严格按系统规则重写，承接具体上下文并给克制、可执行的回应。"},
                ])
            if not reply or _invalid_reply(reply):
                raise ValueError("conversation response failed policy validation")
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            reply = ""
    if not reply:
        reply = _fallback(intent, user_text, evidence, history)

    db.add(AgentTurn(
        conversation_id=conversation.id,
        student_id=student.id,
        user_text=user_text,
        assistant_text=reply,
        intent=intent,
        skill_id=skill_id,
        model_id=model_id,
        prompt_version=PROMPT_VERSION,
        token_usage=token_usage,
        is_fallback=is_fallback,
    ))
    db.commit()
    return reply
