import hashlib
import json
import math
import re
import time
import unicodedata
from pathlib import Path

import chromadb
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    EvaluationCase, EvaluationCaseResult, EvaluationDataset, EvaluationRun,
    KnowledgeActivationEvent, KnowledgeChunk, KnowledgeSource,
    KnowledgeValidationIssue, KnowledgeVersion, RetrievalTrace, StandardQuestion,
)

NORMALIZER_VERSION = "1"


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).lower().strip()
    return "".join(ch for ch in value if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize(text).encode()).hexdigest()


def options_text(options: list[dict]) -> str:
    return "\n".join(f"{item['label']}. {item['text']}" for item in options)


def _validate(row: dict, row_number: int) -> list[tuple[str, str, str]]:
    issues = []
    for field in ("external_id", "stem", "question_type", "options", "standard_answer", "explanation"):
        if not row.get(field): issues.append(("MISSING_FIELD", "P0", f"第 {row_number} 行缺少字段：{field}"))
    options = row.get("options") or []
    labels = {str(item.get("label", "")).upper() for item in options if isinstance(item, dict)}
    if row.get("standard_answer") and str(row["standard_answer"]).upper() not in labels and str(row["standard_answer"]) not in ("正确", "错误"):
        issues.append(("INVALID_ANSWER", "P0", f"第 {row_number} 行标准答案未指向合法选项"))
    return issues


def import_bank(db: Session, path: Path, *, name: str, supplier: str, version_label: str, school_id: str = "pilot-school", region: str = "全国", license_type: str = "C1") -> KnowledgeVersion:
    content = path.read_bytes()
    source_hash = hashlib.sha256(content).hexdigest()
    existing_source = db.scalar(select(KnowledgeSource).where(KnowledgeSource.source_hash == source_hash))
    if existing_source:
        existing = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.source_id == existing_source.id, KnowledgeVersion.version_label == version_label))
        if existing: return existing
    source = existing_source or KnowledgeSource(school_id=school_id, name=name, supplier=supplier, source_hash=source_hash, license_scope="test-only")
    db.add(source); db.flush()
    version = KnowledgeVersion(source_id=source.id, school_id=school_id, version_label=version_label, region=region, license_type=license_type, status="VALIDATING", normalizer_version=NORMALIZER_VERSION, embedding_model=get_settings().embedding_model_id, embedding_dimensions=get_settings().embedding_dimensions)
    db.add(version); db.flush()
    try:
        rows = json.loads(content)
        if not isinstance(rows, list): raise ValueError("题库根节点必须是数组")
    except (json.JSONDecodeError, ValueError) as exc:
        db.add(KnowledgeValidationIssue(knowledge_version_id=version.id, issue_type="ENCODING_ERROR", severity="P0", safe_message=str(exc)))
        version.status, version.error_count = "BLOCKED", 1; db.commit(); return version
    seen_external, answers_by_fingerprint = set(), {}
    for index, row in enumerate(rows, 1):
        issues = _validate(row, index)
        external_id = str(row.get("external_id", ""))
        if external_id in seen_external: issues.append(("DUPLICATE", "P0", f"题号重复：{external_id}"))
        seen_external.add(external_id)
        stem_fp = fingerprint(str(row.get("stem", "")))
        previous_answer = answers_by_fingerprint.get(stem_fp)
        if previous_answer and previous_answer != row.get("standard_answer"): issues.append(("ANSWER_CONFLICT", "P0", f"相同题干存在不同答案：{external_id}"))
        answers_by_fingerprint[stem_fp] = row.get("standard_answer")
        for kind, severity, message in issues:
            db.add(KnowledgeValidationIssue(knowledge_version_id=version.id, external_id=external_id or None, row_number=index, issue_type=kind, severity=severity, safe_message=message))
        if issues: continue
        options = row["options"]
        question = StandardQuestion(knowledge_version_id=version.id, school_id=school_id, external_id=external_id, stem=row["stem"].strip(), normalized_stem=normalize(row["stem"]), stem_fingerprint=stem_fp, options=options, options_fingerprint=fingerprint(options_text(options)), standard_answer=str(row["standard_answer"]), explanation=row["explanation"].strip(), knowledge_points=row.get("knowledge_points", []), question_type=row["question_type"], region=row.get("region", region), license_type=row.get("license_type", license_type))
        db.add(question); db.flush()
        chunk_content = f"题干：{question.stem}\n选项：\n{options_text(options)}\n标准答案：{question.standard_answer}\n解析：{question.explanation}\n知识点：{'、'.join(question.knowledge_points)}"
        db.add(KnowledgeChunk(question_id=question.id, knowledge_version_id=version.id, content=chunk_content, content_hash=hashlib.sha256(chunk_content.encode()).hexdigest()))
        version.item_count += 1
    db.flush()
    version.error_count = len(db.scalars(select(KnowledgeValidationIssue).where(KnowledgeValidationIssue.knowledge_version_id == version.id)).all())
    version.status = "BLOCKED" if version.error_count else "READY"
    db.commit(); return version


