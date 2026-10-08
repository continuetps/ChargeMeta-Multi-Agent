import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import create_engine, inspect, text


@dataclass
class DiscoveredColumn:
    name: str
    data_type: str
    nullable: bool
    primary_key: bool
    comment: str | None


@dataclass
class DiscoveredTable:
    schema: str
    name: str
    comment: str | None
    columns: list[DiscoveredColumn]
    fingerprint: str


class SQLAlchemyConnector:
    """SQLite/MySQL/PostgreSQL等SQLAlchemy方言的统一只读元数据连接器。"""

    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)

    def test_connection(self) -> bool:
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True

    def discover(self) -> list[DiscoveredTable]:
        inspector = inspect(self.engine)
        schemas = [None] if self.engine.dialect.name == "sqlite" else inspector.get_schema_names()
        result = []
        for schema in schemas:
            if schema in {"information_schema", "pg_catalog", "pg_toast"}:
                continue
            for table_name in inspector.get_table_names(schema=schema):
                pk = set(
                    (inspector.get_pk_constraint(table_name, schema=schema) or {}).get("constrained_columns")
                    or []
                )
                columns = [
                    DiscoveredColumn(
                        c["name"],
                        str(c["type"]),
                        bool(c.get("nullable", True)),
                        c["name"] in pk,
                        c.get("comment"),
                    )
                    for c in inspector.get_columns(table_name, schema=schema)
                ]
                try:
                    comment = (inspector.get_table_comment(table_name, schema=schema) or {}).get("text")
                except NotImplementedError:
                    comment = None
                raw = json.dumps([c.__dict__ for c in columns], ensure_ascii=False, sort_keys=True)
                result.append(
                    DiscoveredTable(
                        schema or "main",
                        table_name,
                        comment,
                        columns,
                        hashlib.sha256(raw.encode()).hexdigest(),
                    )
                )
        return result

    def profile_column(self, table: str, column: str, schema: str = "main", limit: int = 20) -> dict:
        p = self.engine.dialect.identifier_preparer
        q_table = p.quote(table)
        if schema != "main" and self.engine.dialect.name != "sqlite":
            q_table = f"{p.quote_schema(schema)}.{q_table}"
        try:
            with self.engine.connect() as conn:
                rows = conn.execute(
                    text(
                        f"SELECT {p.quote(column)} AS value FROM {q_table} WHERE {p.quote(column)} IS NOT NULL LIMIT :limit"
                    ),
                    {"limit": limit},
                )
                values = [str(row.value)[:100] for row in rows]
            return {"samples": values, "sample_count": len(values)}
        except Exception as exc:
            return {"samples": [], "sample_count": 0, "error": str(exc)[:200]}
