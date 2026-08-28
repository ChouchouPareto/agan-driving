from app.knowledge.mnemonics import mnemonic_for


def test_reviewed_mnemonic_matches_known_question():
    result = mnemonic_for("驾驶人抢救伤员变动现场时要标明位置。")
    assert result == "抢救可以移，原位先标记。"


def test_mnemonic_does_not_invent_when_no_reviewed_rule_matches():
    assert mnemonic_for("一道没有被编排过的题") == ""
