import json
import random

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import AgentTurn, Answer, Conversation, Feedback, KnowledgeSource, KnowledgeVersion, OCRAuditLog, OCRField, OCRTask, Question, ReviewTicket, StandardQuestion, Student, StudentQuestionProgress, UploadedAsset
from app.ocr_services import process_ocr_task, store_asset
from app.storage import get_object_storage
from app.schemas import AgentMessageCreate, AgentMessageResult, AuthResult, ConversationCreate, FavoritePatch, FeedbackCreate, InvitationVerify, LearningContextPatch, MockExamSubmit, OCRConfirm, OCRFieldsPatch, OCRTaskCreate, PracticeAnswer, QuestionCreate, QuestionCreated, TicketCreate
from app.services import AIServiceError, authenticate_invitation, create_answer, digest
from app.pe import classify_intent, resolve_follow_up
from app.pe.prompts import PROMPT_VERSION
from app.skills import generate_conversation_reply, resolve_skill
from app.knowledge.advisory_service import retrieve_advisory_documents
from app.knowledge.mnemonics import mnemonic_for

router = APIRouter(prefix="/api/v1")
LICENSE_TYPES = {"A1", "A2", "A3", "B1", "B2", "C1", "C2", "C3", "C4", "C5", "C6", "D", "E", "F", "M", "N", "P"}
SUBJECTS = {"subject-1", "subject-2", "subject-3", "subject-4"}


def _knowledge_license_type(license_type: str, subject: str) -> str | None:
    if license_type in {"C1", "C2"} and subject in {"subject-1", "subject-4", "科目一", "科目四"}:
        return "C1"
    return None


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


@router.patch("/me/learning-context")
def update_learning_context(payload: LearningContextPatch, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    if payload.license_type not in LICENSE_TYPES or payload.subject not in SUBJECTS:
        raise error(422, "INVALID_LEARNING_CONTEXT", "请选择有效的准驾车型和学习阶段。")
    student.license_type = payload.license_type
    student.subject = payload.subject
    db.commit()
    return {"license_type": student.license_type, "subject": student.subject, "content_available": _knowledge_license_type(student.license_type, student.subject) is not None}


@router.get("/knowledge/status")
def student_knowledge_status(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    knowledge_license = _knowledge_license_type(student.license_type, student.subject)
    version = db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.school_id == student.school_id, KnowledgeVersion.status == "ACTIVE", KnowledgeVersion.region == student.region, KnowledgeVersion.license_type == knowledge_license).order_by(KnowledgeVersion.activated_at.desc())) if knowledge_license else None
    if not version:
        return {"connected": False, "version": None, "item_count": 0, "scope": f"{student.region} · {student.license_type}", "is_preview": True, "notice": "当前没有已激活的知识库。"}
    source = db.get(KnowledgeSource, version.source_id)
    is_preview = not source or source.license_scope != "commercial"
    shared_notice = "C2 理论阶段当前与 C1 共用道路安全法规与通行规则题库。" if student.license_type == "C2" else ""
    base_notice = "当前为研究联调题库，正式上线前将替换为供应商授权版本。" if is_preview else "当前使用已授权正式题库。"
    return {"connected": True, "version": version.version_label, "item_count": version.item_count, "scope": f"{student.region} · {student.license_type}", "is_preview": is_preview, "notice": f"{shared_notice}{base_notice}"}


def _practice_summary(db: Session, student: Student, version: KnowledgeVersion) -> dict:
    rows = db.scalars(select(StudentQuestionProgress).where(StudentQuestionProgress.student_id == student.id, StudentQuestionProgress.knowledge_version_id == version.id)).all()
    attempted = sum(1 for row in rows if row.attempts); correct = sum(row.correct_attempts for row in rows); attempts = sum(row.attempts for row in rows)
    return {"attempted": attempted, "correct_attempts": correct, "total_attempts": attempts, "wrong_count": sum(1 for row in rows if row.last_correct is False), "favorite_count": sum(1 for row in rows if row.is_favorite), "accuracy": correct / attempts if attempts else 0}


