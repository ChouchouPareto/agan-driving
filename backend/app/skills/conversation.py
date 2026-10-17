import json
import re

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AgentTurn, Conversation, Student
from app.pe.prompts import COMPANION_CONVERSATION_PROMPT, PROMPT_VERSION
from app.pe.context import recent_dialogue, learner_context
from app.skills.advisory import advisory_response
from app.skills.runtime import SkillContext, POLICY_INTENTS, invalid_skill_reply


def _invalid_reply(reply: str, learner_words: str = "") -> bool:
    if any(word in reply and word not in learner_words for word in ("当众", "人身攻击", "不想动")):
        return True
    return bool(re.search(r"肯定能过|下次一定|一定能过|费不了多少钱|没什么大不了|靠(?:语感|常识|猜)|系统识别|网络波动|信号没传|更清晰的指令|我一直在线|(?:不会|不|绝不)(?:保存|存储|记录).{0,20}(?:信息|隐私|号码|手机号|身份证)|(?:对话|隐私|信息).{0,12}(?:不保存|不记录|不存储)", reply))


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
    runtime: SkillContext | None = None,
) -> str:
    settings = get_settings()
    runtime = runtime or SkillContext(evidence=evidence or [])
    history = recent_dialogue(db, conversation.id)
    learner_words = "\n".join([turn["user"] for turn in history] + [user_text])
    messages: list[dict[str, str]] = [{"role": "system", "content": COMPANION_CONVERSATION_PROMPT}]
    for turn in history:
        messages.extend([
            {"role": "user", "content": turn["user"]},
            {"role": "assistant", "content": turn["assistant"]},
        ])
    context = {
        "current_intent": intent,
        "student_context": learner_context(student, history, user_text),
        "authoritative_evidence": [] if intent in POLICY_INTENTS or intent == "MNEMONIC_HELP" else runtime.evidence,
        "skill_context": runtime.data,
        "separate_facts": bool(runtime.facts) or intent in POLICY_INTENTS or intent == "MNEMONIC_HELP",
        "user_message": user_text,
    }
    if intent == "GREETING":
        context["response_focus"] = "只用一句日常招呼。不念学员档案，不猜测刚报名或紧张，不催开始刷题。"
    elif intent == "EMOTIONAL_SUPPORT":
        context["response_focus"] = "只回应当前具体处境，40到100字，不堆安慰。没有说明的不要猜。不安排休息、呼吸或放手机。不要把抱怨转成学习任务。"
        if any("教练" in t for t in [user_text, *[turn["user"] for turn in history[-3:]]]):
            context["response_focus"] += "不要替教练猜原因、劝忍耐或转去复盘错题。先听用户把事情说完，不默认每轮都要教他怎么对教练说；前面已给过建议就别重复。"
        if "先听我说" in user_text:
            context["response_focus"] = "用户只要求你听他继续说。一句简短回应就好，不提建议、不总结之前的情绪，不安排任何动作。"
    elif intent in {"CHITCHAT", "OUT_OF_SCOPE"}:
        context["response_focus"] = "允许日常闲聊。汽车喜好等话题可以先聊预算和使用需求，不编价格或保证保值。不要以超出驾陪范围拒绝闲聊，更不要劝对方先刷题。"
    elif intent in POLICY_INTENTS:
        context["response_focus"] = "先回应学员已说明的限制（如只能周末练车），最多两句话。不要编写法规、流程步骤或数字；不要承诺任何界面将显示考位、时间预测或排期。你没有实时排期能力。资料摘要会紧接在你的回答后显示，不用提到界面、系统或展示。"
    elif intent in {"HUMAN_HELP", "SCHOOL_SERVICE"}:
        context["response_focus"] = "简短说清你知道和不知道什么。没有当地材料清单、班车时间、收费或约考数据，不能猜。可以请校长核实，点击确认才提交。不说‘正式渠道、系统工单、专人跟进’，用‘请校长看看’就好。别承诺服务时限或隐私不留存。"
    model = settings.main_model_id if (intent == "EMOTIONAL_SUPPORT" or intent in POLICY_INTENTS) and settings.main_model_id not in {"", "mock-main"} else settings.light_model_id
    messages.append({"role": "user", "content": json.dumps(context, ensure_ascii=False)})

    reply = ""
    model_id = "local-safe-fallback"
    token_usage = 0
    is_fallback = True
    curated_only = intent == "MNEMONIC_HELP" and bool(runtime.facts)
    if curated_only:
        model_id, is_fallback = "reviewed-mnemonic", False
    if settings.dashscope_api_key and not curated_only:
        try:
            for attempt in range(2):
                response = httpx.post(
                    f"{settings.dashscope_base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
                    json={
                        "model": model,
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
                if reply and not _invalid_reply(reply, learner_words) and not invalid_skill_reply(reply, intent, runtime):
                    model_id = model
                    token_usage += int(body.get("usage", {}).get("total_tokens", 0))
                    is_fallback = False
                    break
                token_usage += int(body.get("usage", {}).get("total_tokens", 0))
                messages.extend([
                    {"role": "assistant", "content": reply},
                    {"role": "user", "content": "草稿未通过验证。请只用一两句口语回应学员的具体处境。不补写数字、规则或口诀，不作猜测，不重复已知问题；不要提到任何界面、系统功能或预测。"},
                ])
            if not reply or _invalid_reply(reply, learner_words) or invalid_skill_reply(reply, intent, runtime):
                raise ValueError("conversation response failed policy validation")
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            reply = ""
    if not reply:
        if runtime.facts:
            reply = ""
        elif intent in POLICY_INTENTS:
            reply = "这次还没有查到足够的依据，具体安排需要请当地交管部门或驾校确认。"
        elif intent == "MNEMONIC_HELP":
            reply = "这段内容还没有匹配到核对过的口诀。可以把题目发来，我们先把规则弄明白。"
        elif runtime.handoff_available:
            reply = "可以请校长看看。点下方确认按钮后，会把你在这次对话里提到的问题提交过去。"
        elif intent == "PRACTICAL_TRAINING" and "压线" in user_text:
            reply = "倒库压线先看发生在哪一步：是进库时压侧边，还是倒进后压库底？点位要结合你练的车，请教练在现场帮你核对。"
        elif intent == "EMOTIONAL_SUPPORT" and re.search(r"不想|别打开|不要", user_text):
            reply = "那就先不打开练习。你刚才想说的事，我接着听。"
        else:
            reply = _fallback(intent, user_text, evidence, history)
    if runtime.facts:
        reply = "\n\n".join(part for part in (reply, runtime.facts) if part)
    elif intent == "MNEMONIC_HELP" and "还没有匹配" not in reply:
        reply += "\n这次还没有匹配到核对过的口诀，可以把具体题目发来。"

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
