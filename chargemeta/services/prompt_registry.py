from functools import lru_cache
from pathlib import Path

import yaml

PROMPT_ROOT = Path(__file__).parents[2] / "prompts"


@lru_cache
def load_prompt(name: str) -> dict:
    path = PROMPT_ROOT / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt不存在: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))
