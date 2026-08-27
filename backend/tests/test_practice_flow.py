from pathlib import Path

from app.core.database import SessionLocal
from app.knowledge.service import ModelGateway, activate, build_index, import_bank, run_evaluation

FIXTURE = Path(__file__).parent / "fixtures/knowledge/sample_bank.json"


def student_headers(client):
    response = client.post("/api/v1/auth/invitations/verify", json={"code": "INVITE_CODE_REMOVED"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def seed_active_bank():
    with SessionLocal() as db:
        version = build_index(db, import_bank(db, FIXTURE, name="练习题库", supplier="test", version_label="practice-v1").id, ModelGateway())
        run_evaluation(db, version.id, gateway=ModelGateway()); activate(db, version.id)


def test_practice_progress_wrong_book_and_favorite(client):
    seed_active_bank(); headers = student_headers(client)
    listing = client.get("/api/v1/practice/questions", headers=headers)
    assert listing.status_code == 200 and len(listing.json()["items"]) == 2
    question = listing.json()["items"][0]
    assert "standard_answer" not in question and "explanation" not in question

    answered = client.post(f"/api/v1/practice/questions/{question['id']}/answer", headers=headers, json={"answer": "A"})
    assert answered.status_code == 200 and answered.json()["correct"] is False
    assert answered.json()["summary"]["wrong_count"] == 1

    wrong = client.get("/api/v1/practice/questions?mode=wrong", headers=headers).json()
    assert [item["id"] for item in wrong["items"]] == [question["id"]]

    favorite = client.patch(f"/api/v1/practice/questions/{question['id']}/favorite", headers=headers, json={"is_favorite": True})
    assert favorite.status_code == 200 and favorite.json()["summary"]["favorite_count"] == 1
    favorites = client.get("/api/v1/practice/questions?mode=favorites", headers=headers).json()
    assert [item["id"] for item in favorites["items"]] == [question["id"]]


def test_practice_rejects_invalid_answer(client):
    seed_active_bank(); headers = student_headers(client)
    question = client.get("/api/v1/practice/questions", headers=headers).json()["items"][0]
    response = client.post(f"/api/v1/practice/questions/{question['id']}/answer", headers=headers, json={"answer": "Z"})
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_ANSWER"


def test_learning_context_supports_catalog_and_c1_c2_theory_sharing(client):
    seed_active_bank(); headers = student_headers(client)
    context = client.patch("/api/v1/me/learning-context", headers=headers, json={"license_type": "C2", "subject": "subject-1"})
    assert context.status_code == 200 and context.json()["content_available"] is True
    c2_theory = client.get("/api/v1/practice/questions?license_type=C2&subject=subject-1", headers=headers)
    assert c2_theory.status_code == 200 and len(c2_theory.json()["items"]) == 2
    unavailable = client.get("/api/v1/practice/questions?license_type=B2&subject=subject-2", headers=headers)
    assert unavailable.status_code == 200 and unavailable.json()["items"] == []
    rejected = client.patch("/api/v1/me/learning-context", headers=headers, json={"license_type": "X9", "subject": "subject-1"})
    assert rejected.status_code == 422 and rejected.json()["error"]["code"] == "INVALID_LEARNING_CONTEXT"
