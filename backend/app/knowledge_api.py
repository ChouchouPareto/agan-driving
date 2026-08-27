from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.knowledge.service import activate, build_index, run_evaluation
from app.models import EvaluationCaseResult, EvaluationRun, KnowledgeValidationIssue, KnowledgeVersion
from app.staff_api import current_staff, error

router = APIRouter(prefix="/api/v1/staff")


def payload(item: KnowledgeVersion) -> dict:
    return {"id": item.id, "version_label": item.version_label, "status": item.status, "region": item.region, "license_type": item.license_type, "item_count": item.item_count, "error_count": item.error_count, "embedding_model": item.embedding_model, "collection_name": item.collection_name, "activated_at": item.activated_at, "created_at": item.created_at}


@router.get("/knowledge/versions")
def versions(staff=Depends(current_staff), db: Session = Depends(get_db)):
    items = db.scalars(select(KnowledgeVersion).where(KnowledgeVersion.school_id == staff.school_id).order_by(KnowledgeVersion.created_at.desc())).all()
    return {"items": [payload(item) for item in items]}


@router.get("/knowledge/versions/{version_id}")
def version_detail(version_id: str, staff=Depends(current_staff), db: Session = Depends(get_db)):
    item = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == version_id, KnowledgeVersion.school_id == staff.school_id))
    if not item: raise error(404, "NOT_FOUND", "未找到该题库版本。")
    return payload(item)


@router.get("/knowledge/versions/{version_id}/issues")
def issues(version_id: str, staff=Depends(current_staff), db: Session = Depends(get_db)):
    item = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == version_id, KnowledgeVersion.school_id == staff.school_id))
    if not item: raise error(404, "NOT_FOUND", "未找到该题库版本。")
    rows = db.scalars(select(KnowledgeValidationIssue).where(KnowledgeValidationIssue.knowledge_version_id == item.id)).all()
    return {"items": [{"id": row.id, "external_id": row.external_id, "row_number": row.row_number, "issue_type": row.issue_type, "severity": row.severity, "safe_message": row.safe_message, "status": row.status} for row in rows]}


@router.post("/knowledge/versions/{version_id}/rebuild-index")
def rebuild(version_id: str, _: str = Header(alias="Idempotency-Key"), staff=Depends(current_staff), db: Session = Depends(get_db)):
    item = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == version_id, KnowledgeVersion.school_id == staff.school_id))
    if not item: raise error(404, "NOT_FOUND", "未找到该题库版本。")
    try: return payload(build_index(db, item.id))
    except ValueError as exc: raise error(409, "VERSION_NOT_INDEXABLE", "当前版本不能构建索引。") from exc


@router.post("/knowledge/versions/{version_id}/run-evaluation")
def evaluate_version(version_id: str, _: str = Header(alias="Idempotency-Key"), staff=Depends(current_staff), db: Session = Depends(get_db)):
    item = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == version_id, KnowledgeVersion.school_id == staff.school_id))
    if not item: raise error(404, "NOT_FOUND", "未找到该题库版本。")
    try: return evaluation_payload(run_evaluation(db, item.id))
    except ValueError as exc: raise error(409, "VERSION_NOT_EVALUABLE", "请先完成题库校验和索引构建。") from exc


@router.post("/knowledge/versions/{version_id}/activate")
def activate_version(version_id: str, idempotency_key: str = Header(alias="Idempotency-Key"), staff=Depends(current_staff), db: Session = Depends(get_db)):
    item = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == version_id, KnowledgeVersion.school_id == staff.school_id))
    if not item: raise error(404, "NOT_FOUND", "未找到该题库版本。")
    try: return payload(activate(db, item.id, actor_id=staff.id, request_id=idempotency_key))
    except ValueError as exc: raise error(409, "QUALITY_GATE_FAILED", "版本未通过机器校验、索引和离线评测门禁。") from exc


@router.post("/knowledge/versions/{version_id}/rollback")
def rollback_version(version_id: str, idempotency_key: str = Header(alias="Idempotency-Key"), staff=Depends(current_staff), db: Session = Depends(get_db)):
    item = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == version_id, KnowledgeVersion.school_id == staff.school_id))
    if not item: raise error(404, "NOT_FOUND", "未找到该题库版本。")
    try: return payload(activate(db, item.id, actor_id=staff.id, request_id=idempotency_key, event_type="ROLLBACK"))
    except ValueError as exc: raise error(409, "ROLLBACK_GATE_FAILED", "只能回退到已通过评测的历史版本。") from exc


def evaluation_payload(item: EvaluationRun) -> dict:
    return {"id": item.id, "dataset_id": item.dataset_id, "knowledge_version_id": item.knowledge_version_id, "status": item.status, "embedding_model": item.embedding_model, "rerank_model": item.rerank_model, "total_cases": item.total_cases, "passed_cases": item.passed_cases, "p0_errors": item.p0_errors, "top1_rate": item.top1_rate, "answer_accuracy": item.answer_accuracy, "error_message_safe": item.error_message_safe, "created_at": item.created_at, "completed_at": item.completed_at}


@router.get("/evaluation-runs")
def evaluation_runs(staff=Depends(current_staff), db: Session = Depends(get_db)):
    rows = db.scalars(select(EvaluationRun).join(KnowledgeVersion).where(KnowledgeVersion.school_id == staff.school_id).order_by(EvaluationRun.created_at.desc())).all()
    return {"items": [evaluation_payload(row) for row in rows]}


@router.get("/evaluation-runs/{run_id}")
def evaluation_run_detail(run_id: str, staff=Depends(current_staff), db: Session = Depends(get_db)):
    run = db.scalar(select(EvaluationRun).join(KnowledgeVersion).where(EvaluationRun.id == run_id, KnowledgeVersion.school_id == staff.school_id))
    if not run: raise error(404, "NOT_FOUND", "未找到该评测记录。")
    result = evaluation_payload(run)
    rows = db.scalars(select(EvaluationCaseResult).where(EvaluationCaseResult.run_id == run.id)).all()
    result["results"] = [{"id": row.id, "case_id": row.case_id, "matched_question_id": row.matched_question_id, "actual_answer": row.actual_answer, "passed": row.passed, "error_code": row.error_code, "match_type": row.match_type} for row in rows]
    return result
