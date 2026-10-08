import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chargemeta.db import Base
from chargemeta.models import AssetColumn, AssetTable, DataSource
from chargemeta.services.search import search_assets


@pytest.mark.asyncio
async def test_search_synonym():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        s = DataSource(name="demo", kind="sqlite", url="sqlite://")
        db.add(s)
        db.flush()
        t = AssetTable(
            source_id=s.id, schema_name="main", name="customer_profile", fingerprint="x", domain="客户车辆域"
        )
        db.add(t)
        db.flush()
        db.add(
            AssetColumn(
                table_id=t.id,
                name="mobile_phone",
                data_type="TEXT",
                business_name="客户手机号码",
                ai_comment="客户联系电话",
                confidence=0.9,
            )
        )
        db.commit()
        assert (await search_assets(db, "手机号"))[0]["asset"].endswith("mobile_phone")
