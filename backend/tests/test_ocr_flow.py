import io
from datetime import datetime, timedelta, timezone

from PIL import Image
from app.core.database import SessionLocal
from app.models import UploadedAsset
from app.ocr_services import LocalStorage, delete_expired_assets, parse_ocr_text


def image_bytes(fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (640, 480), "white").save(buffer, format=fmt)
    return buffer.getvalue()


def upload(client, auth, content: bytes | None = None, mime: str = "image/png"):
    return client.post(
        "/api/v1/assets/images",
        headers=auth,
        files={"image": ("question.png", content or image_bytes(), mime)},
    )


def test_ocr_image_to_question_is_recoverable_and_idempotent(client, auth):
    uploaded = upload(client, auth)
    assert uploaded.status_code == 200
    asset_id = uploaded.json()["asset_id"]

    headers = {**auth, "Idempotency-Key": "ocr-create-1"}
    created = client.post("/api/v1/ocr-tasks", headers=headers, json={"asset_id": asset_id})
    assert created.status_code == 200
    task_id = created.json()["id"]

    duplicate = client.post("/api/v1/ocr-tasks", headers=headers, json={"asset_id": asset_id})
    assert duplicate.json()["id"] == task_id

    task = client.get(f"/api/v1/ocr-tasks/{task_id}", headers=auth).json()
    assert task["status"] == "WAITING_USER"
    assert any(field["field_type"] == "stem" for field in task["fields"])

    values = [{"field_id": field["id"], "value": field["value"]} for field in task["fields"]]
    saved = client.patch(
        f"/api/v1/ocr-tasks/{task_id}/fields",
        headers=auth,
        json={"version": task["version"], "fields": values},
    )
    assert saved.status_code == 200

    confirm_headers = {**auth, "Idempotency-Key": "ocr-confirm-1"}
    confirmed = client.post(f"/api/v1/ocr-tasks/{task_id}/confirm", headers=confirm_headers, json={})
    assert confirmed.status_code == 200
    question_id = confirmed.json()["question_id"]
    assert client.post(f"/api/v1/ocr-tasks/{task_id}/confirm", headers=confirm_headers, json={}).json()["question_id"] == question_id

    question = client.get(f"/api/v1/questions/{question_id}", headers=auth)
    assert question.status_code == 200
    assert "没有交通信号的交叉路口" in question.json()["text"]


def test_image_content_is_private_and_invalid_files_are_rejected(client, auth):
    uploaded = upload(client, auth)
    asset_id = uploaded.json()["asset_id"]
    assert client.get(f"/api/v1/assets/{asset_id}/content").status_code == 401
    content = client.get(f"/api/v1/assets/{asset_id}/content", headers=auth)
    assert content.status_code == 200
    assert content.headers["cache-control"] == "private, no-store"

    invalid = upload(client, auth, b"<svg></svg>", "image/png")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "IMAGE_DECODE_FAILED"


def test_ocr_version_conflict_is_not_silently_overwritten(client, auth):
    asset_id = upload(client, auth).json()["asset_id"]
    created = client.post(
        "/api/v1/ocr-tasks",
        headers={**auth, "Idempotency-Key": "ocr-version-task"},
        json={"asset_id": asset_id},
    ).json()
    task = client.get(f"/api/v1/ocr-tasks/{created['id']}", headers=auth).json()
    first = task["fields"][0]
    response = client.patch(
        f"/api/v1/ocr-tasks/{created['id']}/fields",
        headers=auth,
        json={"version": task["version"] + 1, "fields": [{"field_id": first["id"], "value": first["value"]}]},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VERSION_CONFLICT"


def test_plain_ocr_text_is_deterministically_split_and_requires_confirmation():
    parsed = parse_ocr_text("一道题目？\nA. 第一个选项\nB、第二个选项")
    assert parsed.stem.value == "一道题目？"
    assert [item.label for item in parsed.options] == ["A", "B"]
    assert all(item.confidence == 0 for item in parsed.options)


def test_expired_asset_is_physically_deleted(client, auth):
    asset_id = upload(client, auth).json()["asset_id"]
    with SessionLocal() as db:
        asset = db.get(UploadedAsset, asset_id)
        storage_key = asset.storage_key
        asset.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert delete_expired_assets() == 1
    try:
        LocalStorage().read(storage_key)
        assert False, "expired file should be deleted"
    except FileNotFoundError:
        pass
    assert client.get(f"/api/v1/assets/{asset_id}/content", headers=auth).status_code == 404
