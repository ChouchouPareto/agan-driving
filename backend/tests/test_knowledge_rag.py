from pathlib import Path

from app.core.database import SessionLocal
from app.knowledge.service import ModelGateway, activate, build_index, fingerprint, import_bank, normalize, retrieve, run_evaluation
from app.models import KnowledgeChunk, RetrievalTrace
from sqlalchemy import select

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
        chunks = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.knowledge_version_id == version.id)).all()
        assert chunks and all(chunk.embedding_status == "READY" and chunk.embedding for chunk in chunks)
        run = run_evaluation(db, version.id, gateway=ModelGateway())
        assert run.status == "PASSED" and run.p0_errors == 0 and run.answer_accuracy == 1
        activate(db, version.id)
        result = retrieve(db, "驾驶机动车通过没有交通信号的交叉路口怎样行驶？", "pilot-school", "全国", "C1")
        assert result and result["answer"].startswith("B.") and result["standard_answer"] == "B" and result["knowledge_version"] == "test-v1"
        judgment = retrieve(db, "驾驶人在发生交通事故后因抢救伤员变动现场时要标明位置。", "pilot-school", "全国", "C1")
        if judgment:
            assert judgment["answer"] not in ("正确. 正确", "错误. 错误")
        assert retrieve(db, "道路上随便问一个完全不相关的问题", "pilot-school", "全国", "C1") is None


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


def test_same_stem_with_different_options_is_disambiguated_by_full_question(tmp_path):
    rows = [
        {"external_id":"a","stem":"同一道题？","question_type":"single_choice","options":[{"label":"A","text":"甲"},{"label":"B","text":"乙"}],"standard_answer":"A","explanation":"选择甲。","knowledge_points":[]},
        {"external_id":"b","stem":"同一道题？","question_type":"single_choice","options":[{"label":"A","text":"丙"},{"label":"B","text":"丁"}],"standard_answer":"B","explanation":"选择丁。","knowledge_points":[]},
    ]
    path = tmp_path / "variants.json"; path.write_text(__import__("json").dumps(rows, ensure_ascii=False))
    with SessionLocal() as db:
        version = import_bank(db, path, name="变体题库", supplier="test", version_label="variants-v1")
        assert version.status == "READY" and version.item_count == 2
        version = build_index(db, version.id, ModelGateway())
        run = run_evaluation(db, version.id, gateway=ModelGateway())
        assert run.status == "PASSED" and run.answer_accuracy == 1
        assert retrieve(db, "同一道题？", "pilot-school", "全国", "C1", knowledge_version_id=version.id) is None


class SemanticGateway(ModelGateway):
    def embed(self, texts):
        vectors = []
        for text in texts:
            if "交叉路口" in text or "路口没灯" in text:
                vectors.append([1.0, 0.0])
            else:
                vectors.append([0.0, 1.0])
        return vectors

    def rerank(self, query, documents):
        return list(range(len(documents)))


def test_vector_recall_finds_a_semantic_paraphrase():
    with SessionLocal() as db:
        gateway = SemanticGateway()
        version = build_index(db, import_bank(db, FIXTURE, name="语义题库", supplier="test", version_label="semantic-v1").id, gateway)
        result = retrieve(db, "路口没灯的时候该让谁先走", "pilot-school", "全国", "C1", gateway=gateway, knowledge_version_id=version.id)
        assert result and result["external_id"] == "TEST-001" and result["match_type"] == "standard_hybrid"


class FailingRerankGateway(SemanticGateway):
    def rerank(self, query, documents):
        raise RuntimeError("simulated provider outage")


def test_rerank_failure_degrades_to_hybrid_scores():
    with SessionLocal() as db:
        gateway = FailingRerankGateway()
        version = build_index(db, import_bank(db, FIXTURE, name="降级题库", supplier="test", version_label="degraded-v1").id, gateway)
        result = retrieve(db, "路口没灯的时候该让谁先走", "pilot-school", "全国", "C1", gateway=gateway, knowledge_version_id=version.id)
        assert result and result["external_id"] == "TEST-001"
        trace = db.scalar(select(RetrievalTrace).order_by(RetrievalTrace.created_at.desc()))
        assert trace and trace.error_code == "RERANK_DEGRADED"


def test_rebuilding_an_active_version_keeps_it_active():
    with SessionLocal() as db:
        gateway = SemanticGateway()
        version = build_index(db, import_bank(db, FIXTURE, name="在线题库", supplier="test", version_label="active-v1").id, gateway)
        run_evaluation(db, version.id, gateway=gateway)
        activate(db, version.id)
        rebuilt = build_index(db, version.id, gateway)
        assert rebuilt.status == "ACTIVE" and rebuilt.collection_name


def test_qwen3_rerank_uses_the_compatible_api(monkeypatch):
    gateway = ModelGateway()
    monkeypatch.setattr(gateway.settings, "dashscope_api_key", "test-key")
    monkeypatch.setattr(gateway.settings, "rag_max_retries", 0)
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"index": 1, "relevance_score": .9}, {"index": 0, "relevance_score": .1}]}

    def fake_post(url, **kwargs):
        captured["url"], captured["body"] = url, kwargs["json"]
        return Response()

    monkeypatch.setattr("app.knowledge.service.httpx.post", fake_post)
    assert gateway.rerank("问题", ["文档一", "文档二"]) == [1, 0]
    assert captured["url"].endswith("/compatible-api/v1/reranks")
    assert captured["body"]["query"] == "问题" and "input" not in captured["body"]
