"""生成56张表、约600个字段的新能源充电网络演示库，并注册为数据源。"""

import os
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from chargemeta.db import Base, SessionLocal, engine
from chargemeta.models import DataSource

TABLES = {
    "station": [
        "station_info",
        "station_region",
        "station_parking_space",
        "station_business_hour",
        "station_service_capability",
        "station_operator",
        "station_contract",
    ],
    "device": [
        "charger_device",
        "charger_connector",
        "device_model",
        "device_gateway",
        "device_firmware",
        "device_protocol",
        "device_status_log",
        "device_component",
    ],
    "customer": [
        "customer_profile",
        "customer_address",
        "vehicle_info",
        "fleet_company",
        "fleet_vehicle_relation",
        "customer_account",
        "customer_auth_record",
    ],
    "charging": [
        "charging_order",
        "charging_session",
        "charging_meter_reading",
        "charging_order_detail",
        "charging_stop_reason",
        "charging_abnormal_record",
        "charging_order_relation",
    ],
    "billing": [
        "pricing_strategy",
        "electricity_price_period",
        "service_fee_rule",
        "payment_transaction",
        "refund_transaction",
        "operator_settlement",
        "settlement_detail",
        "reconciliation_record",
    ],
    "energy": [
        "energy_meter",
        "energy_realtime_data",
        "energy_daily_summary",
        "transformer_load",
        "photovoltaic_generation",
        "storage_device",
        "storage_charge_record",
    ],
    "operation": [
        "device_alarm",
        "alarm_dictionary",
        "maintenance_work_order",
        "work_order_process",
        "inspection_plan",
        "inspection_record",
        "device_fault",
        "spare_part_usage",
    ],
    "carbon": [
        "carbon_emission_factor",
        "carbon_reduction_record",
        "carbon_calculation_task",
        "carbon_asset_account",
        "carbon_report",
    ],
}

BASE_COLS = [
    "id INTEGER PRIMARY KEY",
    "station_id INTEGER",
    "device_id INTEGER",
    "status_cd TEXT",
    "created_at TEXT",
    "updated_at TEXT",
    "operator_id INTEGER",
]
SPECIAL = {
    "station": ["station_code TEXT", "station_name TEXT", "longitude REAL", "latitude REAL"],
    "device": ["dev_sn TEXT", "gun_no TEXT", "rated_kw REAL", "proto_ver TEXT"],
    "customer": ["mobile_phone TEXT", "email TEXT", "plate_number TEXT", "vehicle_vin TEXT"],
    "charging": ["soc_val REAL", "charged_energy REAL", "actual_amt REAL", "duration_sec INTEGER"],
    "billing": ["electricity_fee REAL", "service_fee REAL", "discount_amt REAL", "actual_amt REAL"],
    "energy": ["collect_time TEXT", "voltage REAL", "current_amp REAL", "power_kw REAL"],
    "operation": ["alarm_code TEXT", "fault_level TEXT", "work_order_no TEXT", "ext_info TEXT"],
    "carbon": ["carbon_factor REAL", "reduction_kg REAL", "calculation_method TEXT", "report_period TEXT"],
}


def main():
    demo = Path(os.getenv("DEMO_DB_PATH", str(ROOT / "demo_energy.db"))).resolve()
    demo.parent.mkdir(parents=True, exist_ok=True)
    if demo.exists():
        demo.unlink()
    conn = sqlite3.connect(demo)
    for domain, names in TABLES.items():
        for name in names:
            conn.execute(f'CREATE TABLE "{name}" ({", ".join(BASE_COLS + SPECIAL[domain])})')
            for i in range(1, 7):
                cols = [x.split()[0] for x in BASE_COLS + SPECIAL[domain]]
                values = [
                    i,
                    random.randint(1, 5),
                    random.randint(1, 20),
                    random.choice(["ACTIVE", "OFFLINE", "DONE"]),
                    "2026-09-18 10:00:00",
                    "2026-09-18 12:00:00",
                    1,
                ]
                extras = {
                    "station": [f"ST{i:04d}", f"示范充电站{i}", 121.4 + i / 100, 31.2 + i / 100],
                    "device": [f"DEV2026{i:06d}", f"GUN-{i}", random.choice([60, 120, 180]), "OCPP1.6"],
                    "customer": [
                        f"1380013{i:04d}",
                        f"user{i}@demo.local",
                        f"沪A{i:05d}",
                        f"LHGCM82633A{i:06d}",
                    ],
                    "charging": [
                        random.randint(10, 95),
                        round(random.uniform(5, 80), 2),
                        round(random.uniform(10, 150), 2),
                        random.randint(600, 7200),
                    ],
                    "billing": [10.5, 5.2, 2.0, 13.7],
                    "energy": ["2026-09-18 10:00:00", 380.0, 120.5, 45.8],
                    "operation": [f"ALM{i:03d}", "P2", f"WO2026{i:05d}", "模拟故障信息"],
                    "carbon": [0.5703, 12.4, "模拟核算方法", "2026-09"],
                }[domain]
                marks = ",".join("?" for _ in cols)
                conn.execute(f'INSERT INTO "{name}" ({",".join(cols)}) VALUES ({marks})', values + extras)
    conn.commit()
    conn.close()
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.query(DataSource).filter_by(name="新能源充电网络演示库").first():
            db.add(DataSource(name="新能源充电网络演示库", kind="sqlite", url=f"sqlite:///{demo.as_posix()}"))
            db.commit()
    print(f"完成：{sum(map(len, TABLES.values()))}张表，演示库位于 {demo}")


if __name__ == "__main__":
    main()
