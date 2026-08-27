def create_ticket(client, auth):
    conversation = client.post("/api/v1/conversations", headers=auth, json={}).json()
    question = client.post("/api/v1/questions", headers=auth, json={"conversation_id": conversation["id"], "text": "这道题为什么这样选？"}).json()
    return client.post("/api/v1/review-tickets", headers=auth, json={"question_id": question["id"], "risk_codes": ["STUDENT_REQUEST"]}).json()


def staff_auth(client):
    response = client.post("/api/v1/staff/auth/invitations/verify", json={"code": "INVITE_CODE_REMOVED"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_staff_ticket_claim_reply_and_student_acknowledge(client, auth):
    created = create_ticket(client, auth)
    staff = staff_auth(client)
    listing = client.get("/api/v1/staff/review-tickets", headers=staff).json()
    assert listing["total"] == 1
    assert listing["items"][0]["status"] == "QUEUED"

    claimed = client.post(f"/api/v1/staff/review-tickets/{created['id']}/claim", headers={**staff, "Idempotency-Key": "claim-1"}, json={"version": 1})
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "PROCESSING"

    conflict = client.post(f"/api/v1/staff/review-tickets/{created['id']}/claim", headers={**staff, "Idempotency-Key": "claim-2"}, json={"version": 1})
    assert conflict.status_code == 200  # same assignee retries safely

    replied = client.post(f"/api/v1/staff/review-tickets/{created['id']}/reply", headers={**staff, "Idempotency-Key": "reply-1"}, json={"version": 2, "content": "这道题应先判断标志含义，再排除错误选项。"})
    assert replied.status_code == 200
    assert replied.json()["status"] == "REPLIED"
    assert replied.json()["messages"][0]["author_type"] == "staff"

    acknowledged = client.post(f"/api/v1/review-tickets/{created['id']}/acknowledge", headers={**auth, "Idempotency-Key": "ack-1"}, json={"version": 3})
    assert acknowledged.status_code == 200
    assert acknowledged.json()["status"] == "CLOSED"
    assert [event["event_type"] for event in acknowledged.json()["events"]] == ["CLAIMED", "REPLIED", "ACKNOWLEDGED"]


def test_staff_authorization_and_transition_guards(client, auth):
    created = create_ticket(client, auth)
    assert client.get("/api/v1/staff/review-tickets").status_code == 401
    staff = staff_auth(client)
    premature = client.post(f"/api/v1/staff/review-tickets/{created['id']}/reply", headers={**staff, "Idempotency-Key": "reply-early"}, json={"version": 1, "content": "不能直接回复"})
    assert premature.status_code == 409
    premature_ack = client.post(f"/api/v1/review-tickets/{created['id']}/acknowledge", headers={**auth, "Idempotency-Key": "ack-early"}, json={"version": 1})
    assert premature_ack.status_code == 409
