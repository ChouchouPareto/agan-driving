import json

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Answer, Conversation, Feedback, Question, ReviewTicket, Student
from app.schemas import AuthResult, ConversationCreate, FeedbackCreate, InvitationVerify, QuestionCreate, QuestionCreated, TicketCreate
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


@router.post("/conversations")
def create_conversation(_: ConversationCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    conversation = Conversation(student_id=student.id)
    db.add(conversation)
    db.commit()
    return {"id": conversation.id, "status": conversation.status}


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
    ticket = ReviewTicket(question_id=question.id, student_id=student.id, risk_codes=payload.risk_codes)
    db.add(ticket)
    db.commit()
    return {"id": ticket.id, "status": ticket.status}


@router.get("/review-tickets/{ticket_id}")
def get_ticket(ticket_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    ticket = db.scalar(select(ReviewTicket).where(ReviewTicket.id == ticket_id, ReviewTicket.student_id == student.id))
    if not ticket:
        raise error(404, "NOT_FOUND", "未找到该工单。")
    labels = {"SUBMITTED": "提交给校长", "QUEUED": "校长在摸鱼", "PROCESSING": "校长处理中", "REPLIED": "校长已回复", "CLOSED": "校长说好了"}
    return {"id": ticket.id, "status": ticket.status, "label": labels[ticket.status], "sla": "问题已进入队列，工作时间内预计2小时处理。"}


@router.get("/health")
def health():
    return {"status": "ok"}
