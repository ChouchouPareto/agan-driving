import json
import re


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
