import base64
import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import OCRField, OCRTask, UploadedAsset
from app.storage import LocalStorage, get_object_storage


ALLOWED_MIME = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


class OCRValue(BaseModel):
    value: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(default=0, ge=0, le=1)


class OCROption(OCRValue):
    label: str = Field(min_length=1, max_length=4)


class OCRDocument(BaseModel):
    question_type: str = "unknown"
    stem: OCRValue
    options: list[OCROption] = Field(default_factory=list, max_length=10)
    warnings: list[str] = Field(default_factory=list)


class OCRProviderError(RuntimeError):
    pass


def validate_image(content: bytes, declared_mime: str) -> tuple[str, str]:
    settings = get_settings()
    if not content or len(content) > settings.ocr_max_image_bytes:
        raise ValueError("IMAGE_TOO_LARGE")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            detected = Image.MIME.get(image.format, "")
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise ValueError("IMAGE_DECODE_FAILED") from exc
    if detected not in ALLOWED_MIME or declared_mime not in ALLOWED_MIME or detected != declared_mime:
        raise ValueError("UNSUPPORTED_IMAGE_TYPE")
    if width * height > settings.ocr_max_pixels:
        raise ValueError("IMAGE_TOO_LARGE")
    return detected, ALLOWED_MIME[detected]


def store_asset(db: Session, student_id: str, school_id: str, original_name: str, declared_mime: str, content: bytes) -> UploadedAsset:
    detected_mime, suffix = validate_image(content, declared_mime)
    storage_key = f"{uuid.uuid4().hex}{suffix}"
    get_object_storage().save(storage_key, content)
    asset = UploadedAsset(
        student_id=student_id,
        school_id=school_id,
        storage_key=storage_key,
        original_name=Path(original_name or "question").name[:255],
        safe_name=storage_key,
        declared_mime=declared_mime,
        detected_mime=detected_mime,
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=get_settings().ocr_retention_days),
    )
    db.add(asset)
    db.commit()
    return asset


def _extract_json(value: str) -> dict:
    value = re.sub(r"^\s*\x60\x60\x60(?:json)?", "", value)
    value = re.sub(r"\x60\x60\x60\s*$", "", value).strip()
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end < start:
        raise OCRProviderError("OCR response did not contain JSON")
    return json.loads(value[start : end + 1])


def parse_ocr_text(value: str) -> OCRDocument:
    lines = [line.strip() for line in value.replace("\r", "\n").split("\n") if line.strip()]
    option_pattern = re.compile(r"^([A-HＡ-Ｈ])\s*[\.．、:：\)]\s*(.+)$", re.IGNORECASE)
    stem_lines: list[str] = []
    options: list[OCROption] = []
    for line in lines:
        match = option_pattern.match(line)
        if match:
            label = chr(ord("A") + ord(match.group(1).upper()) - ord("Ａ")) if "Ａ" <= match.group(1).upper() <= "Ｈ" else match.group(1).upper()
            options.append(OCROption(label=label, value=match.group(2).strip(), confidence=0))
        elif options:
            options[-1].value += line
        else:
            stem_lines.append(line)
    stem = "\n".join(stem_lines).strip()
    if not stem:
        raise OCRProviderError("OCR did not recognize a question stem")
    warnings = ["供应商未提供逐字段置信度，请核对识别内容。"]
    if not options:
        warnings.append("未可靠分离题目选项，请手动补充或改用文字输入。")
    return OCRDocument(question_type="single_choice" if options else "unknown", stem=OCRValue(value=stem, confidence=0), options=options, warnings=warnings)


def recognize(content: bytes, mime: str) -> OCRDocument:
    settings = get_settings()
    if settings.mock_ocr:
        return OCRDocument(
            question_type="single_choice",
            stem=OCRValue(value="驾驶机动车通过没有交通信号的交叉路口怎样行驶？", confidence=0.99),
            options=[
                OCROption(label="A", value="减速慢行，并让右方道路来车先行", confidence=0.96),
                OCROption(label="B", value="加速通过", confidence=0.96),
            ],
            warnings=["当前为本地 mock OCR，真实模型冒烟仍需单独验收。"],
        )
    prompt = "请原样提取图片中的全部文字，保留题干和每个选项的换行。不要解题，不要解释，不要添加图片中不存在的内容。"
    encoded = base64.b64encode(content).decode()
    body = {
        "model": settings.ocr_model_id,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
            {"type": "text", "text": prompt},
        ]}],
        "temperature": 0,
    }
    try:
        response = httpx.post(
            f"{settings.dashscope_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
            json=body,
            timeout=settings.model_timeout_seconds,
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]["content"]
        try:
            return OCRDocument.model_validate(_extract_json(message))
        except (json.JSONDecodeError, ValidationError, OCRProviderError):
            return parse_ocr_text(message)
    except (httpx.HTTPError, KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise OCRProviderError("OCR provider failed") from exc


def process_ocr_task(task_id: str) -> None:
    with SessionLocal() as db:
        task = db.get(OCRTask, task_id)
        if not task or task.status not in {"QUEUED", "PROCESSING"}:
            return
        task.status = "PROCESSING"
        task.attempt_count += 1
        task.started_at = datetime.now(timezone.utc)
        db.commit()
        try:
            asset = db.get(UploadedAsset, task.asset_id)
            if not asset or asset.status != "READY":
                raise OCRProviderError("asset unavailable")
            content = get_object_storage().read(asset.storage_key)
            last_error: Exception | None = None
            result = None
            for attempt in range(get_settings().ocr_max_retries):
                task.attempt_count = attempt + 1
                db.commit()
                try:
                    result = recognize(content, asset.detected_mime)
                    break
                except OCRProviderError as exc:
                    last_error = exc
            if result is None:
                raise OCRProviderError("OCR retries exhausted") from last_error
            threshold = get_settings().ocr_low_confidence_threshold
            fields = [OCRField(
                task_id=task.id,
                field_type="stem",
                sequence=0,
                original_value=result.stem.value.strip(),
                confidence=result.stem.confidence,
                needs_confirmation=result.stem.confidence < threshold,
            )]
            fields.extend(OCRField(
                task_id=task.id,
                field_type="option",
                label=option.label.strip().upper(),
                sequence=index,
                original_value=option.value.strip(),
                confidence=option.confidence,
                needs_confirmation=option.confidence < threshold,
            ) for index, option in enumerate(result.options))
            db.add_all(fields)
            task.question_type = result.question_type
            task.warnings = result.warnings
            task.status = "WAITING_USER"
            task.completed_at = datetime.now(timezone.utc)
            task.error_code = None
            task.error_message_safe = None
            db.commit()
        except Exception:
            task.status = "FAILED"
            task.error_code = "OCR_PROVIDER_ERROR"
            task.error_message_safe = "识别失败，请重试或改用文字输入。"
            task.completed_at = datetime.now(timezone.utc)
            db.commit()


def delete_expired_assets() -> int:
    deleted = 0
    with SessionLocal() as db:
        assets = db.scalars(select(UploadedAsset).where(UploadedAsset.expires_at <= datetime.now(timezone.utc), UploadedAsset.status == "READY")).all()
        for asset in assets:
            get_object_storage().delete(asset.storage_key)
            asset.status = "DELETED"
            deleted += 1
        db.commit()
    return deleted
