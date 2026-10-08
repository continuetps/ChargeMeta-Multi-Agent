import re

from pgvector.sqlalchemy import Vector
from sqlalchemy import case, cast, or_, select
from sqlalchemy.orm import Session, joinedload

from ..config import get_settings
from ..models import AssetColumn, AssetTable
from .embedding import cosine_similarity, embed_text

SYNONYMS = {
    "手机号": ["mobile", "phone", "联系电话"],
    "充电枪": ["connector", "gun_no"],
    "功率": ["power", "kw", "rated_kw"],
    "电量": ["energy", "kwh", "charged_energy"],
    "车辆": ["vehicle", "vin", "plate"],
    "告警": ["alarm", "fault", "故障"],
    "金额": ["amount", "amt", "fee"],
}


def _rrf(rankings: list[list[int]], k: int = 60) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, 1):
            scores[item_id] = scores.get(item_id, 0) + 1 / (k + rank)
    return scores


async def search_assets(db: Session, query: str, limit: int = 10) -> list[dict]:
    terms = {query.lower()}
    for key, values in SYNONYMS.items():
        if key in query:
            terms.update(values)
    terms.update(x.lower() for x in re.findall(r"[A-Za-z_]+", query))
    clauses = []
    for term in terms:
        pattern = f"%{term}%"
        clauses += [
            AssetColumn.name.ilike(pattern),
            AssetColumn.business_name.ilike(pattern),
            AssetColumn.ai_comment.ilike(pattern),
            AssetTable.name.ilike(pattern),
            AssetTable.domain.ilike(pattern),
        ]
    keyword_rows = db.scalars(
        select(AssetColumn).join(AssetTable).where(or_(*clauses)).limit(limit * 4)
    ).all()
    query_vector = await embed_text(query)
    if db.bind.dialect.name == "postgresql":
        distance = cast(AssetColumn.embedding, Vector(get_settings().embedding_dimension)).cosine_distance(
            query_vector
        )
        vector_rows = db.scalars(
            select(AssetColumn).where(AssetColumn.embedding.is_not(None)).order_by(distance).limit(limit * 4)
        ).all()
    else:
        candidates = db.scalars(select(AssetColumn).where(AssetColumn.embedding.is_not(None))).all()
        vector_rows = sorted(
            candidates, key=lambda c: cosine_similarity(c.embedding, query_vector), reverse=True
        )[: limit * 4]
    scores = _rrf([[row.id for row in keyword_rows], [row.id for row in vector_rows]])
    ranked_ids = [item[0] for item in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]]
    if not ranked_ids:
        return []
    ordering = case({item_id: index for index, item_id in enumerate(ranked_ids)}, value=AssetColumn.id)
    rows = db.scalars(
        select(AssetColumn)
        .options(joinedload(AssetColumn.table))
        .where(AssetColumn.id.in_(ranked_ids))
        .order_by(ordering)
    ).all()
    return [
        {
            "column_id": c.id,
            "asset": f"{c.table.schema_name}.{c.table.name}.{c.name}",
            "business_name": c.business_name,
            "description": c.ai_comment,
            "domain": c.table.domain,
            "sensitivity": c.sensitivity,
            "confidence": c.confidence,
            "retrieval_score": round(scores[c.id], 6),
            "reason": f"关键词与向量混合召回，命中{c.table.domain}主题域",
        }
        for c in rows
    ]
