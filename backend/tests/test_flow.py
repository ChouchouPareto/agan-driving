import json
import re

import httpx
from app.services import AIService, QUESTION_BANK


def create_question(client, auth, text):
    conversation = client.post("/api/v1/conversations", headers=auth, json={}).json()
    return client.post("/api/v1/questions", headers=auth, json={"conversation_id": conversation["id"], "text": text}).json()


def parse_done(response):
    match = re.search(r"event: done\ndata: (.+)\n\n", response.text)
    assert match, response.text
    return json.loads(match.group(1))


def test_invalid_invitation_uses_unified_error(client):
    response = client.post("/api/v1/auth/invitations/verify", json={"code": "WRONG"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_INVITATION"


def test_standard_question_is_deterministic(client, auth):
    question = create_question(client, auth, "驾驶机动车通过没有交通信号的交叉路口怎样行驶？")
    response = client.get(f"/api/v1/questions/{question['id']}/stream", headers=auth)
    payload = parse_done(response)
    assert payload["direct_answer"] == "减速慢行，并让右方道路来车先行。"
    assert payload["route"] == "standard_question"
    assert payload["evidence"][0]["source_type"] == "question_bank"


def test_unknown_question_refuses_and_creates_ticket(client, auth):
    question = create_question(client, auth, "请告诉我一个没有任何来源的新规定")
    payload = parse_done(client.get(f"/api/v1/questions/{question['id']}/stream", headers=auth))
    assert payload["risk_codes"] == ["NO_TRUSTED_MATCH"]
    ticket = client.post("/api/v1/review-tickets", headers=auth, json={"question_id": question["id"], "risk_codes": payload["risk_codes"]})
    assert ticket.status_code == 200
    status = client.get(f"/api/v1/review-tickets/{ticket.json()['id']}", headers=auth).json()
    assert status["label"] == "校长在摸鱼"
    assert "2小时" in status["sla"]


def test_second_explanation_keeps_standard_answer(client, auth):
    question = create_question(client, auth, "机动车在道路上发生故障难以移动时首先应当持续开启危险报警闪光灯")
    payload = parse_done(client.get(f"/api/v1/questions/{question['id']}/stream", headers=auth))
    second = client.post(f"/api/v1/answers/{payload['id']}/explain-again", headers=auth)
    assert second.status_code == 200
    assert second.json()["direct_answer"] == payload["direct_answer"]
    assert second.json()["detail"] != payload["detail"]


def test_invalid_session_cannot_read_conversation(client, auth):
    conversation = client.post("/api/v1/conversations", headers=auth, json={}).json()
    response = client.get(f"/api/v1/conversations/{conversation['id']}", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_SESSION"


def test_question_submission_is_idempotent_and_can_be_restored(client, auth):
    conversation = client.post("/api/v1/conversations", headers=auth, json={}).json()
    headers = {**auth, "Idempotency-Key": "same-question-request"}
    payload = {"conversation_id": conversation["id"], "text": "驾驶机动车通过没有交通信号的交叉路口怎样行驶？"}
    first = client.post("/api/v1/questions", headers=headers, json=payload).json()
    second = client.post("/api/v1/questions", headers=headers, json=payload).json()
    assert second["id"] == first["id"]
    parse_done(client.get(f"/api/v1/questions/{first['id']}/stream", headers=auth))
    restored = client.get(f"/api/v1/questions/{first['id']}", headers=auth)
    assert restored.status_code == 200
    assert restored.json()["answer"]["direct_answer"] == "减速慢行，并让右方道路来车先行。"


def test_question_restore_is_scoped_to_student(client, auth):
    question = create_question(client, auth, "这是一道待核查问题")
    response = client.get(f"/api/v1/questions/{question['id']}", headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401


def test_idempotency_key_rejects_different_payload(client, auth):
    conversation = client.post("/api/v1/conversations", headers=auth, json={}).json()
    headers = {**auth, "Idempotency-Key": "conflicting-request"}
    client.post("/api/v1/questions", headers=headers, json={"conversation_id": conversation["id"], "text": "第一个问题"})
    conflict = client.post("/api/v1/questions", headers=headers, json={"conversation_id": conversation["id"], "text": "第二个问题"})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_teaching_model_cannot_change_locked_standard_answer(monkeypatch):
    class Response:
        def raise_for_status(self): return None
        def json(self):
            return {"choices": [{"message": {"content": json.dumps({
                "short_reason": "先减速才能留出观察和让行的时间。",
                "detail": "把无信号路口理解为没有人指挥的排队口：先慢下来，再按让行规则确认通行顺序。",
                "common_mistake": "只记得减速，却忘记确认右方来车。",
                "direct_answer": "故意伪造的错误答案",
            }, ensure_ascii=False)} }], "usage": {"total_tokens": 123}}
    service = AIService()
    monkeypatch.setattr(service.settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(service.settings, "main_model_id", "test-model")
    monkeypatch.setattr("app.services.httpx.post", lambda *args, **kwargs: Response())
    match = QUESTION_BANK["驾驶机动车通过没有交通信号的交叉路口怎样行驶"]
    answer = service.answer("测试题", match)
    assert answer.direct_answer == match["answer"]
    assert answer.detail.startswith("把无信号路口")
    assert service.token_usage == 123
    assert service.is_mock is False


def test_teaching_model_failure_falls_back_to_reviewed_explanation(monkeypatch):
    service = AIService()
    monkeypatch.setattr(service.settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(service.settings, "model_max_retries", 0)
    monkeypatch.setattr("app.services.httpx.post", lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("offline")))
    match = QUESTION_BANK["驾驶机动车通过没有交通信号的交叉路口怎样行驶"]
    answer = service.answer("测试题", match)
    assert answer.detail == match["detail"]
    assert service.error_type == "TEACHING_MODEL_FALLBACK"
