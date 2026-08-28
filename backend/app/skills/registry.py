from app.skills.contracts import SkillDecision, SkillSpec
SAFETY_RESPONSES = {
    "SENSITIVE_CONTENT": "先保护好你的隐私：不要发送身份证、手机号、银行卡、验证码或缴费单。只保留题干和选项就够了。",
    "PROMPT_INJECTION": "这段内容在要求我改变规则或泄露内部信息，我不会执行。我们可以继续聊学车、讲题，或者直接开始刷题。",
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
    SkillSpec("mnemonic_coach", "口诀陪练", ("MNEMONIC_HELP",), "RESPOND", ("conversation",), ("reviewed_mnemonics",), "只用已编排口诀帮助记忆", "没有合适口诀时不生造"),
    SkillSpec("learning_diagnosis", "学习诊断", ("LEARNING_PROGRESS",), "RESPOND", ("student_progress",), ("progress_tracker",), "给出下一步学习建议", "引导进入进度页"),
    SkillSpec("school_service", "驾校服务", ("SCHOOL_SERVICE", "HUMAN_HELP"), "RESPOND", ("student_school",), ("school_profile", "principal_ticket"), "回答或形成校长工单", "保护隐私后转校长"),
    SkillSpec("practical_companion", "实操陪练", ("PRACTICAL_TRAINING",), "RESPOND", ("license_type", "subject"), ("training_playbook",), "把动作拆成可练习步骤", "追问具体项目与卡点"),
    SkillSpec("driving_advisor", "驾培知识顾问", ("INDUSTRY_KNOWLEDGE", "LEARNING_PROCESS", "POLICY_REGULATION", "LICENSE_TIMELINE"), "RESPOND", ("region", "license_type", "subject"), ("advisory_knowledge", "policy_rag"), "提供有边界且可执行的行业与流程建议", "地区或时效不明确时先追问，不猜政策"),
    SkillSpec("product_guide", "产品引导", ("PRODUCT_HELP",), "RESPOND", (), ("capability_catalog",), "说明可用能力和边界", "返回学习入口"),
    SkillSpec("companion_chat", "陪伴交流", ("GREETING", "CHITCHAT", "EMOTIONAL_SUPPORT", "THANKS", "OUT_OF_SCOPE"), "RESPOND", ("conversation",), ("tone_policy",), "自然回应并给出合适下一步", "不强行导向刷题"),
)


def resolve_skill(intent: str, user_text: str = "", evidence: list[dict] | None = None) -> SkillDecision:
    spec = next((item for item in SKILLS if intent in item.intents), None)
    if spec is None:
        spec = next(item for item in SKILLS if item.id == "companion_chat")
        intent = "OUT_OF_SCOPE"
    return SkillDecision(
        spec=spec,
        action=spec.action,
        destination=DESTINATIONS.get(intent),
        assistant_message=SAFETY_RESPONSES.get(intent),
    )
