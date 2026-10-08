from itertools import pairwise

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import AssetColumn, AssetRelation, AssetTable


def _value_overlap(left: AssetColumn, right: AssetColumn) -> float:
    left_values = set(left.profile.get("samples", []))
    right_values = set(right.profile.get("samples", []))
    if not left_values or not right_values:
        return 0.0
    return len(left_values & right_values) / min(len(left_values), len(right_values))


def infer_relations(source_id: int) -> dict:
    settings = get_settings()
    ignored = {"id", "created_at", "updated_at", "status_cd", "operator_id"}
    created = reviewed = 0
    with SessionLocal() as db:
        tables = db.scalars(select(AssetTable).where(AssetTable.source_id == source_id)).all()
        groups: dict[str, list[AssetColumn]] = {}
        for table in tables:
            for column in table.columns:
                if column.name not in ignored and column.name.endswith(("_id", "_no", "_sn", "_code")):
                    groups.setdefault(column.name, []).append(column)
        for name, columns in groups.items():
            for source, target in pairwise(columns):
                overlap = _value_overlap(source, target)
                type_compatible = source.data_type.lower() == target.data_type.lower()
                confidence = min(0.98, 0.55 + 0.18 + (0.12 if type_compatible else 0) + 0.13 * overlap)
                evidence = [
                    f"字段名{name}一致",
                    f"数据类型{'一致' if type_compatible else '不一致'}",
                    f"脱敏样本值重合率{overlap:.0%}",
                ]
                relation = db.scalar(
                    select(AssetRelation).where(
                        AssetRelation.source_column_id == source.id,
                        AssetRelation.target_column_id == target.id,
                        AssetRelation.relation_type == "logical_fk",
                    )
                )
                if relation is None:
                    relation = AssetRelation(
                        source_column_id=source.id, target_column_id=target.id, relation_type="logical_fk"
                    )
                    db.add(relation)
                    created += 1
                relation.confidence, relation.evidence = round(confidence, 4), evidence
                relation.review_status = (
                    "auto_published" if confidence >= settings.relation_min_confidence else "pending"
                )
                reviewed += relation.review_status == "pending"
        db.commit()
        total = sum(len(items) - 1 for items in groups.values() if len(items) > 1)
    return {"relations": total, "created": created, "pending_review": reviewed}
