import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api import current_student, error
from app.core.config import get_settings
from app.core.database import get_db
from app.models import Answer, Conversation, OCRTask, Question, ReviewTicket, Staff, Student, TicketEvent, TicketMessage, UploadedAsset
from app.schemas import InvitationVerify, TicketAcknowledge, TicketClaim, TicketReply
from app.services import digest

router = APIRouter(prefix="/api/v1")
LABELS = {"SUBMITTED": "提交给校长", "QUEUED": "校长在摸鱼", "PROCESSING": "校长处理中", "REPLIED": "校长已回复", "CLOSED": "校长说好了"}


def current_staff(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Staff:
    if not authorization or not authorization.startswith("Bearer "):
        raise error(401, "STAFF_UNAUTHORIZED", "请先进入校长工作台。")
    staff = db.scalar(select(Staff).where(Staff.session_token_hash == digest(authorization[7:])))
    if not staff:
        raise error(401, "INVALID_STAFF_SESSION", "工作台登录状态已失效。")
    return staff


def owned_staff_ticket(db: Session, ticket_id: str, staff: Staff) -> ReviewTicket:
    ticket = db.scalar(select(ReviewTicket).where(ReviewTicket.id == ticket_id, ReviewTicket.school_id == staff.school_id))
    if not ticket:
        raise error(404, "NOT_FOUND", "未找到该工单。")
    return ticket


def ticket_payload(db: Session, ticket: ReviewTicket, include_detail: bool = True) -> dict:
    question = db.get(Question, ticket.question_id)
    answer = db.scalar(select(Answer).where(Answer.question_id == question.id)) if question else None
    messages = db.scalars(select(TicketMessage).where(TicketMessage.ticket_id == ticket.id).order_by(TicketMessage.created_at)).all()
    events = db.scalars(select(TicketEvent).where(TicketEvent.ticket_id == ticket.id).order_by(TicketEvent.created_at)).all()
    ocr = db.scalar(select(OCRTask).where(OCRTask.linked_question_id == ticket.question_id))
    result = {"id": ticket.id, "status": ticket.status, "label": LABELS.get(ticket.status, "状态待确认"), "version": ticket.version, "risk_codes": ticket.risk_codes, "assignee_id": ticket.assignee_id, "created_at": ticket.created_at, "updated_at": ticket.updated_at, "sla": "问题已进入队列，测试期目标为工作时间内2小时处理。"}
    if include_detail:
        result.update({
            "question": {"id": question.id, "text": question.raw_text, "status": question.status} if question else None,
            "answer": {"direct_answer": answer.direct_answer, "short_reason": answer.short_reason, "detail": answer.detail, "common_mistake": answer.common_mistake, "evidence": [{"title": e.title, "version": e.version, "excerpt": e.excerpt, "source_type": e.source_type, "source_id": e.source_id} for e in answer.evidence]} if answer else None,
            "ocr": {"task_id": ocr.id, "preview_url": f"/api/staff-backend/staff/assets/{ocr.asset_id}/content"} if ocr else None,
            "messages": [{"id": m.id, "author_type": m.author_type, "content": m.content, "created_at": m.created_at} for m in messages],
            "events": [{"id": e.id, "event_type": e.event_type, "from_status": e.from_status, "to_status": e.to_status, "created_at": e.created_at} for e in events],
        })
    return result


@router.post("/staff/auth/invitations/verify")
def staff_verify(payload: InvitationVerify, db: Session = Depends(get_db)):
    if not secrets.compare_digest(payload.code.strip(), get_settings().staff_invitation_code):
        raise error(400, "INVALID_STAFF_INVITATION", "工作台邀请码无效。")
    token = secrets.token_urlsafe(32)
    staff = db.scalar(select(Staff).where(Staff.school_id == "pilot-school", Staff.role == "coach"))
    if staff:
        staff.session_token_hash = digest(token)
    else:
        staff = Staff(display_name="值班校长", school_id="pilot-school", role="coach", session_token_hash=digest(token))
        db.add(staff)
    db.commit()
    return {"access_token": token, "staff_id": staff.id, "display_name": staff.display_name, "role": staff.role}


@router.get("/staff/me")
def staff_me(staff: Staff = Depends(current_staff)):
    return {"id": staff.id, "display_name": staff.display_name, "role": staff.role, "school_id": staff.school_id}


@router.get("/staff/review-tickets")
def list_tickets(status: str | None = Query(default=None), page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=50), staff: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    query = select(ReviewTicket).where(ReviewTicket.school_id == staff.school_id)
    count_query = select(func.count()).select_from(ReviewTicket).where(ReviewTicket.school_id == staff.school_id)
    if status:
        query, count_query = query.where(ReviewTicket.status == status), count_query.where(ReviewTicket.status == status)
    total = db.scalar(count_query) or 0
    items = db.scalars(query.order_by(ReviewTicket.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [ticket_payload(db, item, False) for item in items], "page": page, "page_size": page_size, "total": total}


@router.get("/staff/review-tickets/{ticket_id}")
def staff_ticket(ticket_id: str, staff: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    return ticket_payload(db, owned_staff_ticket(db, ticket_id, staff))


@router.post("/staff/review-tickets/{ticket_id}/claim")
def claim_ticket(ticket_id: str, payload: TicketClaim, idempotency_key: str = Header(alias="Idempotency-Key"), staff: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    ticket = owned_staff_ticket(db, ticket_id, staff)
    previous = db.scalar(select(TicketEvent).where(TicketEvent.request_id == idempotency_key))
    if previous:
        return ticket_payload(db, db.get(ReviewTicket, ticket_id))
    if ticket.status not in ("SUBMITTED", "QUEUED"):
        if ticket.assignee_id == staff.id:
            return ticket_payload(db, ticket)
        raise error(409, "TICKET_ALREADY_CLAIMED", "该工单已被认领。")
    result = db.execute(update(ReviewTicket).where(ReviewTicket.id == ticket.id, ReviewTicket.school_id == staff.school_id, ReviewTicket.version == payload.version, ReviewTicket.assignee_id.is_(None)).values(assignee_id=staff.id, status="PROCESSING", version=ReviewTicket.version + 1, updated_at=datetime.now(timezone.utc)))
    if result.rowcount != 1:
        db.rollback()
        raise error(409, "VERSION_CONFLICT", "工单已被其他校长更新，请刷新。")
    db.add(TicketEvent(ticket_id=ticket.id, actor_type="staff", actor_id=staff.id, event_type="CLAIMED", from_status=ticket.status, to_status="PROCESSING", request_id=idempotency_key))
    db.commit()
    return ticket_payload(db, db.get(ReviewTicket, ticket.id))


@router.post("/staff/review-tickets/{ticket_id}/reply")
def reply_ticket(ticket_id: str, payload: TicketReply, idempotency_key: str = Header(alias="Idempotency-Key"), staff: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    ticket = owned_staff_ticket(db, ticket_id, staff)
    previous = db.scalar(select(TicketEvent).where(TicketEvent.request_id == idempotency_key))
    if previous:
        return ticket_payload(db, ticket)
    if ticket.assignee_id != staff.id or ticket.status != "PROCESSING":
        raise error(409, "TICKET_NOT_REPLYABLE", "请先认领该工单后再回复。")
    if ticket.version != payload.version:
        raise error(409, "VERSION_CONFLICT", "工单已更新，请刷新。")
    content = payload.content.strip()
    db.add(TicketMessage(ticket_id=ticket.id, author_type="staff", author_id=staff.id, content=content))
    db.add(TicketEvent(ticket_id=ticket.id, actor_type="staff", actor_id=staff.id, event_type="REPLIED", from_status=ticket.status, to_status="REPLIED", request_id=idempotency_key))
    ticket.status, ticket.version, ticket.replied_at = "REPLIED", ticket.version + 1, datetime.now(timezone.utc)
    db.commit()
    return ticket_payload(db, ticket)


@router.get("/staff/assets/{asset_id}/content")
def staff_asset(asset_id: str, staff: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    from app.api import LocalStorage
    from fastapi.responses import Response
    asset = db.scalar(select(UploadedAsset).where(UploadedAsset.id == asset_id, UploadedAsset.school_id == staff.school_id, UploadedAsset.status == "READY"))
    if not asset:
        raise error(404, "NOT_FOUND", "图片不存在或无权查看。")
    try:
        content = LocalStorage().read(asset.storage_key)
    except FileNotFoundError as exc:
        raise error(404, "ASSET_NOT_FOUND", "图片已删除。") from exc
    return Response(content, media_type=asset.detected_mime, headers={"Cache-Control": "private, no-store"})


@router.post("/review-tickets/{ticket_id}/acknowledge")
def acknowledge(ticket_id: str, payload: TicketAcknowledge, idempotency_key: str = Header(alias="Idempotency-Key"), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    ticket = db.scalar(select(ReviewTicket).where(ReviewTicket.id == ticket_id, ReviewTicket.student_id == student.id))
    if not ticket:
        raise error(404, "NOT_FOUND", "未找到该工单。")
    previous = db.scalar(select(TicketEvent).where(TicketEvent.request_id == idempotency_key))
    if previous:
        return ticket_payload(db, ticket)
    if ticket.status != "REPLIED":
        raise error(409, "TICKET_NOT_ACKNOWLEDGEABLE", "校长回复后才能确认解决。")
    if ticket.version != payload.version:
        raise error(409, "VERSION_CONFLICT", "工单已更新，请刷新。")
    db.add(TicketEvent(ticket_id=ticket.id, actor_type="student", actor_id=student.id, event_type="ACKNOWLEDGED", from_status="REPLIED", to_status="CLOSED", request_id=idempotency_key))
    ticket.status, ticket.version, ticket.closed_at = "CLOSED", ticket.version + 1, datetime.now(timezone.utc)
    db.commit()
    return ticket_payload(db, ticket)
