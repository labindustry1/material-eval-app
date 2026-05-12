from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence


class DenseEmbeddingProvider(Protocol):
    name: str

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        ...


@dataclass(frozen=True)
class EmbeddingConfig:
    model_name: str = "BAAI/bge-m3"
    use_fp16: bool = True
    batch_size: int = 8
    max_length: int = 1024

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        return cls(
            model_name=os.getenv("BGE_M3_MODEL_NAME", "BAAI/bge-m3"),
            use_fp16=_env_bool("BGE_M3_USE_FP16", default=True),
            batch_size=int(os.getenv("BGE_M3_BATCH_SIZE", "8")),
            max_length=int(os.getenv("BGE_M3_MAX_LENGTH", "1024")),
        )


class BgeM3DenseEmbeddingProvider:
    name = "bge-m3+dense"

    def __init__(
        self,
        *,
        model: object | None = None,
        model_name: str = "BAAI/bge-m3",
        use_fp16: bool = True,
        batch_size: int = 8,
        max_length: int = 1024,
    ) -> None:
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.batch_size = batch_size
        self.max_length = max_length
        self._model = model

    @classmethod
    def from_config(cls, config: EmbeddingConfig) -> "BgeM3DenseEmbeddingProvider":
        return cls(
            model_name=config.model_name,
            use_fp16=config.use_fp16,
            batch_size=config.batch_size,
            max_length=config.max_length,
        )

    @classmethod
    def from_env(cls) -> "BgeM3DenseEmbeddingProvider":
        return cls.from_config(EmbeddingConfig.from_env())

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        batch = list(texts)
        if not batch:
            return []
        output = self._load_model().encode(
            batch,
            batch_size=self.batch_size,
            max_length=self.max_length,
        )
        return [_as_float_vector(vector) for vector in output["dense_vecs"]]

    def _load_model(self) -> object:
        if self._model is not None:
            return self._model
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError as exc:  # pragma: no cover - only exercised without optional extra.
            raise RuntimeError(
                "BGE-M3 semantic retrieval requires optional dependency `FlagEmbedding`. "
                "Install the optional extra with `uv pip install '.[bge]'`."
            ) from exc

        self._model = BGEM3FlagModel(self.model_name, use_fp16=self.use_fp16)
        return self._model


@dataclass(frozen=True)
class DenseSearchScore:
    index: int
    score: float


def build_bge_m3_provider_from_env() -> BgeM3DenseEmbeddingProvider:
    return BgeM3DenseEmbeddingProvider.from_env()


def rank_texts_by_dense_similarity(
    query: str,
    texts: Sequence[str],
    provider: DenseEmbeddingProvider,
    *,
    limit: int,
) -> list[DenseSearchScore]:
    if not query.strip() or not texts:
        return []
    vectors = provider.embed_texts([query, *texts])
    query_vector = vectors[0]
    scored = [
        DenseSearchScore(index=idx, score=cosine_similarity(query_vector, text_vector))
        for idx, text_vector in enumerate(vectors[1:])
    ]
    return sorted(scored, key=lambda item: (item.score, -item.index), reverse=True)[:limit]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = list(left)
    right_values = list(right)
    if len(left_values) != len(right_values):
        raise ValueError("Vectors must have the same dimension")
    dot = sum(a * b for a, b in zip(left_values, right_values))
    left_norm = math.sqrt(sum(item * item for item in left_values))
    right_norm = math.sqrt(sum(item * item for item in right_values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _as_float_vector(vector: object) -> list[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(item) for item in vector]  # type: ignore[arg-type]


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
