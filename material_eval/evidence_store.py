from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

from material_eval.embeddings import DenseEmbeddingProvider
from material_eval.ingestion import ParsedDocument, ingest_knowledge_base
from material_eval.storage import DEFAULT_DB_PATH


DEFAULT_CHUNK_CHARS = 900
DEFAULT_CHUNK_OVERLAP = 120


@dataclass(frozen=True)
class EvidenceChunkRecord:
    id: int
    document_id: int
    source: str
    source_path: str
    parser: str
    chunk_index: int
    text: str
    text_hash: str


class SqliteEvidenceRepository:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_path TEXT NOT NULL UNIQUE,
                    parser TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    source TEXT NOT NULL,
                    parser TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    UNIQUE(document_id, chunk_index)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_id INTEGER NOT NULL,
                    provider_name TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    vector_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(chunk_id) REFERENCES document_chunks(id) ON DELETE CASCADE,
                    UNIQUE(chunk_id, provider_name)
                )
                """
            )

    def sync_knowledge_base(self, knowledge_dir: Path | str) -> list[EvidenceChunkRecord]:
        self.init_db()
        documents = ingest_knowledge_base(Path(knowledge_dir))
        if not documents:
            return []

        source_paths = [str(Path(document.source_path).resolve()) for document in documents]
        with self._connect() as conn:
            for document in documents:
                self._upsert_document(conn, document)
        return self.list_chunks(source_paths=source_paths)

    def list_chunks(self, *, source_paths: Sequence[str] | None = None) -> list[EvidenceChunkRecord]:
        self.init_db()
        query = """
            SELECT
                c.id,
                c.document_id,
                c.source,
                d.source_path,
                c.parser,
                c.chunk_index,
                c.text,
                c.text_hash
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
        """
        params: list[str] = []
        if source_paths:
            placeholders = ",".join("?" for _ in source_paths)
            query += f" WHERE d.source_path IN ({placeholders})"
            params.extend(str(Path(path).resolve()) for path in source_paths)
        query += " ORDER BY d.source, c.chunk_index"

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [
            EvidenceChunkRecord(
                id=row["id"],
                document_id=row["document_id"],
                source=row["source"],
                source_path=row["source_path"],
                parser=row["parser"],
                chunk_index=row["chunk_index"],
                text=row["text"],
                text_hash=row["text_hash"],
            )
            for row in rows
        ]

    def get_or_create_embeddings(
        self,
        provider: DenseEmbeddingProvider,
        chunks: Sequence[EvidenceChunkRecord],
    ) -> dict[int, list[float]]:
        self.init_db()
        cached = self._get_cached_embeddings(provider.name, chunks)
        missing = [chunk for chunk in chunks if chunk.id not in cached]
        if missing:
            vectors = provider.embed_texts([chunk.text for chunk in missing])
            if len(vectors) != len(missing):
                raise ValueError("Embedding provider returned an unexpected number of vectors")
            with self._connect() as conn:
                for chunk, vector in zip(missing, vectors):
                    self._save_embedding(conn, chunk.id, provider.name, vector)
                    cached[chunk.id] = [float(item) for item in vector]
        return cached

    def counts(self) -> dict[str, int]:
        self.init_db()
        with self._connect() as conn:
            return {
                table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("documents", "document_chunks", "chunk_embeddings")
            }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _upsert_document(self, conn: sqlite3.Connection, document: ParsedDocument) -> None:
        source_path = str(Path(document.source_path).resolve())
        content_hash = _hash_text(document.markdown)
        now = datetime.now().isoformat(timespec="seconds")
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            "SELECT id, content_hash FROM documents WHERE source_path = ?",
            (source_path,),
        ).fetchone()

        if existing is None:
            cursor = conn.execute(
                """
                INSERT INTO documents (source, source_path, parser, content_hash, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (document.source, source_path, document.parser, content_hash, now),
            )
            document_id = int(cursor.lastrowid)
            self._replace_chunks(conn, document_id, document)
            return

        document_id = int(existing["id"])
        current_chunk_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM document_chunks WHERE document_id = ?",
                (document_id,),
            ).fetchone()[0]
        )
        if existing["content_hash"] == content_hash and current_chunk_count:
            return

        conn.execute(
            """
            UPDATE documents
            SET source = ?, parser = ?, content_hash = ?, updated_at = ?
            WHERE id = ?
            """,
            (document.source, document.parser, content_hash, now, document_id),
        )
        self._replace_chunks(conn, document_id, document)

    def _replace_chunks(self, conn: sqlite3.Connection, document_id: int, document: ParsedDocument) -> None:
        conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (document_id,))
        for index, text in enumerate(chunk_text(document.markdown)):
            conn.execute(
                """
                INSERT INTO document_chunks (document_id, chunk_index, text, text_hash, source, parser)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (document_id, index, text, _hash_text(text), document.source, document.parser),
            )

    def _get_cached_embeddings(
        self,
        provider_name: str,
        chunks: Sequence[EvidenceChunkRecord],
    ) -> dict[int, list[float]]:
        if not chunks:
            return {}
        chunk_ids = [chunk.id for chunk in chunks]
        placeholders = ",".join("?" for _ in chunk_ids)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                SELECT chunk_id, vector_json
                FROM chunk_embeddings
                WHERE provider_name = ? AND chunk_id IN ({placeholders})
                """,
                [provider_name, *chunk_ids],
            ).fetchall()
        return {int(row["chunk_id"]): [float(item) for item in json.loads(row["vector_json"])] for row in rows}

    def _save_embedding(
        self,
        conn: sqlite3.Connection,
        chunk_id: int,
        provider_name: str,
        vector: Sequence[float],
    ) -> None:
        values = [float(item) for item in vector]
        conn.execute(
            """
            INSERT INTO chunk_embeddings (chunk_id, provider_name, dimension, vector_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chunk_id, provider_name) DO UPDATE SET
                dimension = excluded.dimension,
                vector_json = excluded.vector_json,
                updated_at = excluded.updated_at
            """,
            (
                chunk_id,
                provider_name,
                len(values),
                json.dumps(values),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def chunk_text(
    text: str,
    *,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_hard_chunks(paragraph, max_chars=max_chars, overlap=overlap))
            continue
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def _hard_chunks(text: str, *, max_chars: int, overlap: int) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    safe_overlap = max(0, min(overlap, max_chars - 1))
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = end - safe_overlap
    return [chunk for chunk in chunks if chunk]


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
