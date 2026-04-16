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
DEFAULT_DEEPSEEK_EMBEDDING_MODEL = "deepseek-embedding"
DEFAULT_DEEPSEEK_EMBEDDING_ENDPOINT = "https://api.deepseek.com/v1/embeddings"
DEFAULT_DEEPSEEK_EMBEDDING_DIMENSIONS = 1024


class EmbeddingBackend:
    name: str
    model: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed(self, text: str) -> list[float]:
        content = (text or "").strip()
        if not content:
            return []
        vectors = self.embed_documents([content])
        return vectors[0] if vectors else []

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


class OpenAICompatibleEmbeddingBackend(EmbeddingBackend):
    """Generic backend for any OpenAI-compatible /v1/embeddings endpoint.

    Works with OpenAI, DeepSeek, or any compatible provider.
    Set ``endpoint`` to the base URL (e.g. ``https://api.deepseek.com/v1/embeddings``).
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        model: str,
        dimensions: int = 1536,
        name: str = "openai-compatible",
        timeout_seconds: int = 60,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self.model = model
        self.dimensions = dimensions
        self.name = name
        self.timeout_seconds = timeout_seconds

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload: dict[str, object] = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }
        request = urllib_request.Request(
            self._endpoint,
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
            raise RuntimeError(f"Embeddings request to {self._endpoint} failed with HTTP {exc.code}: {body[:240]}") from exc
        except urllib_error.URLError as exc:  # pragma: no cover - network-dependent.
            raise RuntimeError(f"Embeddings request to {self._endpoint} failed: {exc.reason}") from exc
        parsed = json.loads(raw)
        data = parsed.get("data", [])
        if len(data) != len(texts):
            raise RuntimeError("Embeddings response size did not match the number of requested texts.")
        vectors = [[round(float(value), 6) for value in item.get("embedding", [])] for item in data]
        if vectors and self.dimensions != len(vectors[0]):
            self.dimensions = len(vectors[0])
        return vectors


# Convenience alias kept for backwards compat
class OpenAIEmbeddingBackend(OpenAICompatibleEmbeddingBackend):
    name = "openai"

    def __init__(
        self,
        model: str = DEFAULT_OPENAI_EMBEDDING_MODEL,
        dimensions: int | None = None,
        timeout_seconds: int = 60,
    ) -> None:
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        super().__init__(
            api_key=api_key,
            endpoint="https://api.openai.com/v1/embeddings",
            model=model,
            dimensions=int(dimensions) if dimensions else 1536,
            name="openai",
            timeout_seconds=timeout_seconds,
        )


def create_embedding_backend(
    backend: str = "auto",
    model: str = "",
    dimensions: int = 0,
) -> EmbeddingBackend:
    normalized = (backend or "auto").strip().lower()
    if normalized == "auto":
        # Priority 1: OpenAI (best quality, paid)
        if os.environ.get("OPENAI_API_KEY", "").strip():
            return OpenAIEmbeddingBackend(model=model or DEFAULT_OPENAI_EMBEDDING_MODEL, dimensions=dimensions or 1536)
        # Priority 2: DeepSeek (good quality, cheap — uses DEEPSEEK_API_KEY)
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if deepseek_key:
            return OpenAICompatibleEmbeddingBackend(
                api_key=deepseek_key,
                endpoint=DEFAULT_DEEPSEEK_EMBEDDING_ENDPOINT,
                model=model or DEFAULT_DEEPSEEK_EMBEDDING_MODEL,
                dimensions=dimensions or DEFAULT_DEEPSEEK_EMBEDDING_DIMENSIONS,
                name="deepseek",
            )
        # Priority 3: local sentence-transformers (free, no API key needed)
        if importlib.util.find_spec("sentence_transformers") is not None:
            return SentenceTransformerEmbeddingBackend(model=model or DEFAULT_SENTENCE_TRANSFORMER_MODEL)
        # Fallback: deterministic hash (no semantic meaning)
        return HashEmbeddingBackend(dimensions=dimensions or DEFAULT_HASH_DIMENSIONS)
    if normalized in {"local-hash", "hash", "local"}:
        return HashEmbeddingBackend(dimensions=dimensions or DEFAULT_HASH_DIMENSIONS)
    if normalized in {"sentence-transformers", "sentence_transformers", "st"}:
        return SentenceTransformerEmbeddingBackend(model=model or DEFAULT_SENTENCE_TRANSFORMER_MODEL)
    if normalized == "openai":
        return OpenAIEmbeddingBackend(model=model or DEFAULT_OPENAI_EMBEDDING_MODEL, dimensions=dimensions or 1536)
    if normalized == "deepseek":
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not deepseek_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured.")
        return OpenAICompatibleEmbeddingBackend(
            api_key=deepseek_key,
            endpoint=DEFAULT_DEEPSEEK_EMBEDDING_ENDPOINT,
            model=model or DEFAULT_DEEPSEEK_EMBEDDING_MODEL,
            dimensions=dimensions or DEFAULT_DEEPSEEK_EMBEDDING_DIMENSIONS,
            name="deepseek",
        )
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
