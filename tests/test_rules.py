from chargemeta.services.rules import classify_domain, detect_sensitivity, mask_sample


def test_domain_classification():
    assert classify_domain("charger_device")[0] == "设备资产域"
    assert classify_domain("carbon_report")[0] == "碳资产域"


def test_sensitive_and_masking():
    assert detect_sensitivity("mobile_phone", ["13800138000"])[0] == "L3-个人敏感"
    assert mask_sample("13800138000") == "138****8000"
