"""Resume missing vectors for ACTIVE knowledge only; never rebuild completed rows."""
import argparse
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.core.database import engine, SessionLocal
from app.core.migrations import initialize_database
from app.knowledge.service import ModelGateway, _VECTOR_INDEX_CACHE
from app.models import KnowledgeChunk, KnowledgeVersion


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=3, choices=range(1, 5))
    args = parser.parse_args()
    initialize_database(engine)
    with SessionLocal() as db:
        versions = list(db.scalars(select(KnowledgeVersion).where(KnowledgeVersion.status == "ACTIVE")))
        for version in versions:
            gateway = ModelGateway()
            if gateway.settings.mock_ai:
                raise RuntimeError("Real embedding credentials required")
            if version.embedding_model != gateway.settings.embedding_model_id or version.embedding_dimensions != gateway.settings.embedding_dimensions:
                raise RuntimeError("Configured embedding model/dimensions differ from this index")
            chunks = list(db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.knowledge_version_id == version.id, KnowledgeChunk.embedding.is_(None))))
            batches = [chunks[i:i + 10] for i in range(0, len(chunks), 10)]
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                for batch, vectors in zip(batches, pool.map(lambda batch: gateway.embed([c.content for c in batch]), batches), strict=True):
                    if len(vectors) != len(batch) or any(len(v) != version.embedding_dimensions for v in vectors):
                        raise ValueError("Embedding response shape mismatch")
                    for chunk, vector in zip(batch, vectors, strict=True):
                        chunk.embedding = vector
                        chunk.embedding_status = "READY"
                    db.commit()
                    print(f"backfilled {len(batch)} vectors", flush=True)
            _VECTOR_INDEX_CACHE.pop(version.id, None)
            print(f"Completed: {len(chunks)} missing vectors in {version.version_label}", flush=True)


if __name__ == "__main__":
    main()
