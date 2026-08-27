from pathlib import Path

from app.core.database import SessionLocal
from app.knowledge.service import ModelGateway, activate, build_index, fingerprint, import_bank, normalize, retrieve, run_evaluation

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
        run = run_evaluation(db, version.id, gateway=ModelGateway())
        assert run.status == "PASSED" and run.p0_errors == 0 and run.answer_accuracy == 1
        activate(db, version.id)
        result = retrieve(db, "驾驶机动车通过没有交通信号的交叉路口怎样行驶？", "pilot-school", "全国", "C1")
        assert result and result["answer"].startswith("B.") and result["standard_answer"] == "B" and result["knowledge_version"] == "test-v1"


def test_activation_requires_a_passed_evaluation():
    with SessionLocal() as db:
        version = build_index(db, import_bank(db, FIXTURE, name="测试题库", supplier="internal-test", version_label="gate-v1").id, ModelGateway())
        try:
            activate(db, version.id)
            assert False, "activation should have been blocked"
        except ValueError:
            pass


def test_can_rollback_to_a_previously_evaluated_version(tmp_path):
    with SessionLocal() as db:
        first = build_index(db, import_bank(db, FIXTURE, name="题库一", supplier="test", version_label="rollback-v1").id, ModelGateway())
        run_evaluation(db, first.id, gateway=ModelGateway()); activate(db, first.id)
        second_path = tmp_path / "second.json"; second_path.write_text(FIXTURE.read_text().replace("让行规则", "优先通行规则"))
        second = build_index(db, import_bank(db, second_path, name="题库二", supplier="test", version_label="rollback-v2").id, ModelGateway())
        run_evaluation(db, second.id, gateway=ModelGateway()); activate(db, second.id)
        restored = activate(db, first.id, event_type="ROLLBACK")
        assert restored.status == "ACTIVE" and second.status == "RETIRED"


def test_invalid_bank_is_blocked(tmp_path):
    path = tmp_path / "invalid.json"; path.write_text('[{"external_id":"bad","stem":"缺答案"}]')
    with SessionLocal() as db:
        version = import_bank(db, path, name="坏题库", supplier="test", version_label="bad-v1")
        assert version.status == "BLOCKED" and version.error_count > 0
