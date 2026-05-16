from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Callable, Sequence

from material_eval.evidence import EvidenceCard, search_evidence


@dataclass(frozen=True)
class RetrievalQuestion:
    query: str
    expected_sources: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalEvaluationItem:
    query: str
    expected_sources: tuple[str, ...]
    returned_sources: tuple[str, ...]
    top_method: str
    hit: bool


@dataclass(frozen=True)
class RetrievalEvaluationResult:
    total_questions: int
    hits: int
    hit_rate: float
    method_counts: dict[str, int]
    items: tuple[RetrievalEvaluationItem, ...]


def run_retrieval_evaluation(
    questions: Sequence[RetrievalQuestion],
    *,
    search_fn: Callable[[str, int], list[EvidenceCard]] | None = None,
    limit: int = 4,
) -> RetrievalEvaluationResult:
    retriever = search_fn or search_evidence
    items: list[RetrievalEvaluationItem] = []
    method_counter: Counter[str] = Counter()
    for question in questions:
        cards = retriever(question.query, limit)
        returned_sources = tuple(card.source for card in cards)
        top_method = cards[0].retrieval_method if cards else "none"
        method_counter[top_method] += 1
        expected = set(question.expected_sources)
        hit = bool(expected.intersection(returned_sources))
        items.append(
            RetrievalEvaluationItem(
                query=question.query,
                expected_sources=question.expected_sources,
                returned_sources=returned_sources,
                top_method=top_method,
                hit=hit,
            )
        )

    hits = sum(1 for item in items if item.hit)
    total = len(items)
    return RetrievalEvaluationResult(
        total_questions=total,
        hits=hits,
        hit_rate=hits / total if total else 0.0,
        method_counts=dict(method_counter),
        items=tuple(items),
    )


def default_retrieval_questions() -> tuple[RetrievalQuestion, ...]:
    return (
        RetrievalQuestion("机器人 连杆 轻量化", ("人形机器人关节连杆减重白皮书.txt",)),
        RetrievalQuestion("装甲 材料 准入 抗冲击", ("军工装甲材料准入标准_2025.txt",)),
        RetrievalQuestion("工艺 保密 供应商", ("工艺保密规范_V2.txt",)),
    )
