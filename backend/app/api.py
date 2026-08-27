import json

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Answer, Conversation, Feedback, KnowledgeVersion, OCRAuditLog, OCRField, OCRTask, Question, ReviewTicket, StandardQuestion, Student, UploadedAsset
from app.ocr_services import LocalStorage, process_ocr_task, store_asset
from app.schemas import AuthResult, ConversationCreate, FeedbackCreate, InvitationVerify, OCRConfirm, OCRFieldsPatch, OCRTaskCreate, QuestionCreate, QuestionCreated, TicketCreate
from app.services import AIServiceError, authenticate_invitation, create_answer, digest

router = APIRouter(prefix="/api/v1")


def error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def current_student(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Student:
    if not authorization or not authorization.startswith("Bearer "):
        raise error(401, "UNAUTHORIZED", "请先使用邀请码进入。")
    student = db.scalar(select(Student).where(Student.session_token_hash == digest(authorization[7:])))
    if not student:
        raise error(401, "INVALID_SESSION", "登录状态已失效，请重新使用邀请码进入。")
    return student


def _owned_task(db: Session, task_id: str, student: Student) -> OCRTask:
    task = db.scalar(select(OCRTask).where(OCRTask.id == task_id, OCRTask.student_id == student.id))
    if not task:
        raise error(404, "NOT_FOUND", "未找到该识别任务。")
    return task


def _task_payload(db: Session, task: OCRTask) -> dict:
    fields = db.scalars(select(OCRField).where(OCRField.task_id == task.id).order_by(OCRField.sequence)).all()
    return {
        "id": task.id,
        "status": task.status,
        "request_id": task.request_id,
        "version": task.version,
        "question_type": task.question_type,
        "warnings": task.warnings,
        "needs_confirmation": any(item.needs_confirmation and not item.confirmed_at for item in fields),
        "fields": [{
            "id": item.id,
            "field_type": item.field_type,
            "label": item.label,
            "sequence": item.sequence,
            "value": item.corrected_value if item.corrected_value is not None else item.original_value,
            "confidence": item.confidence,
            "needs_confirmation": item.needs_confirmation,
            "version": item.version,
        } for item in fields],
        "safe_error": {"code": task.error_code, "message": task.error_message_safe} if task.error_code else None,
        "preview_url": f"/api/backend/assets/{task.asset_id}/content",
        "linked_question_id": task.linked_question_id,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


@router.post("/auth/invitations/verify", response_model=AuthResult)
def verify(payload: InvitationVerify, db: Session = Depends(get_db)):
    result = authenticate_invitation(db, payload.code)
    if not result:
        raise error(400, "INVALID_INVITATION", "邀请码无效或已失效。")
    student, token = result
    return AuthResult(access_token=token, student_id=student.id, anonymous_id=student.anonymous_id)


@router.get("/me")
def me(student: Student = Depends(current_student)):
    return {"id": student.id, "anonymous_id": student.anonymous_id, "subject": student.subject, "license_type": student.license_type, "region": student.region}


@router.get("/practice/questions")
def practice_questions(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    version = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.school_id == student.school_id, KnowledgeVersion.status == "ACTIVE", KnowledgeVersion.region == student.region, KnowledgeVersion.license_type == student.license_type).order_by(KnowledgeVersion.activated_at.desc()))
    if not version:
        return {"items": [], "knowledge_version": None}
    items = db.scalars(select(StandardQuestion).where(StandardQuestion.knowledge_version_id == version.id, StandardQuestion.status == "VALID").order_by(StandardQuestion.external_id).limit(20)).all()
    return {"knowledge_version": version.version_label, "items": [{"id": item.id, "external_id": item.external_id, "stem": item.stem, "options": item.options, "standard_answer": item.standard_answer, "explanation": item.explanation} for item in items]}


@router.post("/conversations")
def create_conversation(_: ConversationCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    conversation = Conversation(student_id=student.id)
    db.add(conversation)
    db.commit()
    return {"id": conversation.id, "status": conversation.status}


@router.post("/assets/images")
async def upload_image(image: UploadFile = File(...), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    content = await image.read(get_settings().ocr_max_image_bytes + 1)
    try:
        asset = store_asset(db, student.id, student.school_id, image.filename or "question", image.content_type or "", content)
    except ValueError as exc:
        code = str(exc)
        messages = {
            "IMAGE_TOO_LARGE": "图片超过限制或尺寸异常。",
            "IMAGE_DECODE_FAILED": "图片无法读取，请重新选择。",
            "UNSUPPORTED_IMAGE_TYPE": "仅支持 JPEG、PNG 或 WebP 图片。",
        }
        raise error(422, code, messages.get(code, "图片不符合要求。")) from exc
    return {
        "asset_id": asset.id,
        "status": asset.status,
        "mime": asset.detected_mime,
        "size_bytes": asset.size_bytes,
        "expires_at": asset.expires_at,
        "request_id": asset.id,
    }


@router.get("/assets/{asset_id}/content")
def get_asset_content(asset_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    asset = db.scalar(select(UploadedAsset).where(UploadedAsset.id == asset_id, UploadedAsset.student_id == student.id))
    expires_at = asset.expires_at if asset else None
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not asset or asset.status != "READY" or (expires_at and expires_at <= datetime.now(timezone.utc)):
        raise error(404, "ASSET_EXPIRED", "图片已过期或不存在。")
    try:
        content = LocalStorage().read(asset.storage_key)
    except FileNotFoundError as exc:
        raise error(404, "ASSET_NOT_FOUND", "图片已删除。") from exc
    return Response(content, media_type=asset.detected_mime, headers={"Cache-Control": "private, no-store", "Content-Disposition": "inline"})


@router.post("/ocr-tasks")
def create_ocr_task(payload: OCRTaskCreate, background: BackgroundTasks, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    if not idempotency_key or len(idempotency_key) > 128:
        raise error(422, "INVALID_IDEMPOTENCY_KEY", "创建识别任务需要有效的请求标识。")
    existing = db.scalar(select(OCRTask).where(OCRTask.idempotency_key == idempotency_key))
    if existing:
        if existing.student_id == student.id and existing.asset_id == payload.asset_id:
            return _task_payload(db, existing)
        raise error(409, "IDEMPOTENCY_CONFLICT", "该请求标识已用于其他任务。")
    asset = db.scalar(select(UploadedAsset).where(UploadedAsset.id == payload.asset_id, UploadedAsset.student_id == student.id, UploadedAsset.status == "READY"))
    if not asset:
        raise error(404, "ASSET_NOT_FOUND", "未找到可用图片。")
    task = OCRTask(asset_id=asset.id, student_id=student.id, idempotency_key=idempotency_key)
    db.add(task)
    db.commit()
    background.add_task(process_ocr_task, task.id)
    return _task_payload(db, task)


@router.get("/ocr-tasks/{task_id}")
def get_ocr_task(task_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return _task_payload(db, _owned_task(db, task_id, student))


@router.patch("/ocr-tasks/{task_id}/fields")
def patch_ocr_fields(task_id: str, payload: OCRFieldsPatch, x_request_id: str | None = Header(default=None), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    task = _owned_task(db, task_id, student)
    if task.status != "WAITING_USER":
        raise error(409, "OCR_NOT_EDITABLE", "当前识别任务不能修改。")
    if task.version != payload.version:
        raise error(409, "VERSION_CONFLICT", "识别内容已更新，请刷新后重试。")
    owned = {item.id: item for item in db.scalars(select(OCRField).where(OCRField.task_id == task.id)).all()}
    for change in payload.fields:
        item = owned.get(change.field_id)
        if not item:
            raise error(422, "INVALID_OCR_FIELD", "包含无效的识别字段。")
        before = item.corrected_value if item.corrected_value is not None else item.original_value
        item.corrected_value = change.value.strip()
        item.confirmed_at = datetime.now(timezone.utc)
        item.version += 1
        db.add(OCRAuditLog(task_id=task.id, field_id=item.id, actor_id=student.id, action="CORRECT_OR_CONFIRM", before_value=before, after_value=item.corrected_value, request_id=x_request_id or task.request_id))
    task.version += 1
    db.commit()
    return _task_payload(db, task)


@router.post("/ocr-tasks/{task_id}/confirm")
def confirm_ocr_task(task_id: str, payload: OCRConfirm, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    task = _owned_task(db, task_id, student)
    if task.linked_question_id:
        return {"ocr_task_id": task.id, "question_id": task.linked_question_id, "status": "QUESTION_CREATED"}
    if task.status != "WAITING_USER":
        raise error(409, "OCR_NOT_CONFIRMABLE", "识别尚未完成或当前不能确认。")
    fields = db.scalars(select(OCRField).where(OCRField.task_id == task.id).order_by(OCRField.sequence)).all()
    if not fields:
        raise error(409, "OCR_EMPTY", "没有可确认的识别内容。")
    for item in fields:
        if item.needs_confirmation and not item.confirmed_at:
            raise error(409, "OCR_CONFIRMATION_REQUIRED", "请先确认标记为不确定的内容。")
    stem = next((item for item in fields if item.field_type == "stem"), None)
    if not stem:
        raise error(409, "OCR_STEM_REQUIRED", "题干缺失，请修正后重试。")
    conversation = None
    if payload.conversation_id:
        conversation = db.scalar(select(Conversation).where(Conversation.id == payload.conversation_id, Conversation.student_id == student.id))
        if not conversation:
            raise error(404, "NOT_FOUND", "未找到该会话。")
    else:
        conversation = Conversation(student_id=student.id)
        db.add(conversation)
        db.flush()
    text = (stem.corrected_value or stem.original_value).strip()
    options = [f"{item.label or ''}. {(item.corrected_value or item.original_value).strip()}" for item in fields if item.field_type == "option"]
    if options:
        text = text + "\n" + "\n".join(options)
    request_id = idempotency_key or f"ocr-confirm-{task.id}"
    question = Question(conversation_id=conversation.id, raw_text=text, request_id=request_id)
    db.add(question)
    db.flush()
    task.linked_question_id = question.id
    task.status = "QUESTION_CREATED"
    task.version += 1
    db.add(OCRAuditLog(task_id=task.id, actor_id=student.id, action="CONFIRM_AND_CREATE_QUESTION", after_value=question.id, request_id=request_id))
    db.commit()
    return {"ocr_task_id": task.id, "question_id": question.id, "status": task.status}


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    conversation = db.scalar(select(Conversation).where(Conversation.id == conversation_id, Conversation.student_id == student.id))
    if not conversation:
        raise error(404, "NOT_FOUND", "未找到该会话。")
    questions = db.scalars(select(Question).where(Question.conversation_id == conversation.id)).all()
    return {"id": conversation.id, "status": conversation.status, "questions": [{"id": q.id, "text": q.raw_text, "status": q.status, "answer_id": q.answer.id if q.answer else None} for q in questions]}


@router.post("/questions", response_model=QuestionCreated)
def submit_question(payload: QuestionCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    conversation = db.scalar(select(Conversation).where(Conversation.id == payload.conversation_id, Conversation.student_id == student.id))
    if not conversation:
        raise error(404, "NOT_FOUND", "未找到该会话。")
    if idempotency_key:
        if len(idempotency_key) > 128:
            raise error(422, "INVALID_IDEMPOTENCY_KEY", "请求标识不符合要求。")
        existing = db.scalar(select(Question).where(Question.request_id == idempotency_key))
        if existing:
            if existing.conversation_id == conversation.id and existing.raw_text == payload.text.strip():
                return QuestionCreated(id=existing.id, request_id=existing.request_id, status=existing.status)
            raise error(409, "IDEMPOTENCY_CONFLICT", "该请求标识已用于其他内容。")
    question = Question(conversation_id=conversation.id, raw_text=payload.text.strip(), **({"request_id": idempotency_key} if idempotency_key else {}))
    db.add(question)
    db.commit()
    return QuestionCreated(id=question.id, request_id=question.request_id, status=question.status)


@router.get("/questions/{question_id}")
def get_question(question_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    question = db.scalar(select(Question).join(Conversation).where(Question.id == question_id, Conversation.student_id == student.id))
    if not question:
        raise error(404, "NOT_FOUND", "未找到该问题。")
    answer = None
    if question.answer:
        answer = {
            "id": question.answer.id, "direct_answer": question.answer.direct_answer,
            "short_reason": question.answer.short_reason, "detail": question.answer.detail,
            "common_mistake": question.answer.common_mistake,
            "evidence": [{"source_type": item.source_type, "source_id": item.source_id, "title": item.title, "version": item.version, "excerpt": item.excerpt} for item in question.answer.evidence],
            "risk_codes": [], "route": question.route,
        }
    review_ticket = db.scalar(select(ReviewTicket).where(ReviewTicket.question_id == question.id, ReviewTicket.student_id == student.id))
    ticket = None
    if review_ticket:
        labels = {"SUBMITTED": "提交给校长", "QUEUED": "校长在摸鱼", "PROCESSING": "校长处理中", "REPLIED": "校长已回复", "CLOSED": "校长说好了"}
        ticket = {"id": review_ticket.id, "status": review_ticket.status, "label": labels.get(review_ticket.status, "状态待确认"), "sla": "问题已进入队列，工作时间内预计2小时处理。"}
    if answer is not None and question.status == "NEEDS_REVIEW":
        answer["risk_codes"] = review_ticket.risk_codes if review_ticket else ["NEEDS_REVIEW"]
    return {"id": question.id, "text": question.raw_text, "status": question.status, "answer": answer, "ticket": ticket}


@router.get("/questions/{question_id}/stream")
def stream_question(question_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    question = db.scalar(select(Question).join(Conversation).where(Question.id == question_id, Conversation.student_id == student.id))
    if not question:
        raise error(404, "NOT_FOUND", "未找到该问题。")

    def events():
        yield "event: status\ndata: {\"status\":\"ROUTING\"}\n\n"
        try:
            payload = create_answer(db, question)
            data = json.dumps(payload.model_dump(), ensure_ascii=False)
            yield f"event: done\ndata: {data}\n\n"
        except AIServiceError:
            data = json.dumps({"error": {"code": "AI_SERVICE_ERROR", "message": "回答服务暂时不可用，请重试或提交给校长。"}}, ensure_ascii=False)
            yield f"event: error\ndata: {data}\n\n"
        except Exception:
            data = json.dumps({"error": {"code": "INTERNAL_ERROR", "message": "处理失败，请稍后重试。"}}, ensure_ascii=False)
            yield f"event: error\ndata: {data}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/answers/{answer_id}/feedback")
def feedback(answer_id: str, payload: FeedbackCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    answer = db.scalar(select(Answer).join(Question).join(Conversation).where(Answer.id == answer_id, Conversation.student_id == student.id))
    if not answer:
        raise error(404, "NOT_FOUND", "未找到该回答。")
    item = Feedback(answer_id=answer.id, student_id=student.id, type=payload.type)
    db.add(item)
    db.commit()
    return {"id": item.id, "type": item.type}


@router.post("/answers/{answer_id}/explain-again")
def explain_again(answer_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    answer = db.scalar(select(Answer).join(Question).join(Conversation).where(Answer.id == answer_id, Conversation.student_id == student.id))
    if not answer:
        raise error(404, "NOT_FOUND", "未找到该回答。")
    return create_answer(db, answer.question, explain_again=True)


@router.post("/review-tickets")
def create_ticket(payload: TicketCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    question = db.scalar(select(Question).join(Conversation).where(Question.id == payload.question_id, Conversation.student_id == student.id))
    if not question:
        raise error(404, "NOT_FOUND", "未找到该问题。")
    existing = db.scalar(select(ReviewTicket).where(ReviewTicket.question_id == question.id, ReviewTicket.student_id == student.id))
    if existing:
        return {"id": existing.id, "status": existing.status}
    ticket = ReviewTicket(question_id=question.id, student_id=student.id, school_id=student.school_id, risk_codes=payload.risk_codes)
    db.add(ticket)
    db.commit()
    return {"id": ticket.id, "status": ticket.status}


@router.get("/review-tickets/{ticket_id}")
def get_ticket(ticket_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    ticket = db.scalar(select(ReviewTicket).where(ReviewTicket.id == ticket_id, ReviewTicket.student_id == student.id))
    if not ticket:
        raise error(404, "NOT_FOUND", "未找到该工单。")
    from app.staff_api import ticket_payload
    return ticket_payload(db, ticket)


@router.get("/health")
def health():
    return {"status": "ok"}
