from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.knowledge.service import activate, build_index
from app.models import KnowledgeValidationIssue, KnowledgeVersion
from app.staff_api import current_staff, error

router = APIRouter(prefix="/api/v1/staff/knowledge")


def payload(item: KnowledgeVersion) -> dict:
    return {"id": item.id, "version_label": item.version_label, "status": item.status, "region": item.region, "license_type": item.license_type, "item_count": item.item_count, "error_count": item.error_count, "embedding_model": item.embedding_model, "collection_name": item.collection_name, "activated_at": item.activated_at, "created_at": item.created_at}


@router.get("/versions")
def versions(staff=Depends(current_staff), db: Session = Depends(get_db)):
    items = db.scalars(select(KnowledgeVersion).where(KnowledgeVersion.school_id == staff.school_id).order_by(KnowledgeVersion.created_at.desc())).all()
    return {"items": [payload(item) for item in items]}


@router.get("/versions/{version_id}")
def version_detail(version_id: str, staff=Depends(current_staff), db: Session = Depends(get_db)):
    item = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == version_id, KnowledgeVersion.school_id == staff.school_id))
    if not item: raise error(404, "NOT_FOUND", "未找到该题库版本。")
    return payload(item)


@router.get("/versions/{version_id}/issues")
def issues(version_id: str, staff=Depends(current_staff), db: Session = Depends(get_db)):
    item = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == version_id, KnowledgeVersion.school_id == staff.school_id))
    if not item: raise error(404, "NOT_FOUND", "未找到该题库版本。")
    rows = db.scalars(select(KnowledgeValidationIssue).where(KnowledgeValidationIssue.knowledge_version_id == item.id)).all()
    return {"items": [{"id": row.id, "external_id": row.external_id, "row_number": row.row_number, "issue_type": row.issue_type, "severity": row.severity, "safe_message": row.safe_message, "status": row.status} for row in rows]}


@router.post("/versions/{version_id}/rebuild-index")
def rebuild(version_id: str, _: str = Header(alias="Idempotency-Key"), staff=Depends(current_staff), db: Session = Depends(get_db)):
    item = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == version_id, KnowledgeVersion.school_id == staff.school_id))
    if not item: raise error(404, "NOT_FOUND", "未找到该题库版本。")
    try: return payload(build_index(db, item.id))
    except ValueError as exc: raise error(409, "VERSION_NOT_INDEXABLE", "当前版本不能构建索引。") from exc


@router.post("/versions/{version_id}/activate")
def activate_version(version_id: str, _: str = Header(alias="Idempotency-Key"), staff=Depends(current_staff), db: Session = Depends(get_db)):
    item = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.id == version_id, KnowledgeVersion.school_id == staff.school_id))
    if not item: raise error(404, "NOT_FOUND", "未找到该题库版本。")
    try: return payload(activate(db, item.id))
    except ValueError as exc: raise error(409, "QUALITY_GATE_FAILED", "版本未通过机器校验和索引门禁。") from exc
