import os
import tempfile
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DASHSCOPE_API_KEY"] = ""
os.environ["OCR_STORAGE_DIR"] = tempfile.mkdtemp(prefix="driving-school-ocr-tests-")

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.services import seed


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


@pytest.fixture
def auth(client):
    response = client.post("/api/v1/auth/invitations/verify", json={"code": "INVITE_CODE_REMOVED"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
