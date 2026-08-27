from pathlib import Path

from app.core.database import SessionLocal
from app.knowledge.service import ModelGateway, activate, build_index, fingerprint, import_bank, normalize, retrieve

FIXTURE = Path(__file__).parent / "fixtures/knowledge/sample_bank.json"


def test_normalization_and_fingerprint_are_stable():
    assert normalize(" 驾驶机动车，通过！ ") == normalize("驾驶机动车通过")
    assert fingerprint("Ａ．减速") == fingerprint("A减速")


def test_import_index_activate_and_retrieve():
    with SessionLocal() as db:
        version = import_bank(db, FIXTURE, name="测试题库", supplier="internal-test", version_label="test-v1")
        assert version.status == "READY" and version.item_count == 2 and version.error_count == 0
        assert import_bank(db, FIXTURE, name="测试题库", supplier="internal-test", version_label="test-v1").id == version.id
        version = build_index(db, version.id, ModelGateway())
        assert version.collection_name and version.status == "READY"
        activate(db, version.id)
        result = retrieve(db, "驾驶机动车通过没有交通信号的交叉路口怎样行驶？", "pilot-school", "全国", "C1")
        assert result and result["answer"].startswith("B.") and result["standard_answer"] == "B" and result["knowledge_version"] == "test-v1"


def test_invalid_bank_is_blocked(tmp_path):
    path = tmp_path / "invalid.json"; path.write_text('[{"external_id":"bad","stem":"缺答案"}]')
    with SessionLocal() as db:
        version = import_bank(db, path, name="坏题库", supplier="test", version_label="bad-v1")
        assert version.status == "BLOCKED" and version.error_count > 0
