import re

DOMAINS = {
    "场站资产域": ("station", "site", "region", "parking"),
    "设备资产域": ("charger", "connector", "device", "gateway", "firmware"),
    "客户车辆域": ("customer", "user", "vehicle", "fleet", "account"),
    "充电交易域": ("charging", "session", "order", "meter_reading"),
    "计费结算域": ("price", "fee", "payment", "refund", "settlement", "reconciliation"),
    "能源管理域": ("energy", "power", "photovoltaic", "storage", "transformer"),
    "运维告警域": ("alarm", "fault", "maintenance", "work_order", "inspection"),
    "碳资产域": ("carbon", "emission", "reduction"),
}
PATTERNS = {
    "手机号": re.compile(r"^(1\d{10}|1\d{2}\*{4}\d{4})$"),
    "邮箱": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "车牌号": re.compile(r"^[\u4e00-\u9fa5][A-Z][A-Z0-9]{5,6}$"),
    "VIN": re.compile(r"^[A-HJ-NPR-Z0-9]{17}$"),
}


def classify_domain(table_name: str) -> tuple[str, float]:
    lowered = table_name.lower()
    for domain, words in DOMAINS.items():
        if any(word in lowered for word in words):
            return domain, 0.9
    return "公共数据域", 0.55


def detect_sensitivity(column_name: str, samples: list[str]) -> tuple[str, str | None]:
    lowered = column_name.lower()
    if any(x in lowered for x in ("mobile", "phone", "id_card", "email", "address", "plate", "vin")):
        return "L3-个人敏感", "字段名规则命中"
    if any(x in lowered for x in ("longitude", "latitude", "location", "account", "amount")):
        return "L2-内部", "内部属性规则命中"
    for value in samples[:10]:
        for semantic, pattern in PATTERNS.items():
            if pattern.match(value):
                return "L3-个人敏感", f"样本格式匹配{semantic}"
    return "L1-公开", None


def mask_sample(value: str) -> str:
    if re.fullmatch(r"1\d{10}", value):
        return value[:3] + "****" + value[-4:]
    if "@" in value:
        left, right = value.split("@", 1)
        return left[:1] + "***@" + right
    if len(value) == 17 and value.isalnum():
        return value[:3] + "***********" + value[-3:]
    return value[:50]
