from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import AssetColumn, AssetTable, ReviewTask


def _recommended_rules(column: AssetColumn) -> list[dict]:
    name = column.name.lower()
    rules = []
    if name in {"soc_val", "start_soc", "end_soc"}:
        rules.append({"type": "range", "min": 0, "max": 100, "reason": "SOC百分比标准范围"})
    if any(token in name for token in ("mobile", "phone")):
        rules.append({"type": "regex", "pattern": "^1\\d{10}$", "reason": "中国大陆手机号格式"})
    if column.primary_key:
        rules += [{"type": "not_null"}, {"type": "unique"}]
    if name.endswith(("_id", "_no", "_code")) and not column.nullable:
        rules.append({"type": "not_null"})
    return rules


def inspect_quality(job_id: int, source_id: int) -> dict:
    settings = get_settings()
    with SessionLocal() as db:
        columns = db.scalars(
            select(AssetColumn).join(AssetTable).where(AssetTable.source_id == source_id)
        ).all()
        total = len(columns)
        missing = low_confidence = pending = type_conflicts = 0
        confidence_sum = 0.0
        for column in columns:
            missing += not bool(column.business_name and column.ai_comment)
            low_confidence += column.confidence < settings.review_threshold
            pending += column.review_status == "pending"
            confidence_sum += column.confidence
            lowered_type = column.data_type.lower()
            if any(
                token in column.name.lower() for token in ("amount", "amt", "fee", "power", "energy")
            ) and not any(
                token in lowered_type for token in ("int", "real", "float", "double", "decimal", "numeric")
            ):
                type_conflicts += 1
            profile = dict(column.profile)
            profile["recommended_rules"] = _recommended_rules(column)
            column.profile = profile
            if column.review_status == "pending":
                existing = db.scalar(
                    select(ReviewTask).where(ReviewTask.job_id == job_id, ReviewTask.column_id == column.id)
                )
                if existing is None:
                    db.add(
                        ReviewTask(
                            job_id=job_id,
                            column_id=column.id,
                            reason="AI语义置信度未达到自动发布阈值",
                            priority="high" if column.sensitivity != "L1-公开" else "medium",
                            ai_snapshot={
                                "business_name": column.business_name,
                                "description": column.ai_comment,
                                "confidence": column.confidence,
                                "evidence": column.evidence,
                            },
                        )
                    )
        db.commit()
        average = confidence_sum / total if total else 0
        pending_ratio = pending / total if total else 0
        missing_ratio = missing / total if total else 0
        retry = (
            average < settings.quality_min_average_confidence
            or missing_ratio > 0.05
            or pending_ratio > settings.quality_max_pending_ratio
        )
        return {
            "total_columns": total,
            "average_confidence": round(average, 4),
            "missing_annotations": missing,
            "low_confidence": low_confidence,
            "pending_reviews": pending,
            "pending_ratio": round(pending_ratio, 4),
            "type_conflicts": type_conflicts,
            "recommended_rules": sum(len(c.profile.get("recommended_rules", [])) for c in columns),
            "retry_governance": retry,
            "review_required": pending > 0 or type_conflicts > 0,
            "quality_passed": not retry,
        }
