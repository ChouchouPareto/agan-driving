import json
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdvisoryKnowledgeDocument


DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "data" / "advisory_authoritative.json"


def import_advisory_documents(db: Session, path: Path = DEFAULT_DATASET) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    for item in payload["documents"]:
        record = db.scalar(select(AdvisoryKnowledgeDocument).where(AdvisoryKnowledgeDocument.external_id == item["external_id"]))
        if record is None:
            record = AdvisoryKnowledgeDocument(external_id=item["external_id"])
            db.add(record)
        for key, value in item.items():
            if key != "external_id":
                setattr(record, key, value)
        record.status = "ACTIVE"
        count += 1
    db.commit()
    return count


def retrieve_advisory_documents(db: Session, query: str, topic: str, license_type: str, region: str, limit: int = 2) -> list[dict]:
    records = list(db.scalars(select(AdvisoryKnowledgeDocument).where(AdvisoryKnowledgeDocument.status == "ACTIVE")))
    if not records:
        import_advisory_documents(db)
        records = list(db.scalars(select(AdvisoryKnowledgeDocument).where(AdvisoryKnowledgeDocument.status == "ACTIVE")))
    tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]\d", query))
    ranked = []
    for record in records:
        haystack = " ".join([record.title, record.summary, record.content, *record.keywords])
        score = (5 if record.topic == topic else 0) + (2 if license_type in record.license_types else 0)
        score += 1 if record.region == "全国" or region in record.region else 0
        score += sum(3 for keyword in record.keywords if keyword in query)
        score += sum(1 for token in tokens if token in haystack)
        if score > 4:
            ranked.append((score, record))
    ranked.sort(key=lambda item: (-item[0], item[1].external_id))
    return [
        {
            "title": record.title,
            "summary": record.summary,
            "content": record.content,
            "source_org": record.source_org,
            "source_url": record.source_url,
            "document_no": record.document_no,
            "effective_at": record.effective_at,
            "region": record.region,
        }
        for _, record in ranked[:limit]
    ]