def _active_practice_version(db: Session, student: Student, license_type: str, subject: str) -> KnowledgeVersion | None:
    knowledge_license = _knowledge_license_type(license_type, subject)
    return db.scalar(select(KnowledgeVersion).where(KnowledgeVersion.school_id == student.school_id, KnowledgeVersion.status == "ACTIVE", KnowledgeVersion.region == student.region, KnowledgeVersion.license_type == knowledge_license).order_by(KnowledgeVersion.activated_at.desc())) if knowledge_license else None


def _record_practice_answer(db: Session, student: Student, version: KnowledgeVersion, question: StandardQuestion, selected: str) -> bool:
    progress = db.scalar(select(StudentQuestionProgress).where(StudentQuestionProgress.student_id == student.id, StudentQuestionProgress.standard_question_id == question.id))
    if not progress:
        progress = StudentQuestionProgress(student_id=student.id, standard_question_id=question.id, knowledge_version_id=version.id, attempts=0, correct_attempts=0, wrong_attempts=0, is_favorite=False); db.add(progress)
    correct = selected == question.standard_answer
    progress.attempts += 1; progress.correct_attempts += int(correct); progress.wrong_attempts += int(not correct); progress.last_answer = selected; progress.last_correct = correct; progress.last_answered_at = datetime.now(timezone.utc)
    return correct


