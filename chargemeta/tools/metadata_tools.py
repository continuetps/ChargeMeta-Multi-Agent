from sqlalchemy import select

from ..config import get_settings
from ..connectors import SQLAlchemyConnector
from ..db import SessionLocal
from ..models import AssetColumn, AssetTable, DataSource, MetadataChange
from ..services.rules import classify_domain, detect_sensitivity, mask_sample


def collect_and_profile(source_id: int) -> dict:
    """Discover structure, persist field-level changes, profile and mask samples."""
    settings = get_settings()
    with SessionLocal() as db:
        source = db.get(DataSource, source_id)
        connector = SQLAlchemyConnector(source.url)
        discovered = connector.discover()
        active_tables = {(item.schema, item.name) for item in discovered}
        previous = db.scalars(select(AssetTable).where(AssetTable.source_id == source_id)).all()
        changes = 0
        for old in previous:
            if (old.schema_name, old.name) not in active_tables:
                db.add(
                    MetadataChange(
                        source_id=source_id,
                        asset_type="table",
                        asset_name=old.name,
                        change_type="deleted",
                        before={"fingerprint": old.fingerprint},
                        after=None,
                    )
                )
                changes += 1
        column_count = sensitive_count = 0
        for item in discovered:
            table = db.scalar(
                select(AssetTable).where(
                    AssetTable.source_id == source_id,
                    AssetTable.schema_name == item.schema,
                    AssetTable.name == item.name,
                )
            )
            if table is None:
                table = AssetTable(
                    source_id=source_id, schema_name=item.schema, name=item.name, fingerprint=item.fingerprint
                )
                db.add(table)
                db.flush()
                db.add(
                    MetadataChange(
                        source_id=source_id,
                        asset_type="table",
                        asset_name=item.name,
                        change_type="created",
                        before=None,
                        after={"fingerprint": item.fingerprint},
                    )
                )
                changes += 1
            elif table.fingerprint != item.fingerprint:
                db.add(
                    MetadataChange(
                        source_id=source_id,
                        asset_type="table",
                        asset_name=item.name,
                        change_type="schema_changed",
                        before={"fingerprint": table.fingerprint},
                        after={"fingerprint": item.fingerprint},
                    )
                )
                changes += 1
            table.comment, table.fingerprint = item.comment, item.fingerprint
            table.domain, table.confidence = classify_domain(item.name)
            table.ai_comment = f"新能源充电网络{table.domain}中的{item.name}业务表"
            active_columns = {column.name for column in item.columns}
            for existing in list(table.columns):
                if existing.name not in active_columns:
                    db.add(
                        MetadataChange(
                            source_id=source_id,
                            asset_type="column",
                            asset_name=f"{item.name}.{existing.name}",
                            change_type="deleted",
                            before={"data_type": existing.data_type},
                            after=None,
                        )
                    )
                    changes += 1
            for discovered_column in item.columns:
                column = db.scalar(
                    select(AssetColumn).where(
                        AssetColumn.table_id == table.id, AssetColumn.name == discovered_column.name
                    )
                )
                if column is None:
                    column = AssetColumn(
                        table_id=table.id, name=discovered_column.name, data_type=discovered_column.data_type
                    )
                    db.add(column)
                    db.add(
                        MetadataChange(
                            source_id=source_id,
                            asset_type="column",
                            asset_name=f"{item.name}.{discovered_column.name}",
                            change_type="created",
                            before=None,
                            after={"data_type": discovered_column.data_type},
                        )
                    )
                    changes += 1
                elif column.data_type != discovered_column.data_type:
                    db.add(
                        MetadataChange(
                            source_id=source_id,
                            asset_type="column",
                            asset_name=f"{item.name}.{discovered_column.name}",
                            change_type="type_changed",
                            before={"data_type": column.data_type},
                            after={"data_type": discovered_column.data_type},
                        )
                    )
                    changes += 1
                profile = connector.profile_column(
                    item.name, discovered_column.name, item.schema, settings.sample_limit
                )
                raw_samples = profile.get("samples", [])
                sensitivity, reason = detect_sensitivity(discovered_column.name, raw_samples)
                profile["samples"] = [mask_sample(value) for value in raw_samples]
                column.data_type, column.nullable, column.primary_key = (
                    discovered_column.data_type,
                    discovered_column.nullable,
                    discovered_column.primary_key,
                )
                column.comment, column.profile, column.sensitivity = (
                    discovered_column.comment,
                    profile,
                    sensitivity,
                )
                if reason:
                    column.evidence = list(dict.fromkeys([*column.evidence, reason]))
                sensitive_count += sensitivity != "L1-公开"
                column_count += 1
            db.commit()
        return {
            "tables": len(discovered),
            "columns": column_count,
            "sensitive_columns": sensitive_count,
            "metadata_changes": changes,
        }
