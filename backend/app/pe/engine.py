import json
import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.pe.prompts import INTENT_CLASSIFIER_PROMPT

INTENTS = {
    "QUESTION_ANSWER", "FOLLOW_UP", "START_PRACTICE", "WRONG_QUESTIONS",
    "FAVORITES", "LEARNING_PROGRESS", "SCHOOL_SERVICE", "HUMAN_HELP",
    "GREETING", "CHITCHAT", "EMOTIONAL_SUPPORT", "THANKS", "PRODUCT_HELP",
    "PRACTICAL_TRAINING", "MOCK_EXAM", "INDUSTRY_KNOWLEDGE",
    "LEARNING_PROCESS", "POLICY_REGULATION", "LICENSE_TIMELINE",
    "MNEMONIC_HELP", "OUT_OF_SCOPE", "SENSITIVE_CONTENT", "PROMPT_INJECTION",
}


@dataclass(frozen=True)
class IntentResult:
    intent: str
    confidence: float
    source: str


def _rule_intent(text: str, has_context: bool) -> IntentResult | None:
    value = text.strip()
    compact = re.sub(r"[\s-]", "", value)
    if re.search(r"忽略.{0,10}(之前|以上|系统|所有).{0,10}(指令|提示)|系统提示词|开发者消息|越狱|jailbreak|绕过.{0,10}(规则|限制|安全)|泄露.{0,10}(提示词|密钥|配置)|输出.{0,10}(系统|隐藏).{0,10}(提示词|指令)|扮演.{0,20}(不受限制|开发者模式)", value, re.I):
        return IntentResult("PROMPT_INJECTION", 0.99, "security_rule")
    if (
        re.search(r"身份证|银行卡|缴费单|付款码|财务信息|家庭住址|登录密码|短信验证码|支付密码", value)
        or re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", compact)
        or re.search(r"(?<!\d)\d{17}[\dXx](?!\d)", compact)
        or re.search(r"(?<!\d)\d{16,19}(?!\d)", compact)
        or re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", value)
    ):
        return IntentResult("SENSITIVE_CONTENT", 0.99, "security_rule")
    if re.search(r"(?:不想|不愿|先不|暂时不|不要|别|不想再).{0,5}(?:刷题|练题|做题|模拟考)|(?:刷题|练题|做题).{0,4}(?:不动|烦了|累了)", value):
        return IntentResult("EMOTIONAL_SUPPORT", 0.99, "negation_rule")
    if re.search(r"口诀|怎么记|记忆方法|好记的方法", value):
        return IntentResult("MNEMONIC_HELP", 0.98, "rule")
    rules = [
        (r"模拟考|模拟考试|考试模式|测一下能不能过", "MOCK_EXAM"),
        (r"错题", "WRONG_QUESTIONS"),
        (r"收藏", "FAVORITES"),
        (r"刷题|练题|顺序练习|开始练习|做题", "START_PRACTICE"),
        (r"学习进度|正确率|薄弱点|学得怎么样", "LEARNING_PROGRESS"),
        (r"转人工|问校长|不懂就问校长|找教练", "HUMAN_HELP"),
        (r"(驾驶证|驾照).{0,8}(还没|没有|迟迟).{0,8}(拿|发|出)|什么时候.{0,4}(拿证|发证)", "LICENSE_TIMELINE"),
        (r"最快.{0,6}(拿证|取证)|(拿证|取证).{0,8}(多久|周期|时间)|多久.{0,6}(拿证|取证)|学车.{0,6}(多久|周期)", "LICENSE_TIMELINE"),
        (r"政策|法规|新规|学时.{0,4}(要求|规定)|考试.{0,4}(间隔|规定)|有效期", "POLICY_REGULATION"),
        (r"学车流程|报名后.{0,8}(做什么|怎么学)|先考什么|下一步.{0,6}(学|练|考)|从报名到拿证", "LEARNING_PROCESS"),
        (r"驾培行业|驾校.{0,6}(怎么选|班型|收费|服务)|教练.{0,6}(安排|行业)|退学|转校", "INDUSTRY_KNOWLEDGE"),
        (r"报名|缴费|班车|教练安排|考试预约|驾校地址|教练.{0,10}(等|迟到|没来|不回|联系不上|放鸽子)", "SCHOOL_SERVICE"),
    ]
    for pattern, intent in rules:
        if re.search(pattern, value):
            return IntentResult(intent, 0.99, "rule")
    if re.fullmatch(r"(?:你好|您好|嗨|哈喽|hello|hi|早上好|下午好|晚上好)(?:呀|啊|哈|哇)?[！!。,.，\s]*", value, re.I):
        return IntentResult("GREETING", 0.99, "rule")
    if re.search(r"谢谢|感谢|辛苦了|明白了|知道了|懂了", value):
        return IntentResult("THANKS", 0.96, "rule")
    if re.search(r"(?:你的|这个)?系统.{0,8}(?:设置|配置|工作)|你是怎么工作的|你用的什么模型|你的知识库|你会什么|怎么使用你", value):
        return IntentResult("PRODUCT_HELP", 0.98, "rule")
    if re.search(r"科目[二三四]|倒车入库|侧方停车|坡道起步|直角转弯|曲线行驶|百米加减挡|靠边停车|离合器|换挡|路考", value):
        return IntentResult("PRACTICAL_TRAINING", 0.98, "rule")
    if re.search(r"不开心|难过|焦虑|紧张|害怕|压力大|好烦|烦死|崩溃|好累|心累|麻烦|不想学|不想继续|学不动|考不过|没信心|又?挂了怎么办|考试没过|又要补考", value):
        return IntentResult("EMOTIONAL_SUPPORT", 0.98, "rule")
    if re.search(r"你是谁|你能做什么|陪我聊|聊会儿|无聊|讲个笑话", value) or re.fullmatch(r"(?:嘿+|哈+|哈哈+|嘻嘻+|呵呵+|嗯+|哦+|好吧|行吧|在吗|干嘛呢)[~～!！。,.，\s]*", value):
        return IntentResult("CHITCHAT", 0.95, "rule")
    if has_context:
        short_follow_up = re.fullmatch(r"(?:为什么|为啥|什么意思|然后呢|所以呢)[？?!！。,.  ]*", value)
        explicit_question_reference = re.search(r"^(?:上一题|刚才那题|这题|那题|这个答案|刚才的答案)", value)
        explanation_request = re.search(r"^(?:怎么理解|没看懂|还是不懂|再讲(?:一次|一遍)?|换个说法)[？?!！。,.  ]*$", value)
        if short_follow_up or explicit_question_reference or explanation_request:
            return IntentResult("FOLLOW_UP", 0.96, "rule")
    if re.search(r"题|驾驶|机动车|交通|道路|车道|标志|扣分|罚款|速度|路口|酒驾|醉驾|驾驶证|超车|停车|灯光|事故|高速|轮胎|方向盘", value):
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
            timeout=min(settings.model_timeout_seconds, 3),
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
