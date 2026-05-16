from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from material_eval.embeddings import (
    DenseEmbeddingProvider,
    build_bge_m3_provider_from_env,
    cosine_similarity,
    rank_texts_by_dense_similarity,
)
from material_eval.evidence_store import EvidenceChunkRecord, SqliteEvidenceRepository
from material_eval.ingestion import ingest_knowledge_base
from material_eval.storage import DEFAULT_DB_PATH

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - exercised only in minimal fallback installs
    BM25Okapi = None


DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge_base"


@dataclass(frozen=True)
class EvidenceCard:
    source: str
    text: str
    score: float
    source_type: str = "内部种子资料"
    retrieval_method: str = "keyword"
    chunk_id: int | None = None

    @property
    def summary(self) -> str:
        snippet = self.text.strip()
        return snippet[:140] + ("..." if len(snippet) > 140 else "")


def load_documents(
    knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR,
    evidence_db_path: Path | str = DEFAULT_DB_PATH,
) -> list[EvidenceCard]:
    repository = SqliteEvidenceRepository(evidence_db_path)
    chunks = repository.sync_knowledge_base(knowledge_dir)
    if chunks:
        return [_card_from_chunk(chunk) for chunk in chunks]

    cards: list[EvidenceCard] = []
    for document in ingest_knowledge_base(Path(knowledge_dir)):
        if document.markdown:
            cards.append(
                EvidenceCard(
                    source=document.source,
                    text=document.markdown,
                    score=0,
                    source_type=f"内部种子资料/{document.parser}",
                )
            )
    return cards


def search_evidence(
    query: str,
    limit: int = 4,
    knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR,
    evidence_db_path: Path | str = DEFAULT_DB_PATH,
    retrieval_mode: str | None = None,
    embedding_provider: DenseEmbeddingProvider | None = None,
) -> list[EvidenceCard]:
    documents = load_documents(knowledge_dir, evidence_db_path=evidence_db_path)
    if not documents:
        return []

    mode = (retrieval_mode or "bm25").strip().lower()
    if mode in {"embedding", "bge-m3", "bge-m3+dense"}:
        embedding_results = _search_embeddings(
            query,
            documents,
            limit,
            embedding_provider,
            repository=SqliteEvidenceRepository(evidence_db_path),
        )
        if embedding_results:
            return embedding_results

    if BM25Okapi is not None:
        bm25_results = _search_bm25(query, documents, limit)
        if bm25_results:
            return bm25_results

    return _search_keyword(query, documents, limit)


def _search_embeddings(
    query: str,
    documents: list[EvidenceCard],
    limit: int,
    embedding_provider: DenseEmbeddingProvider | None,
    repository: SqliteEvidenceRepository | None = None,
) -> list[EvidenceCard]:
    provider = embedding_provider or build_bge_m3_provider_from_env()
    try:
        if repository is not None and all(card.chunk_id is not None for card in documents):
            scores = _rank_cards_with_cached_embeddings(query, documents, provider, repository, limit)
        else:
            texts = [f"{card.source}\n{card.text}" for card in documents]
            scores = rank_texts_by_dense_similarity(query, texts, provider, limit=limit)
    except Exception:
        return []

    results: list[EvidenceCard] = []
    for score in scores:
        score_value = score.score
        index = score.index
        if score_value <= 0:
            continue
        card = documents[index]
        results.append(
            EvidenceCard(
                source=card.source,
                text=card.text,
                score=float(score_value),
                source_type=card.source_type,
                retrieval_method=provider.name,
                chunk_id=card.chunk_id,
            )
        )
    return results


def _rank_cards_with_cached_embeddings(
    query: str,
    documents: list[EvidenceCard],
    provider: DenseEmbeddingProvider,
    repository: SqliteEvidenceRepository,
    limit: int,
):
    from material_eval.embeddings import DenseSearchScore

    query_vector = provider.embed_texts([query])[0]
    chunks = [
        EvidenceChunkRecord(
            id=card.chunk_id or 0,
            document_id=0,
            source=card.source,
            source_path="",
            parser=card.source_type.removeprefix("内部证据库/"),
            chunk_index=idx,
            text=card.text,
            text_hash="",
        )
        for idx, card in enumerate(documents)
    ]
    cached_vectors = repository.get_or_create_embeddings(provider, chunks)
    scores = [
        DenseSearchScore(
            index=idx,
            score=cosine_similarity(query_vector, cached_vectors[card.chunk_id or 0]),
        )
        for idx, card in enumerate(documents)
        if card.chunk_id in cached_vectors
    ]
    return sorted(scores, key=lambda item: (item.score, -item.index), reverse=True)[:limit]