class ModelGateway:
    def __init__(self): self.settings = get_settings()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.settings.dashscope_api_key:
            return [self._fake_embedding(text) for text in texts]
        response = httpx.post(f"{self.settings.dashscope_base_url.rstrip('/')}/embeddings", headers={"Authorization": f"Bearer {self.settings.dashscope_api_key}"}, json={"model": self.settings.embedding_model_id, "input": texts, "dimensions": self.settings.embedding_dimensions}, timeout=self.settings.rag_model_timeout_seconds)
        response.raise_for_status(); return [item["embedding"] for item in response.json()["data"]]

    def rerank(self, query: str, documents: list[str]) -> list[int]:
        if not self.settings.dashscope_api_key: return list(range(len(documents)))
        response = httpx.post("https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank", headers={"Authorization": f"Bearer {self.settings.dashscope_api_key}"}, json={"model": self.settings.rerank_model_id, "input": {"query": query, "documents": documents}, "parameters": {"return_documents": False, "top_n": min(len(documents), self.settings.rag_rerank_top_k)}}, timeout=self.settings.rag_model_timeout_seconds)
        response.raise_for_status(); payload = response.json(); results = payload.get("results") or payload.get("output", {}).get("results", [])
        return [item["index"] for item in results]

    def _fake_embedding(self, text: str) -> list[float]:
        dims = self.settings.embedding_dimensions; values = [0.0] * dims
        for token in re.findall(r"[\u4e00-\u9fff]|[a-z0-9]+", normalize(text)):
            values[int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % dims] += 1
        norm = math.sqrt(sum(value * value for value in values)) or 1
        return [value / norm for value in values]


def build_index(db: Session, version_id: str, gateway: ModelGateway | None = None) -> KnowledgeVersion:
    version = db.get(KnowledgeVersion, version_id)
    if not version or version.status not in ("READY", "INDEXING", "ACTIVE"): raise ValueError("knowledge version is not indexable")
    gateway = gateway or ModelGateway(); version.status = "INDEXING"; db.commit()
    chunks = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.knowledge_version_id == version.id)).all()
    collection_name = f"{get_settings().rag_collection_prefix}_{version.id.replace('-', '')[:12]}_{version.embedding_dimensions}"
    client = chromadb.PersistentClient(path=str(Path(get_settings().rag_storage_dir).resolve()))
    try: client.delete_collection(collection_name)
    except Exception: pass
    collection = client.create_collection(collection_name, metadata={"hnsw:space": "cosine"})
    embeddings = gateway.embed([item.content for item in chunks])
    questions = {q.id: q for q in db.scalars(select(StandardQuestion).where(StandardQuestion.knowledge_version_id == version.id)).all()}
    collection.add(ids=[item.id for item in chunks], embeddings=embeddings, documents=[item.content for item in chunks], metadatas=[{"school_id": version.school_id, "version_id": version.id, "region": questions[item.question_id].region, "license_type": questions[item.question_id].license_type, "status": questions[item.question_id].status, "question_id": item.question_id} for item in chunks])
    for item in chunks: item.embedding_status, item.vector_record_id = "READY", item.id
    version.collection_name, version.status = collection_name, "READY"; db.commit(); return version


