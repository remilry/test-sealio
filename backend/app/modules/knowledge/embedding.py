"""Text → vectors for the semantic half of the search.

`fastembed` runs a small model locally (no API call, no cost). Tests use `HashEmbedder`, which is
deterministic and instant, so only the tests marked `slow` ever load the model.
"""

import hashlib
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

MODEL = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
CACHE_DIR = Path.home() / ".cache" / "fastembed"


class Embedder(Protocol):
    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedder:
    def __init__(self) -> None:
        # Imported here: loading onnxruntime is slow and the hash embedder does not need it.
        from fastembed import TextEmbedding

        # Downloaded once into ~/.cache/fastembed, offline afterwards (fastembed's default is the
        # system temp folder, which the OS may empty).
        self._model = TextEmbedding(MODEL, cache_dir=str(CACHE_DIR))

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        # bge models expect queries with an instruction prefix: query_embed adds it.
        return next(iter(self._model.query_embed(text))).tolist()


class HashEmbedder:
    """Bag of hashed words, normalised: texts sharing words are close. For tests only."""

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    @staticmethod
    def _embed(text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        for word in re.findall(r"\w+", text.lower()):
            digest = hashlib.blake2b(word.encode(), digest_size=4).digest()
            vector[int.from_bytes(digest) % DIMENSIONS] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


@lru_cache
def get_embedder() -> Embedder:
    if get_settings().embedder == "hash":
        return HashEmbedder()
    return FastEmbedder()