@router.get("/practice/questions")
def practice_questions(mode: str = Query(default="all", pattern="^(all|wrong|favorites)$"), license_type: str = Query(default="C1"), subject: str = Query(default="subject-1"), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    version = _active_practice_version(db, student, license_type, subject)
    if not version:
        return {"items": [], "knowledge_version": None, "summary": {"attempted": 0, "correct_attempts": 0, "total_attempts": 0, "wrong_count": 0, "favorite_count": 0, "accuracy": 0}}
    progress_rows = db.scalars(select(StudentQuestionProgress).where(StudentQuestionProgress.student_id == student.id, StudentQuestionProgress.knowledge_version_id == version.id)).all(); progress = {row.standard_question_id: row for row in progress_rows}
    items = db.scalars(select(StandardQuestion).where(StandardQuestion.knowledge_version_id == version.id, StandardQuestion.status == "VALID").order_by(StandardQuestion.external_id)).all()
    if mode == "wrong": items = [item for item in items if progress.get(item.id) and progress[item.id].last_correct is False]
    if mode == "favorites": items = [item for item in items if progress.get(item.id) and progress[item.id].is_favorite]
    return {"knowledge_version": version.version_label, "summary": _practice_summary(db, student, version), "items": [{"id": item.id, "external_id": item.external_id, "stem": item.stem, "options": item.options, "mnemonic": mnemonic_for(item.stem, item.explanation), "attempted": bool(progress.get(item.id) and progress[item.id].attempts), "last_correct": progress[item.id].last_correct if progress.get(item.id) else None, "is_favorite": progress[item.id].is_favorite if progress.get(item.id) else False} for item in items]}


@router.post("/practice/questions/{question_id}/answer")
def answer_practice_question(question_id: str, payload: PracticeAnswer, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    question = db.get(StandardQuestion, question_id); version = db.get(KnowledgeVersion, question.knowledge_version_id) if question else None
    if not question or not version or version.status != "ACTIVE" or version.school_id != student.school_id: raise error(404, "NOT_FOUND", "未找到该练习题。")
    selected = payload.answer.strip(); valid_answers = {str(option.get("label", "")) for option in question.options}
    if selected not in valid_answers: raise error(422, "INVALID_ANSWER", "请选择有效答案。")
    correct = _record_practice_answer(db, student, version, question, selected)
    db.commit()
    progress = db.scalar(select(StudentQuestionProgress).where(StudentQuestionProgress.student_id == student.id, StudentQuestionProgress.standard_question_id == question.id))
    return {"correct": correct, "standard_answer": question.standard_answer, "explanation": question.explanation, "mnemonic": mnemonic_for(question.stem, question.explanation), "is_favorite": bool(progress and progress.is_favorite), "summary": _practice_summary(db, student, version)}


@router.patch("/practice/questions/{question_id}/favorite")
def favorite_practice_question(question_id: str, payload: FavoritePatch, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    question = db.get(StandardQuestion, question_id); version = db.get(KnowledgeVersion, question.knowledge_version_id) if question else None
    if not question or not version or version.status != "ACTIVE" or version.school_id != student.school_id: raise error(404, "NOT_FOUND", "未找到该练习题。")
    progress = db.scalar(select(StudentQuestionProgress).where(StudentQuestionProgress.student_id == student.id, StudentQuestionProgress.standard_question_id == question.id))
    if not progress: progress = StudentQuestionProgress(student_id=student.id, standard_question_id=question.id, knowledge_version_id=version.id, attempts=0, correct_attempts=0, wrong_attempts=0, is_favorite=False); db.add(progress)
    progress.is_favorite = payload.is_favorite; db.commit()
    return {"question_id": question.id, "is_favorite": progress.is_favorite, "summary": _practice_summary(db, student, version)}


@router.get("/practice/insights")
def practice_insights(license_type: str = Query(default="C1"), subject: str = Query(default="subject-1"), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    version = _active_practice_version(db, student, license_type, subject)
    if not version:
        return {"summary": None, "weak_points": [], "readiness": "NOT_STARTED", "recommendation": "题库开放后，我会根据你的答题记录安排练习。"}
    summary = _practice_summary(db, student, version)
    rows = db.scalars(select(StudentQuestionProgress).where(StudentQuestionProgress.student_id == student.id, StudentQuestionProgress.knowledge_version_id == version.id, StudentQuestionProgress.attempts > 0)).all()
    questions = {item.id: item for item in db.scalars(select(StandardQuestion).where(StandardQuestion.knowledge_version_id == version.id)).all()}
    stats: dict[str, dict[str, int]] = {}
    for row in rows:
        question = questions.get(row.standard_question_id)
        for point in (question.knowledge_points if question else []) or ["综合规则"]:
            current = stats.setdefault(point, {"attempts": 0, "wrong": 0})
            current["attempts"] += row.attempts; current["wrong"] += row.wrong_attempts
    weak_points = sorted(({"name": name, **values, "error_rate": values["wrong"] / values["attempts"]} for name, values in stats.items() if values["wrong"]), key=lambda item: (item["error_rate"], item["wrong"]), reverse=True)[:3]
    readiness = "READY" if summary["attempted"] >= 100 and summary["accuracy"] >= .9 else "BUILDING" if summary["attempted"] else "NOT_STARTED"
    recommendation = f"先复习“{weak_points[0]['name']}”，再做 10 道相关题。" if weak_points else ("正确率已达到 90%，建议进行一次模拟考试。" if summary["accuracy"] >= .9 else "先完成一组顺序练习，我会开始识别你的薄弱点。")
    return {"summary": summary, "weak_points": weak_points, "readiness": readiness, "recommendation": recommendation}


@router.get("/practice/mock-exam")
def create_mock_exam(size: int = Query(default=100, ge=1, le=100), license_type: str = Query(default="C1"), subject: str = Query(default="subject-1"), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    version = _active_practice_version(db, student, license_type, subject)
    if not version:
        return {"knowledge_version": None, "duration_minutes": 45, "pass_score": 90, "items": []}
    available = db.scalars(select(StandardQuestion).where(StandardQuestion.knowledge_version_id == version.id, StandardQuestion.status == "VALID")).all()
    items = random.sample(available, min(size, len(available)))
    return {"knowledge_version": version.version_label, "duration_minutes": 45, "pass_score": 90, "items": [{"id": item.id, "external_id": item.external_id, "stem": item.stem, "options": item.options} for item in items]}


@router.post("/practice/mock-exam")
def submit_mock_exam(payload: MockExamSubmit, license_type: str = Query(default="C1"), subject: str = Query(default="subject-1"), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    version = _active_practice_version(db, student, license_type, subject)
    if not version: raise error(404, "NOT_FOUND", "当前没有可用的模拟考试题库。")
    question_ids = [item.question_id for item in payload.answers]
    if len(question_ids) != len(set(question_ids)): raise error(422, "DUPLICATE_ANSWER", "同一道题不能重复提交。")
    questions = {item.id: item for item in db.scalars(select(StandardQuestion).where(StandardQuestion.id.in_(question_ids), StandardQuestion.knowledge_version_id == version.id)).all()}
    if len(questions) != len(question_ids): raise error(422, "INVALID_EXAM", "试卷中包含无效题目。")
    details = []
    for item in payload.answers:
        question = questions[item.question_id]
        valid_answers = {str(option.get("label", "")) for option in question.options}
        if item.answer not in valid_answers: raise error(422, "INVALID_ANSWER", "试卷中包含无效答案。")
        correct = _record_practice_answer(db, student, version, question, item.answer)
        details.append({"question_id": question.id, "selected_answer": item.answer, "standard_answer": question.standard_answer, "correct": correct, "explanation": question.explanation})
    db.commit()
    correct_count = sum(int(item["correct"]) for item in details); total = len(details); score = round(correct_count / total * 100)
    return {"score": score, "passed": score >= 90, "correct_count": correct_count, "total": total, "details": details, "summary": _practice_summary(db, student, version)}


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
        content = get_object_storage().read(asset.storage_key)
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
    safety_intent = classify_intent(text, False).intent
    if safety_intent == "SENSITIVE_CONTENT":
        raise error(422, "SENSITIVE_CONTENT", "图片中可能包含敏感信息，请只保留题目区域后重新上传。")
    if safety_intent == "PROMPT_INJECTION":
        raise error(422, "UNSAFE_INSTRUCTION", "图片内容包含异常指令，未进入问答模型。请只保留真实题目。")
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
    questions = db.scalars(select(Question).where(Question.conversation_id == conversation.id).order_by(Question.created_at)).all()
    return {"id": conversation.id, "status": conversation.status, "questions": [_question_payload(db, q, student) for q in questions]}


def _answer_payload(question: Question) -> dict | None:
    if not question.answer:
        return None
    return {
        "id": question.answer.id, "direct_answer": question.answer.direct_answer,
        "short_reason": question.answer.short_reason, "detail": question.answer.detail,
        "common_mistake": question.answer.common_mistake,
        "evidence": [{"source_type": item.source_type, "source_id": item.source_id, "title": item.title, "version": item.version, "excerpt": item.excerpt} for item in question.answer.evidence],
        "risk_codes": ["NEEDS_REVIEW"] if question.status == "NEEDS_REVIEW" else [], "route": question.route,
    }


def _question_payload(db: Session, question: Question, student: Student) -> dict:
    review_ticket = db.scalar(select(ReviewTicket).where(ReviewTicket.question_id == question.id, ReviewTicket.student_id == student.id))
    labels = {"SUBMITTED": "提交给校长", "QUEUED": "校长在摸鱼", "PROCESSING": "校长处理中", "REPLIED": "校长已回复", "CLOSED": "处理已完成"}
    ticket = None if not review_ticket else {"id": review_ticket.id, "status": review_ticket.status, "label": labels.get(review_ticket.status, "状态待确认"), "sla": "问题已进入队列，工作时间内预计2小时处理。"}
    answer = _answer_payload(question)
    if answer is not None and review_ticket and question.status == "NEEDS_REVIEW":
        answer["risk_codes"] = review_ticket.risk_codes
    return {"id": question.id, "conversation_id": question.conversation_id, "text": question.raw_text, "resolved_text": question.resolved_text, "intent": question.intent, "prompt_version": question.prompt_version, "status": question.status, "answer": answer, "ticket": ticket}


@router.post("/agent/messages", response_model=AgentMessageResult)
def agent_message(payload: AgentMessageCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    if payload.license_type not in LICENSE_TYPES or payload.subject not in SUBJECTS:
        raise error(422, "INVALID_LEARNING_CONTEXT", "请选择有效的准驾车型和学习阶段。")
    student.license_type = payload.license_type
    student.subject = payload.subject
    conversation = None
    if payload.conversation_id:
        conversation = db.scalar(select(Conversation).where(Conversation.id == payload.conversation_id, Conversation.student_id == student.id))
        if not conversation:
            raise error(404, "NOT_FOUND", "未找到该会话。")
    if conversation is None:
        conversation = Conversation(student_id=student.id)
        db.add(conversation); db.flush()
    previous = db.scalar(select(Question).where(Question.conversation_id == conversation.id).order_by(Question.created_at.desc()))
    previous_turn = db.scalar(select(AgentTurn.id).where(AgentTurn.conversation_id == conversation.id).limit(1))
    context_question = db.scalar(select(Question).where(Question.conversation_id == conversation.id, Question.intent != "FOLLOW_UP").order_by(Question.created_at.desc()))
    classified = classify_intent(payload.text, previous is not None or previous_turn is not None)
    evidence = retrieve_advisory_documents(db, payload.text, classified.intent, payload.license_type, student.region) if classified.intent in {"INDUSTRY_KNOWLEDGE", "LEARNING_PROCESS", "POLICY_REGULATION", "LICENSE_TIMELINE"} else None
    if classified.intent == "MNEMONIC_HELP" and context_question:
        explanation = context_question.answer.detail if context_question.answer else ""
        mnemonic = mnemonic_for(context_question.resolved_text or context_question.raw_text, explanation)
        if mnemonic:
            evidence = [{"title": "刚才这道题的记忆口诀", "summary": mnemonic, "source_type": "reviewed_mnemonic"}]
    skill = resolve_skill(classified.intent, payload.text, evidence)
    if skill.action == "NAVIGATE":
        db.commit()
        labels = {"START_PRACTICE": "想刷题的话，点下面就能开始。", "WRONG_QUESTIONS": "可以，点下面打开错题本。", "FAVORITES": "可以，点下面看收藏的题。", "MOCK_EXAM": "准备好了就点下面，再开始模拟考试。"}
        return AgentMessageResult(conversation_id=conversation.id, intent=classified.intent, skill_id=skill.spec.id, action="SUGGEST_NAVIGATION", destination=skill.destination, assistant_message=labels.get(classified.intent, "点下面再继续。"), prompt_version=PROMPT_VERSION)
    if skill.action == "RESPOND":
        message = skill.assistant_message or generate_conversation_reply(db, conversation, student, classified.intent, skill.spec.id, payload.text.strip(), evidence)
        db.commit()
        return AgentMessageResult(conversation_id=conversation.id, intent=classified.intent, skill_id=skill.spec.id, action="RESPOND", assistant_message=message, prompt_version=PROMPT_VERSION)
    resolved = resolve_follow_up(payload.text, context_question.raw_text if context_question else None) if classified.intent == "FOLLOW_UP" else payload.text.strip()
    question = Question(conversation_id=conversation.id, raw_text=payload.text.strip(), resolved_text=resolved, intent=classified.intent, prompt_version=PROMPT_VERSION)
    db.add(question); db.commit()
    return AgentMessageResult(conversation_id=conversation.id, intent=classified.intent, skill_id=skill.spec.id, action="ANSWER", question_id=question.id, prompt_version=PROMPT_VERSION)


@router.post("/questions", response_model=QuestionCreated)
def submit_question(payload: QuestionCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    safety_intent = classify_intent(payload.text, False).intent
    if safety_intent == "SENSITIVE_CONTENT":
        raise error(422, "SENSITIVE_CONTENT", "请移除身份证、手机号、银行卡、验证码等敏感信息后再提问。")
    if safety_intent == "PROMPT_INJECTION":
        raise error(422, "UNSAFE_INSTRUCTION", "内容包含异常指令，未进入问答模型。")
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
    return _question_payload(db, question, student)


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
    existing = db.scalar(select(Feedback).where(Feedback.answer_id == answer.id, Feedback.student_id == student.id, Feedback.type == payload.type))
    if existing:
        return {"id": existing.id, "type": existing.type}
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
