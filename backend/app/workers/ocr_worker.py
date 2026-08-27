import argparse
import time

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import OCRTask
from app.ocr_services import delete_expired_assets, process_ocr_task


def run_once() -> int:
    with SessionLocal() as db:
        task_ids = list(db.scalars(select(OCRTask.id).where(OCRTask.status == "QUEUED").limit(10)).all())
    for task_id in task_ids:
        process_ocr_task(task_id)
    delete_expired_assets()
    return len(task_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process persistent OCR jobs")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    while True:
        run_once()
        if args.once:
            break
        time.sleep(max(args.interval, 0.2))


if __name__ == "__main__":
    main()
