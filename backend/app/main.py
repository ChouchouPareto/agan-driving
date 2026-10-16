from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api import router
from app.staff_api import router as staff_router
from app.knowledge_api import router as knowledge_router
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.services import seed
from app.database_backup import backup_database, restore_database_if_needed
from app.rate_limit import limiter, request_identity

@asynccontextmanager
async def lifespan(_: FastAPI):
    restore_database_if_needed()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="阿甘学车 API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.include_router(staff_router)
app.include_router(knowledge_router)


@app.middleware("http")
async def protect_high_cost_routes(request: Request, call_next):
    if get_settings().app_env.lower() == "test":
        return await call_next(request)
    limits = {
        ("POST", "/api/v1/auth/invitations/verify"): (10, 600),
        ("POST", "/api/v1/staff/auth/invitations/verify"): (10, 600),
        ("POST", "/api/v1/agent/messages"): (30, 60),
        ("POST", "/api/v1/assets/images"): (10, 60),
    }
    rule = limits.get((request.method, request.url.path))
    if rule:
        allowed, retry_after = limiter.allow(f"{request.url.path}:{request_identity(request)}", *rule)
        if not allowed:
            return JSONResponse(status_code=429, headers={"Retry-After": str(retry_after)}, content={"error": {"code": "RATE_LIMITED", "message": "操作太频繁，请稍后再试。"}})
    return await call_next(request)


@app.middleware("http")
async def persist_sqlite_mutations(request: Request, call_next):
    response = await call_next(request)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and response.status_code < 500:
        backup_database()
    return response


@app.get("/api/v1/health")
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    settings = get_settings()
    return {
        "status": "ok",
        "service": "agan-driving-api",
        "environment": settings.app_env,
        "model_connected": not settings.mock_ai,
        "persistent_storage": "tos" if settings.tos_enabled else "local",
    }


@app.get("/api/v1/health/readiness")
def readiness():
    settings = get_settings()
    with SessionLocal() as db:
        active_knowledge = db.scalar(text("SELECT COUNT(*) FROM knowledge_versions WHERE status = 'ACTIVE'")) or 0
    issues = [*settings.production_issues]
    if active_knowledge == 0:
        issues.append("ACTIVE_KNOWLEDGE_MISSING")
    payload = {"status": "ready" if not issues else "not_ready", "issues": issues, "active_knowledge_versions": active_knowledge}
    return JSONResponse(status_code=200 if not issues else 503, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "输入内容不符合要求。", "details": exc.errors()}})


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(Exception)
async def unhandled_error(_: Request, __: Exception):
    return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "服务暂时不可用，请稍后重试。"}})
