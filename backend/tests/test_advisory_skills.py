from app.pe import classify_intent
from app.skills import resolve_skill
from app.skills.advisory import advisory_response
from app.core.database import SessionLocal
from app.knowledge.advisory_service import import_advisory_documents, retrieve_advisory_documents


def test_advisory_intents_are_fast_rule_routes():
    cases = {
        "在杭州最快多久能拿证？": "LICENSE_TIMELINE",
        "最快拿证周期要多久？": "LICENSE_TIMELINE",
        "最近学时有什么新规定？": "POLICY_REGULATION",
        "从报名到拿证的学车流程是什么？": "LEARNING_PROCESS",
        "驾校班型和收费应该怎么选？": "INDUSTRY_KNOWLEDGE",
        "我总觉得考不过，压力特别大": "EMOTIONAL_SUPPORT",
        "学车很麻烦": "EMOTIONAL_SUPPORT",
        "你好呀": "GREETING",
    }
    for text, expected in cases.items():
        result = classify_intent(text, False)
        assert result.intent == expected
        assert result.source == "rule"


def test_policy_and_timeline_answers_do_not_invent_fixed_rules():
    policy = resolve_skill("POLICY_REGULATION", "最近有新规吗？")
    assert policy.spec.id == "driving_advisor"
    assert policy.assistant_message is None
    policy_fallback = advisory_response("POLICY_REGULATION", "最近有新规吗？")
    assert "省市" in policy_fallback
    assert "生效" in policy_fallback

    timeline = resolve_skill("LICENSE_TIMELINE", "最快多久拿证？")
    assert timeline.assistant_message is None
    timeline_fallback = advisory_response("LICENSE_TIMELINE", "最快多久拿证？")
    assert "不能只用一个固定天数" in timeline_fallback
    assert "所在城市" in timeline_fallback


def test_anxiety_support_is_specific_and_non_judgmental():
    decision = resolve_skill("EMOTIONAL_SUPPORT", "我怕挂科，越来越没信心")
    assert decision.spec.id == "companion_chat"
    assert decision.assistant_message is None
    fallback = advisory_response("EMOTIONAL_SUPPORT", "我怕挂科，越来越没信心")
    assert "等同于学不会" in fallback
    assert "最没把握的科目" in fallback


def test_authoritative_timeline_knowledge_is_retrievable():
    with SessionLocal() as db:
        assert import_advisory_documents(db) == 5
        evidence = retrieve_advisory_documents(db, "最快拿证周期要多久？", "LICENSE_TIMELINE", "C1", "全国")
    assert evidence
    assert "C1/C2考试预约最低间隔" in evidence[0]["title"]
    response = advisory_response("LICENSE_TIMELINE", "最快拿证周期要多久？", evidence)
    assert "最早预约条件" in response
    assert "ga.wuxi.gov.cn" in response
