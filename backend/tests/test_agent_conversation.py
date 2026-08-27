import json
import re


def done(response):
    match = re.search(r"event: done\ndata: (.+)\n\n", response.text)
    assert match, response.text
    return json.loads(match.group(1))


def send(client, auth, text, conversation_id=None):
    return client.post("/api/v1/agent/messages", headers=auth, json={"conversation_id": conversation_id, "text": text})


def test_agent_routes_practice_without_creating_question(client, auth):
    result = send(client, auth, "我要刷题").json()
    assert result["intent"] == "START_PRACTICE"
    assert result["action"] == "NAVIGATE"
    assert result["destination"] == "/practice"
    conversation = client.get(f"/api/v1/conversations/{result['conversation_id']}", headers=auth).json()
    assert conversation["questions"] == []


def test_agent_business_intent_has_priority_over_short_follow_up(client, auth):
    first = send(client, auth, "交叉路口怎样行驶？").json()
    result = send(client, auth, "我想练一下错题", first["conversation_id"]).json()
    assert result["intent"] == "WRONG_QUESTIONS"
    assert result["destination"] == "/practice?mode=wrong"


def test_agent_follow_up_inherits_previous_question(client, auth):
    first = send(client, auth, "驾驶机动车通过没有交通信号的交叉路口怎样行驶？").json()
    first_answer = done(client.get(f"/api/v1/questions/{first['question_id']}/stream", headers=auth))
    assert first_answer["route"] == "standard_question"
    follow = send(client, auth, "为什么？", first["conversation_id"]).json()
    assert follow["intent"] == "FOLLOW_UP"
    follow_answer = done(client.get(f"/api/v1/questions/{follow['question_id']}/stream", headers=auth))
    assert follow_answer["direct_answer"] == first_answer["direct_answer"]
    conversation = client.get(f"/api/v1/conversations/{first['conversation_id']}", headers=auth).json()
    assert len(conversation["questions"]) == 2
    assert conversation["questions"][1]["resolved_text"].startswith(conversation["questions"][0]["text"])
    assert conversation["questions"][1]["prompt_version"] == "pe-v1.0"


def test_agent_blocks_sensitive_content(client, auth):
    result = send(client, auth, "这是我的身份证和缴费单").json()
    assert result["intent"] == "SENSITIVE_CONTENT"
    assert result["action"] == "RESPOND"
    assert "不要发送" in result["assistant_message"]
