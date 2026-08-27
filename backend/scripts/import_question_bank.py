import argparse
from pathlib import Path

from app.core.database import SessionLocal
from app.knowledge.service import import_bank

parser = argparse.ArgumentParser(description="Import a trusted Subject 1 question bank")
parser.add_argument("path", type=Path)
parser.add_argument("--name", required=True)
parser.add_argument("--supplier", required=True)
parser.add_argument("--version", required=True)
args = parser.parse_args()
with SessionLocal() as db:
    version = import_bank(db, args.path.resolve(), name=args.name, supplier=args.supplier, version_label=args.version)
    print({"version_id": version.id, "status": version.status, "items": version.item_count, "errors": version.error_count})
