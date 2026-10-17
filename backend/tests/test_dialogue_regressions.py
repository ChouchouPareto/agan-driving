import json
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, text

from app.core.config import get_settings
from app.core.database import Base, SessionLocal
from app.core.migrations import initialize_database
from app.knowledge.service import ModelGateway, activate, build_index, import_bank, run_evaluation
from app.models import ReviewTicket
from app.skills import conversation as conversation_service


def send(client, auth, message, conversation_id=None):
    response = client.post("/api/v1/agent/messages", headers=auth, json={"text": message, "conversation_id": conversation_id})
    assert response.status_code == 200
    return response.json()


def fake_model(monkeypatch, reply="我们接着聊你刚才说的事。"):
    requests = []
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": reply}}], "usage": {"total_tokens": 12}}
    def post(*args, **kwargs):
        requests.append(kwargs["json"])
        return Response()
    monkeypatch.setattr(get_settings(), "dashscope_api_key", "unit-test-only")
    monkeypatch.setattr(conversation_service.httpx, "post", post)
    return requests


def test_negated_tools_and_emotional_followup_stay_in_chat(client, auth):
    first = send(client, auth, "我不想刷题")
    second = send(client, auth, "别打开错题本，我想聊聊为什么总犯同一种错", first["conversation_id"])
    third = send(client, auth, "为什么？", first["conversation_id"])
    assert all(item["action"] == "RESPOND" and item["destination"] is None for item in (first, second, third))
    assert client.get(f"/api/v1/conversations/{first['conversation_id']}", headers=auth).json()["questions"] == []


def test_privacy_distinguishes_material_question_from_actual_data(client, auth):
    assert send(client, auth, "报名要带身份证吗？不要记录我的个人信息")["intent"] == "SCHOOL_SERVICE"
    assert send(client, auth, "这是我的身份证和缴费单")["intent"] == "SENSITIVE_CONTENT"
    assert send(client, auth, "我的手机号是13800138000")["intent"] == "SENSITIVE_CONTENT"


def test_c2_followup_has_facts_and_conversation_profile(client, auth, monkeypatch):
    requests = fake_model(monkeypatch)
    first = send(client, auth, "最快拿证周期要多久？")
    second = send(client, auth, "杭州，C2，已经通过科目一，每周只能周末去", first["conversation_id"])
    assert second["intent"] == "LICENSE_TIMELINE"
    context = json.loads(requests[-1]["messages"][-1]["content"])
    assert context["student_context"]["license_type"] == "C2"
    assert context["student_context"]["region"] == "杭州"
    assert context["student_context"]["learning_stage"] == "科目一已通过"
    assert "C2满20日" in second["assistant_message"]


def test_untrusted_policy_numbers_are_removed(client, auth, monkeypatch):
    fake_model(monkeypatch, "C2科目二必须满99天才能预约。")
    result = send(client, auth, "最快拿证周期要多久？")
    assert "99" not in result["assistant_message"]
    assert "C1/C2取得学习驾驶证明满10日" in result["assistant_message"]


def test_theory_history_is_available_to_chat_and_mnemonics_are_locked(client, auth, monkeypatch):
    first = send(client, auth, "驾驶机动车通过没有交通信号的交叉路口怎样行驶？")
    client.get(f"/api/v1/questions/{first['question_id']}/stream", headers=auth)
    requests = fake_model(monkeypatch, "三长一短选最短，三短一长选最长。")
    result = send(client, auth, "有没有什么口诀？", first["conversation_id"])
    assert "三长一短" not in result["assistant_message"]
    assert "无灯无标先减速" in result["assistant_message"]
    assert requests == []  # Reviewed mnemonics must never depend on generated wording.
    switched = send(client, auth, "给个酒驾的口诀，不是刚才路口那题", first["conversation_id"])
    assert "喝酒不开车" in switched["assistant_message"]
    assert "无灯" not in switched["assistant_message"]
    send(client, auth, "为什么教练让我等了这么久", first["conversation_id"])
    assert any("没有交通信号" in message["content"] for message in requests[0]["messages"] if message["role"] == "user")


def test_progress_skill_uses_owned_attempts(client, auth):
    with SessionLocal() as db:
        fixture = Path(__file__).parent / "fixtures/knowledge/sample_bank.json"
        version = build_index(db, import_bank(db, fixture, name="test", supplier="test", version_label="stats").id)
        run_evaluation(db, version.id); activate(db, version.id)
    question = client.get("/api/v1/practice/questions", headers=auth).json()["items"][0]
    answer = client.post(f"/api/v1/practice/questions/{question['id']}/answer", headers=auth, json={"answer": "A"}).json()
    result = send(client, auth, "我的正确率和薄弱点是什么？")
    assert "1 次答题记录" in result["assistant_message"]
    assert f"答对 {int(answer['correct'])} 次" in result["assistant_message"]
    assert "看不到" not in result["assistant_message"]


def test_handoff_requires_click_and_is_idempotent_and_owned(client, auth):
    result = send(client, auth, "帮我转人工，联系校长")
    assert result["handoff_available"] is True
    with SessionLocal() as db:
        assert db.scalar(select(ReviewTicket)) is None
    url = f"/api/v1/conversations/{result['conversation_id']}/review-ticket"
    first = client.post(url, headers=auth)
    second = client.post(url, headers=auth)
    assert first.status_code == 200 and first.json() == second.json()
    detail = client.get(f"/api/v1/review-tickets/{first.json()['id']}", headers=auth).json()
    assert "联系校长" in detail["question"]["text"]
    assert client.post(url).status_code == 401
    assert client.post("/api/v1/conversations/not-owned/review-ticket", headers=auth).status_code == 404


def test_history_preserves_chat_and_navigation_on_refresh(client, auth):
    first = send(client, auth, "你好")
    send(client, auth, "我要刷题", first["conversation_id"])
    history = client.get(f"/api/v1/conversations/{first['conversation_id']}", headers=auth).json()
    assert [turn["user"] for turn in history["turns"]] == ["你好", "我要刷题"]
    assert history["turns"][-1]["destination"] == "/practice"


def test_old_sqlite_is_migrated_and_backed_up(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE knowledge_chunks DROP COLUMN embedding"))
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('b73d9012f5aa')"))
    initialize_database(engine)
    assert "embedding" in {column["name"] for column in inspect(engine).get_columns("knowledge_chunks")}
    assert len(list((tmp_path / "backups").glob("*.db"))) == 1
    initialize_database(engine)
    assert len(list((tmp_path / "backups").glob("*.db"))) == 1
    engine.dispose()


def test_policy_facts_cite_each_source_and_do_not_claim_freshness(client, auth):
    result = send(client, auth, "最近学时有什么新规定？")
    reply = result["assistant_message"]
    assert "历史资料" in reply
    assert "三年" not in reply  # unrelated driving-proof validity
    assert "大纲" in reply


def test_policy_rejects_invented_interface():
    from app.skills.runtime import SkillContext, invalid_skill_reply
    assert invalid_skill_reply("界面会给你展示详细的时间参考", "LICENSE_TIMELINE", SkillContext())


def test_reply_validator_rejects_invented_events_and_privacy_guarantees():
    from app.skills.conversation import _invalid_reply
    assert _invalid_reply("被当众指责确实难过", "教练说了我")
    assert not _invalid_reply("被当众指责确实难过", "教练当众说了我")
    assert _invalid_reply("我们的对话不会保存你的身份证号或手机号等隐私数据")