def activate(db: Session, version_id: str, *, actor_id: str = "system", request_id: str | None = None, event_type: str = "ACTIVATE") -> KnowledgeVersion:
    if request_id:
        prior = db.scalar(select(KnowledgeActivationEvent).where(KnowledgeActivationEvent.request_id == request_id))
        if prior:
            if prior.to_version_id != version_id or prior.event_type != event_type: raise ValueError("idempotency key conflict")
            return db.get(KnowledgeVersion, prior.to_version_id)
    version = db.get(KnowledgeVersion, version_id)
    allowed = ("READY",) if event_type == "ACTIVATE" else ("RETIRED",)
    latest_run = db.scalar(select(EvaluationRun).where(EvaluationRun.knowledge_version_id == version_id).order_by(EvaluationRun.created_at.desc())) if version else None
    if not version or version.status not in allowed or version.error_count or not latest_run or latest_run.status != "PASSED": raise ValueError("version failed quality gate")
    current = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.school_id == version.school_id, KnowledgeVersion.status == "ACTIVE"))
    if current: current.status = "RETIRED"
    from datetime import datetime, timezone
    version.status, version.activated_at = "ACTIVE", datetime.now(timezone.utc)
    db.add(KnowledgeActivationEvent(school_id=version.school_id, actor_id=actor_id, event_type=event_type, from_version_id=current.id if current else None, to_version_id=version.id, request_id=request_id or f"{event_type.lower()}-{version.id}-{time.time_ns()}"))
    db.commit(); return version


def retrieve(db: Session, text: str, school_id: str, region: str, license_type: str, question_id: str | None = None, gateway: ModelGateway | None = None, knowledge_version_id: str | None = None) -> dict | None:
    started = time.monotonic(); gateway = gateway or ModelGateway()
    version = db.get(KnowledgeVersion, knowledge_version_id) if knowledge_version_id else db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.school_id == school_id, KnowledgeVersion.status == "ACTIVE", KnowledgeVersion.region == region, KnowledgeVersion.license_type == license_type).order_by(KnowledgeVersion.activated_at.desc()))
    if version and (version.school_id != school_id or version.region != region or version.license_type != license_type): version = None
    if not version: return None
    normalized = normalize(text); exact = db.scalar(select(StandardQuestion).where(StandardQuestion.knowledge_version_id == version.id, StandardQuestion.status == "VALID", StandardQuestion.stem_fingerprint == fingerprint(text)))
    candidates = [exact] if exact else []
    match_type = "standard_exact" if exact else "standard_hybrid"
    if not exact:
        all_questions = db.scalars(select(StandardQuestion).where(StandardQuestion.knowledge_version_id == version.id, StandardQuestion.status == "VALID")).all()
        keyword = sorted(all_questions, key=lambda item: sum(1 for ch in set(normalized) if ch in item.normalized_stem), reverse=True)[:get_settings().rag_keyword_top_k]
        candidates.extend(keyword)
        if version.collection_name:
            client = chromadb.PersistentClient(path=str(Path(get_settings().rag_storage_dir).resolve())); collection = client.get_collection(version.collection_name)
            result = collection.query(query_embeddings=gateway.embed([text]), n_results=min(get_settings().rag_vector_top_k, max(1, version.item_count)), where={"$and": [{"school_id": school_id}, {"region": region}, {"license_type": license_type}, {"status": "VALID"}]})
            for qid in result.get("metadatas", [[]])[0]:
                candidate = db.get(StandardQuestion, qid["question_id"])
                if candidate and candidate not in candidates: candidates.append(candidate)
        if candidates:
            order = gateway.rerank(text, [item.stem + "\n" + item.explanation for item in candidates[:30]])
            candidates = [candidates[index] for index in order if index < len(candidates)][:get_settings().rag_rerank_top_k]
    selected = candidates[0] if candidates else None
    error_code = None if selected else "NO_TRUSTED_EVIDENCE"
    db.add(RetrievalTrace(question_id=question_id, knowledge_version_id=version.id, query_hash=fingerprint(text), match_type=match_type if selected else "none", candidate_ids=[item.id for item in candidates], final_evidence_ids=[selected.id] if selected else [], error_code=error_code, latency_ms=int((time.monotonic() - started) * 1000))); db.commit()
    if not selected: return None
    option = next((item for item in selected.options if str(item.get("label", "")).upper() == selected.standard_answer.upper()), None)
    display_answer = f"{selected.standard_answer}. {option['text']}" if option else selected.standard_answer
    return {"answer": display_answer, "standard_answer": selected.standard_answer, "reason": selected.explanation[:160], "detail": selected.explanation, "mistake": "请注意题干中的否定词、范围和关键条件。", "source_id": selected.id, "external_id": selected.external_id, "title": "科目一标准题库", "excerpt": selected.explanation, "knowledge_version": version.version_label, "match_type": match_type, "region": selected.region, "license_type": selected.license_type}


