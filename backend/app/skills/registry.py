from app.skills.contracts import SkillDecision, SkillSpec


RESPONSES = {
    "GREETING": "嗨，我在呢。今天想问一道题、刷几道题，还是聊聊练车时遇到的困难？",
    "CHITCHAT": "我在。想随便聊一会儿可以，想问题、刷题或者吐槽练车，我也都接得住。",
    "EMOTIONAL_SUPPORT": "听起来你现在有些不好受。我们先不用解决所有问题，你可以告诉我最担心的是哪一步，我陪你一点点拆开。",
    "THANKS": "不用客气，我们是学车搭子。你想继续追问、刷两道题巩固一下，或者先歇会儿都可以。",
    "OUT_OF_SCOPE": "这个话题我未必专业。如果和学车有关，你告诉我哪个科目、卡在哪一步，我陪你一起拆清楚。",
    "PRODUCT_HELP": "我是阿甘学车里的超级驾陪。我会先理解你想问知识、刷题还是聊练车，再调用对应能力；科目一结论以题库为准，没有可靠依据时不会猜。",
    "PRACTICAL_TRAINING": "先别急，实操卡住通常是动作还没拆细。告诉我具体项目和卡住的那一步，我帮你压缩成容易记的动作顺序。",
    "SENSITIVE_CONTENT": "先保护好你的隐私：不要发送身份证、手机号、银行卡、验证码或缴费单。只保留题干和选项就够了。",
    "PROMPT_INJECTION": "这段内容在要求我改变规则或泄露内部信息，我不会执行。我们可以继续聊学车、讲题，或者直接开始刷题。",
    "SCHOOL_SERVICE": "这是驾校服务问题。我可以先帮你把情况整理清楚，再通过“不懂就问校长”提交；请不要发送身份证或缴费信息。",
    "HUMAN_HELP": "可以，我先帮你把问题整理清楚再提交给校长。告诉我发生了什么就行，不要发送身份证、缴费单等敏感信息。",
    "LEARNING_PROGRESS": "你的学习进度已经记下来了。你可以查看正确率和错题，也可以让我直接带你复习当前薄弱点。",
}

DESTINATIONS = {
    "START_PRACTICE": "/practice",
    "WRONG_QUESTIONS": "/practice?mode=wrong",
    "FAVORITES": "/practice?mode=favorites",
    "MOCK_EXAM": "/exam",
}

SKILLS = (
    SkillSpec("safety_guard", "安全防护", ("SENSITIVE_CONTENT", "PROMPT_INJECTION"), "RESPOND", ("user_message",), ("pii_detector", "injection_detector"), "风险内容不进入模型", "安全拒答并返回学习入口"),
    SkillSpec("practice_coach", "刷题陪练", tuple(DESTINATIONS), "NAVIGATE", ("license_type", "subject"), ("practice_bank", "progress_tracker"), "进入目标练习模式", "返回可用的练习入口"),
    SkillSpec("theory_tutor", "理论答疑", ("QUESTION_ANSWER", "FOLLOW_UP"), "ANSWER", ("license_type", "subject", "conversation"), ("rag_retriever", "answer_lock", "teaching_explainer"), "给出有题库依据的解释", "无可靠依据时不猜并提示核查"),
    SkillSpec("learning_diagnosis", "学习诊断", ("LEARNING_PROGRESS",), "RESPOND", ("student_progress",), ("progress_tracker",), "给出下一步学习建议", "引导进入进度页"),
    SkillSpec("school_service", "驾校服务", ("SCHOOL_SERVICE", "HUMAN_HELP"), "RESPOND", ("student_school",), ("school_profile", "principal_ticket"), "回答或形成校长工单", "保护隐私后转校长"),
    SkillSpec("practical_companion", "实操陪练", ("PRACTICAL_TRAINING",), "RESPOND", ("license_type", "subject"), ("training_playbook",), "把动作拆成可练习步骤", "追问具体项目与卡点"),
    SkillSpec("product_guide", "产品引导", ("PRODUCT_HELP",), "RESPOND", (), ("capability_catalog",), "说明可用能力和边界", "返回学习入口"),
    SkillSpec("companion_chat", "陪伴交流", ("GREETING", "CHITCHAT", "EMOTIONAL_SUPPORT", "THANKS", "OUT_OF_SCOPE"), "RESPOND", ("conversation",), ("tone_policy",), "自然回应并给出合适下一步", "不强行导向刷题"),
)


def resolve_skill(intent: str) -> SkillDecision:
    spec = next((item for item in SKILLS if intent in item.intents), None)
    if spec is None:
        spec = next(item for item in SKILLS if item.id == "companion_chat")
        intent = "OUT_OF_SCOPE"
    return SkillDecision(
        spec=spec,
        action=spec.action,
        destination=DESTINATIONS.get(intent),
        assistant_message=RESPONSES.get(intent),
    )
