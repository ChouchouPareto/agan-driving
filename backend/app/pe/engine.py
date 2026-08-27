import json
import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.pe.prompts import INTENT_CLASSIFIER_PROMPT

INTENTS = {
    "QUESTION_ANSWER", "FOLLOW_UP", "START_PRACTICE", "WRONG_QUESTIONS",
    "FAVORITES", "LEARNING_PROGRESS", "SCHOOL_SERVICE", "HUMAN_HELP",
    "OUT_OF_SCOPE", "SENSITIVE_CONTENT",
}


@dataclass(frozen=True)
class IntentResult:
    intent: str
    confidence: float
    source: str


def _rule_intent(text: str, has_context: bool) -> IntentResult | None:
    value = text.strip()
    rules = [
        (r"身份证|银行卡|缴费单|付款码|财务信息", "SENSITIVE_CONTENT"),
        (r"错题", "WRONG_QUESTIONS"),
        (r"收藏", "FAVORITES"),
        (r"刷题|练题|顺序练习|开始练习|做题", "START_PRACTICE"),
        (r"学习进度|正确率|薄弱点|学得怎么样", "LEARNING_PROGRESS"),
        (r"转人工|问校长|不懂就问校长|找教练", "HUMAN_HELP"),
        (r"报名|缴费|班车|教练安排|考试预约|驾校地址", "SCHOOL_SERVICE"),
    ]
    for pattern, intent in rules:
        if re.search(pattern, value):
            return IntentResult(intent, 0.99, "rule")
    if has_context and (len(value) <= 18 or re.search(r"为什么|怎么理解|没看懂|还是不懂|再讲|上一题|这题|那题|什么意思", value)):
        return IntentResult("FOLLOW_UP", 0.96, "rule")
    if re.search(r"题|驾驶|机动车|交通|道路|车道|标志|扣分|罚款|速度|路口", value):
        return IntentResult("QUESTION_ANSWER", 0.9, "rule")
    return None


def _model_intent(text: str, has_context: bool) -> IntentResult | None:
    settings = get_settings()
    if not settings.dashscope_api_key:
        return None
    payload = {
        "model": settings.light_model_id,
        "messages": [
            {"role": "system", "content": INTENT_CLASSIFIER_PROMPT},
            {"role": "user", "content": f"是否有上一轮题目：{has_context}\n用户消息：{text}"},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    try:
        response = httpx.post(
            f"{settings.dashscope_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
            json=payload,
            timeout=min(settings.model_timeout_seconds, 12),
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        intent = str(parsed.get("intent", "")).upper()
        if intent in INTENTS:
            return IntentResult(intent, float(parsed.get("confidence", 0.7)), "model")
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


def classify_intent(text: str, has_context: bool) -> IntentResult:
    return _rule_intent(text, has_context) or _model_intent(text, has_context) or IntentResult("OUT_OF_SCOPE", 0.6, "fallback")


def resolve_follow_up(text: str, previous_question: str | None) -> str:
    if not previous_question:
        return text.strip()
    return f"{previous_question.strip()}\n学员追问：{text.strip()}"
