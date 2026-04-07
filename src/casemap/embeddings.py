from __future__ import annotations

from dataclasses import dataclass
from urllib import error as urllib_error
from urllib import request as urllib_request
import importlib.util
import json
import math
import os
import ssl
import hashlib

from .graphrag import tokenize

DEFAULT_HASH_DIMENSIONS = 256
DEFAULT_SENTENCE_TRANSFORMER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingBackend:
    name: str
    model: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def manifest(self) -> dict:
        return {
            "backend": self.name,
            "model": self.model,
            "dimensions": self.dimensions,
        }


@dataclass
class HashEmbeddingBackend(EmbeddingBackend):
    dimensions: int = DEFAULT_HASH_DIMENSIONS
    name: str = "local-hash"
    model: str = "deterministic-token-hash"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [_hash_embedding(text, dimensions=self.dimensions) for text in texts]


class SentenceTransformerEmbeddingBackend(EmbeddingBackend):
    name = "sentence-transformers"

    def __init__(self, model: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on optional dependency.
            raise RuntimeError(
                "sentence-transformers is not installed. Install it to use the sentence-transformers embedding backend."
            ) from exc
        self.model = model
        self._client = SentenceTransformer(model)
        dimension = getattr(self._client, "get_sentence_embedding_dimension", None)
        self.dimensions = int(dimension()) if callable(dimension) and dimension() else 384

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        encoded = self._client.encode(texts, normalize_embeddings=True)
        return [[round(float(value), 6) for value in row] for row in encoded]


class OpenAIEmbeddingBackend(EmbeddingBackend):
    name = "openai"

    def __init__(
        self,
        model: str = DEFAULT_OPENAI_EMBEDDING_MODEL,
        dimensions: int | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.model = model
        self.dimensions = int(dimensions) if dimensions else 1536
        self.timeout_seconds = timeout_seconds
        self._api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload: dict[str, object] = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }
        if self.model.startswith("text-embedding-3") and self.dimensions:
            payload["dimensions"] = self.dimensions
        request = urllib_request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib_request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", "ignore")
        except urllib_error.HTTPError as exc:  # pragma: no cover - network-dependent.
            body = exc.read().decode("utf-8", "ignore") if hasattr(exc, "read") else ""
            raise RuntimeError(f"OpenAI embeddings request failed with HTTP {exc.code}: {body[:240]}") from exc
        except urllib_error.URLError as exc:  # pragma: no cover - network-dependent.
            raise RuntimeError(f"OpenAI embeddings request failed: {exc.reason}") from exc
        parsed = json.loads(raw)
        data = parsed.get("data", [])
        if len(data) != len(texts):
            raise RuntimeError("OpenAI embeddings response size did not match the number of requested texts.")
        vectors = [[round(float(value), 6) for value in item.get("embedding", [])] for item in data]
        if vectors and self.dimensions != len(vectors[0]):
            self.dimensions = len(vectors[0])
        return vectors


def create_embedding_backend(
    backend: str = "auto",
    model: str = "",
    dimensions: int = 0,
) -> EmbeddingBackend:
    normalized = (backend or "auto").strip().lower()
    if normalized == "auto":
        if os.environ.get("OPENAI_API_KEY", "").strip():
            return OpenAIEmbeddingBackend(model=model or DEFAULT_OPENAI_EMBEDDING_MODEL, dimensions=dimensions or 1536)
        if importlib.util.find_spec("sentence_transformers") is not None:
            return SentenceTransformerEmbeddingBackend(model=model or DEFAULT_SENTENCE_TRANSFORMER_MODEL)
        return HashEmbeddingBackend(dimensions=dimensions or DEFAULT_HASH_DIMENSIONS)
    if normalized in {"local-hash", "hash", "local"}:
        return HashEmbeddingBackend(dimensions=dimensions or DEFAULT_HASH_DIMENSIONS)
    if normalized in {"sentence-transformers", "sentence_transformers", "st"}:
        return SentenceTransformerEmbeddingBackend(model=model or DEFAULT_SENTENCE_TRANSFORMER_MODEL)
    if normalized == "openai":
        return OpenAIEmbeddingBackend(model=model or DEFAULT_OPENAI_EMBEDDING_MODEL, dimensions=dimensions or 1536)
    raise ValueError(f"Unsupported embedding backend: {backend}")


def _hash_embedding(text: str, dimensions: int = DEFAULT_HASH_DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / magnitude, 6) for value in vector]
