import json
from abc import ABC, abstractmethod
from typing import ClassVar

import httpx

from ..config import get_settings
from ..schemas import SemanticResult
from .prompt_registry import load_prompt

SYSTEM_PROMPT = load_prompt("governance")["system"]


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    async def infer(self, context: dict) -> SemanticResult: ...


class MockProvider(LLMProvider):
    name = "mock"
    NAMES: ClassVar[dict[str, str]] = {
        "device_id": "设备ID",
        "dev_sn": "设备序列号",
        "station_id": "充电站ID",
        "connector_id": "充电枪ID",
        "gun_no": "充电枪编号",
        "soc_val": "电池剩余电量",
        "rated_kw": "额定功率",
        "mobile_phone": "客户手机号码",
        "plate_number": "车牌号码",
        "actual_amt": "实际支付金额",
        "charged_energy": "充电电量",
        "collect_time": "采集时间",
    }

    async def infer(self, context: dict) -> SemanticResult:
        name = context["column_name"]
        business_name = self.NAMES.get(name, name.replace("_", " ").title())
        confidence = 0.91 if name in self.NAMES else 0.68
        return SemanticResult(
            business_name=business_name,
            description=f"{context['table_name']}表中的{business_name}字段",
            semantic_type="标识" if name.endswith(("_id", "_no", "_sn")) else "业务属性",
            sensitivity=context.get("sensitivity", "L1-公开"),
            confidence=confidence,
            evidence=["字段命名语义", "所属表上下文", "脱敏样本特征"],
        )


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self):
        self.settings = get_settings()

    async def infer(self, context: dict) -> SemanticResult:
        prompt = f"上下文：{json.dumps(context, ensure_ascii=False)}\nJSON Schema：{json.dumps(SemanticResult.model_json_schema(), ensure_ascii=False)}"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.settings.ollama_base_url}/api/chat",
                json={
                    "model": self.settings.ollama_model,
                    "stream": False,
                    "format": "json",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "options": {"temperature": 0.1},
                },
            )
            response.raise_for_status()
        return SemanticResult.model_validate_json(response.json()["message"]["content"])


class BailianProvider(LLMProvider):
    name = "bailian"

    def __init__(self):
        self.settings = get_settings()

    async def infer(self, context: dict) -> SemanticResult:
        if not self.settings.bailian_api_key:
            raise RuntimeError("BAILIAN_API_KEY未配置")
        headers = {"Authorization": f"Bearer {self.settings.bailian_api_key}"}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.settings.bailian_base_url}/chat/completions",
                headers=headers,
                json={
                    "model": self.settings.bailian_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
        return SemanticResult.model_validate_json(response.json()["choices"][0]["message"]["content"])


def get_llm_provider(force_cloud: bool = False) -> LLMProvider:
    settings = get_settings()
    provider = "bailian" if force_cloud and settings.bailian_api_key else settings.llm_provider.lower()
    return {"ollama": OllamaProvider, "bailian": BailianProvider}.get(provider, MockProvider)()
