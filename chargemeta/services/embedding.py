import hashlib
import math
import re

import httpx

from ..config import get_settings


def _hash_embedding(text: str, dimension: int) -> list[float]:
    """Deterministic feature hashing fallback; no model download required."""
    vector = [0.0] * dimension
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    tokens += [text[i : i + 2] for i in range(max(0, len(text) - 1))]
    for token in tokens:
        digest = hashlib.sha256(token.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        vector[index] += 1.0 if digest[4] % 2 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


async def embed_text(text: str) -> list[float]:
    settings = get_settings()
    if settings.embedding_provider == "ollama":
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/embed",
                json={"model": settings.ollama_embedding_model, "input": text},
            )
            response.raise_for_status()
        vector = response.json()["embeddings"][0]
        vector = (vector + [0.0] * settings.embedding_dimension)[: settings.embedding_dimension]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
    return _hash_embedding(text, settings.embedding_dimension)


def cosine_similarity(left: list[float] | None, right: list[float]) -> float:
    if not left:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=False))