def _search_bm25(query: str, documents: list[EvidenceCard], limit: int) -> list[EvidenceCard]:
    tokenized_corpus = [_tokenize(f"{card.source}\n{card.text}") for card in documents]
    query_tokens = _tokenize(query)
    if not query_tokens or not any(tokenized_corpus):
        return []

    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query_tokens)
    scored = []
    for card, corpus_tokens, score in zip(documents, tokenized_corpus, scores):
        overlap = len(set(query_tokens).intersection(corpus_tokens))
        score_value = float(score) if score > 0 else float(overlap) * 1e-6
        if score_value > 0:
            scored.append(
                EvidenceCard(
                    source=card.source,
                    text=card.text,
                    score=score_value,
                    source_type=card.source_type,
                    retrieval_method="bm25",
                    chunk_id=card.chunk_id,
                )
            )
    return sorted(scored, key=lambda card: (card.score, card.source), reverse=True)[:limit]


def _search_keyword(query: str, documents: list[EvidenceCard], limit: int) -> list[EvidenceCard]:
    terms = _query_terms(query)
    scored: list[EvidenceCard] = []
    for card in documents:
        haystack = f"{card.source}\n{card.text}".lower()
        score = sum(haystack.count(term.lower()) for term in terms)
        if score:
            scored.append(
                EvidenceCard(
                    source=card.source,
                    text=card.text,
                    score=float(score),
                    source_type=card.source_type,
                    retrieval_method="keyword",
                    chunk_id=card.chunk_id,
                )
            )

    if not scored:
        # MVP fallback: expose seed documents instead of silently pretending no context exists.
        return [
            EvidenceCard(
                source=card.source,
                text=card.text,
                score=0.0,
                source_type=card.source_type,
                retrieval_method="fallback",
                chunk_id=card.chunk_id,
            )
            for card in documents[:limit]
        ]

    return sorted(scored, key=lambda card: (card.score, card.source), reverse=True)[:limit]


def _query_terms(query: str) -> list[str]:
    normalized = query.strip()
    ascii_terms = re.findall(r"[A-Za-z0-9_+\-.]{2,}", normalized)
    chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
    terms = ascii_terms + chinese_terms

    # Add a few overlapping Chinese n-grams to improve matching on tiny seed docs.
    compact_cn = "".join(chinese_terms)
    if len(compact_cn) >= 4:
        terms.extend(compact_cn[i : i + 4] for i in range(0, len(compact_cn) - 3, 2))

    seen: set[str] = set()
    unique_terms: list[str] = []
    for term in terms:
        if term not in seen:
            seen.add(term)
            unique_terms.append(term)
    return unique_terms


def _card_from_chunk(chunk: EvidenceChunkRecord) -> EvidenceCard:
    return EvidenceCard(
        source=chunk.source,
        text=chunk.text,
        score=0.0,
        source_type=f"内部证据库/{chunk.parser}",
        chunk_id=chunk.id,
    )


def _tokenize(text: str) -> list[str]:
    ascii_terms = [term.lower() for term in re.findall(r"[A-Za-z0-9_+\-.]{2,}", text)]
    chinese_text = "".join(re.findall(r"[\u4e00-\u9fff]+", text))
    chinese_tokens = list(_char_ngrams(chinese_text, sizes=(2, 3, 4)))
    return _dedupe(ascii_terms + chinese_tokens)


def _char_ngrams(text: str, sizes: Iterable[int]) -> Iterable[str]:
    for size in sizes:
        if len(text) < size:
            continue
        for idx in range(0, len(text) - size + 1):
            yield text[idx : idx + size]


def _dedupe(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_terms: list[str] = []
    for term in terms:
        if term not in seen:
            seen.add(term)
            unique_terms.append(term)
    return unique_terms