def create_evaluation_dataset(db: Session, version_id: str) -> EvaluationDataset:
    version = db.get(KnowledgeVersion, version_id)
    if not version: raise ValueError("version not found")
    dataset = EvaluationDataset(school_id=version.school_id, name=f"{version.version_label} 全量标准题评测", version_label=version.version_label)
    db.add(dataset); db.flush()
    for question in db.scalars(select(StandardQuestion).where(StandardQuestion.knowledge_version_id == version.id, StandardQuestion.status == "VALID")).all():
        db.add(EvaluationCase(dataset_id=dataset.id, input_text=question.stem, expected_external_id=question.external_id, expected_answer=question.standard_answer, region=question.region, license_type=question.license_type, severity="P0"))
    db.commit(); return dataset


def run_evaluation(db: Session, version_id: str, dataset_id: str | None = None, gateway: ModelGateway | None = None) -> EvaluationRun:
    version = db.get(KnowledgeVersion, version_id)
    if not version or version.status not in ("READY", "ACTIVE", "RETIRED") or not version.collection_name: raise ValueError("version is not evaluable")
    dataset = db.get(EvaluationDataset, dataset_id) if dataset_id else create_evaluation_dataset(db, version_id)
    if not dataset or dataset.school_id != version.school_id: raise ValueError("dataset not found")
    gateway = gateway or ModelGateway(); cases = db.scalars(select(EvaluationCase).where(EvaluationCase.dataset_id == dataset.id)).all()
    run = EvaluationRun(dataset_id=dataset.id, knowledge_version_id=version.id, embedding_model=version.embedding_model, rerank_model=get_settings().rerank_model_id, total_cases=len(cases))
    db.add(run); db.flush()
    top1 = answers = passed = p0 = 0
    try:
        for case in cases:
            result = retrieve(db, case.input_text, version.school_id, case.region, case.license_type, gateway=gateway, knowledge_version_id=version.id)
            id_ok = bool(result and result["external_id"] == case.expected_external_id); answer_ok = bool(result and result["standard_answer"] == case.expected_answer)
            top1 += int(id_ok); answers += int(answer_ok); case_passed = id_ok and answer_ok; passed += int(case_passed)
            if not case_passed and case.severity == "P0": p0 += 1
            db.add(EvaluationCaseResult(run_id=run.id, case_id=case.id, matched_question_id=result["source_id"] if result else None, actual_answer=result["standard_answer"] if result else None, passed=case_passed, error_code=None if case_passed else "EXPECTED_RESULT_MISMATCH", match_type=result["match_type"] if result else "none"))
        run.passed_cases, run.p0_errors = passed, p0
        run.top1_rate = top1 / len(cases) if cases else 0; run.answer_accuracy = answers / len(cases) if cases else 0
        run.status = "PASSED" if cases and p0 == 0 and run.answer_accuracy == 1 else "FAILED"
    except Exception:
        run.status, run.error_message_safe = "FAILED", "评测执行失败，请检查模型和索引配置。"
    from datetime import datetime, timezone
    run.completed_at = datetime.now(timezone.utc); db.commit(); return run
