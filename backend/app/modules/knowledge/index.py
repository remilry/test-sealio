"""Hybrid search over a tenant's passages: vectors (pgvector) + full text (tsvector), fused by RRF.

The full-text half catches identifiers, policy numbers and proper names; the vector half catches
rephrasings ("legal form" vs "company limited by shares").
"""

from sqlalchemy import Text, cast, func, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.orm import Session

from app.modules.knowledge.chunking import Passage
from app.modules.knowledge.embedding import Embedder
from app.modules.knowledge.models import Chunk, Document, DocumentStatus
from app.modules.knowledge.schemas import FoundPassage

# Candidates taken from each half before fusion.
CANDIDATES = 40
# Reciprocal Rank Fusion constant (60 in the original paper).
RRF_K = 60


def store(session: Session, document_id: int, passages: list[Passage], embedder: Embedder) -> None:
    vectors = embedder.embed_passages([f"{p.context}\n{p.text}" for p in passages])
    session.add_all(
        Chunk(
            document_id=document_id,
            position=position,
            page=passage.page,
            box=passage.box.model_dump() if passage.box else None,
            text=passage.text,
            context=passage.context,
            embedding=vector,
        )
        for position, (passage, vector) in enumerate(zip(passages, vectors, strict=True))
    )


def search(
    session: Session, tenant_id: int, query: str, embedder: Embedder, k: int = 8
) -> list[FoundPassage]:
    """The k passages of the tenant's indexed documents that best match the query."""
    searchable = (
        select(Chunk.id)
        .join(Document, Document.id == Chunk.document_id)
        .where(Document.tenant_id == tenant_id, Document.status == DocumentStatus.INDEXED)
    )
    by_vector = session.scalars(
        searchable.order_by(Chunk.embedding.cosine_distance(embedder.embed_query(query))).limit(
            CANDIDATES
        )
    ).all()
    # Any of the query's words (plainto_tsquery would require all of them).
    tsquery = cast(
        func.replace(cast(func.plainto_tsquery("english", query), Text), "&", "|"), TSQUERY
    )
    by_text = session.scalars(
        searchable.where(Chunk.tsv.op("@@")(tsquery))
        .order_by(func.ts_rank_cd(Chunk.tsv, tsquery).desc())
        .limit(CANDIDATES)
    ).all()

    scores: dict[int, float] = {}
    for ranking in (by_vector, by_text):
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
    best = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)[:k]
    rows = {
        chunk.id: (chunk, name)
        for chunk, name in session.execute(
            select(Chunk, Document.name)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.id.in_(best))
        ).all()
    }
    return [
        FoundPassage(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_name=name,
            page=chunk.page,
            text=chunk.text,
            score=scores[chunk.id],
        )
        for chunk, name in (rows[chunk_id] for chunk_id in best)
    ]
