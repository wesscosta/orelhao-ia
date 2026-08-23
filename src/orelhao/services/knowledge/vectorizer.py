from __future__ import annotations

import hashlib
import re
import unicodedata

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def _features(text: str) -> list[str]:
    normalized = _normalize(text)
    tokens = _TOKEN_RE.findall(normalized)
    features = [f"w:{token}" for token in tokens]
    compact = " ".join(tokens)
    features.extend(f"c:{compact[i:i+3]}" for i in range(max(0, len(compact) - 2)))
    return features


def hashing_vector(text: str, *, dimensions: int = 384) -> np.ndarray:
    if dimensions <= 0:
        raise ValueError("dimensions deve ser positivo")
    vector = np.zeros(dimensions, dtype=np.float32)
    for feature in _features(text):
        raw = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        number = int.from_bytes(raw, "little")
        index = number % dimensions
        sign = 1.0 if number & 1 else -1.0
        vector[index] += sign
    norm = float(np.linalg.norm(vector))
    if norm:
        vector /= norm
    return vector
