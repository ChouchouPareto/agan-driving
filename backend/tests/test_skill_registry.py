from app.skills import SKILLS, resolve_skill


def test_every_skill_has_an_executable_contract():
    assert len(SKILLS) >= 8
    for skill in SKILLS:
        assert skill.id
        assert skill.intents
        assert skill.required_context is not None
        assert skill.tools is not None
        assert skill.completion
        assert skill.fallback


def test_skill_registry_routes_core_learning_scenarios():
    assert resolve_skill("QUESTION_ANSWER").spec.id == "theory_tutor"
    assert resolve_skill("START_PRACTICE").destination == "/practice"
    assert resolve_skill("EMOTIONAL_SUPPORT").spec.id == "companion_chat"
    assert resolve_skill("PROMPT_INJECTION").spec.id == "safety_guard"
