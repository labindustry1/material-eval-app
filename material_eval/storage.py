from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "mvp.sqlite3"


@dataclass(frozen=True)
class EvaluationRunSummary:
    id: int
    created_at: str
    material_name: str
    domain: str
    part_name: str
    topology: str


@dataclass(frozen=True)
class EvaluationRunDetail(EvaluationRunSummary):
    payload: dict[str, Any]
    report_markdown: str


@dataclass(frozen=True)
class ReportReview:
    id: int
    run_id: int
    created_at: str
    reviewer: str
    status: str
    comment: str


class RunRepository(Protocol):
    def save_run(
        self,
        *,
        material_name: str,
        domain: str,
        part_name: str,
        topology: str,
        payload: dict[str, Any],
        report_markdown: str,
    ) -> int:
        ...

    def list_recent_runs(self, limit: int = 8) -> list[EvaluationRunSummary]:
        ...

    def get_run(self, run_id: int) -> EvaluationRunDetail:
        ...


class SqliteRunRepository:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    material_name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    part_name TEXT NOT NULL,
                    topology TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    report_markdown TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS report_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    status TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES evaluation_runs(id) ON DELETE CASCADE
                )
                """
            )

    def save_run(
        self,
        *,
        material_name: str,
        domain: str,
        part_name: str,
        topology: str,
        payload: dict[str, Any],
        report_markdown: str,
    ) -> int:
        self.init_db()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO evaluation_runs
                    (created_at, material_name, domain, part_name, topology, payload_json, report_markdown)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    material_name,
                    domain,
                    part_name,
                    topology,
                    json.dumps(payload, ensure_ascii=False),
                    report_markdown,
                ),
            )
            return int(cursor.lastrowid)

    def list_recent_runs(self, limit: int = 8) -> list[EvaluationRunSummary]:
        self.init_db()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, created_at, material_name, domain, part_name, topology
                FROM evaluation_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [
                EvaluationRunSummary(
                    id=row["id"],
                    created_at=row["created_at"],
                    material_name=row["material_name"],
                    domain=row["domain"],
                    part_name=row["part_name"],
                    topology=row["topology"],
                )
                for row in rows
            ]

    def get_run(self, run_id: int) -> EvaluationRunDetail:
        self.init_db()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT id, created_at, material_name, domain, part_name, topology, payload_json, report_markdown
                FROM evaluation_runs
                WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Evaluation run not found: {run_id}")
        return EvaluationRunDetail(
            id=row["id"],
            created_at=row["created_at"],
            material_name=row["material_name"],
            domain=row["domain"],
            part_name=row["part_name"],
            topology=row["topology"],
            payload=json.loads(row["payload_json"]),
            report_markdown=row["report_markdown"],
        )

    def save_review(self, *, run_id: int, reviewer: str, status: str, comment: str) -> int:
        self.init_db()
        with sqlite3.connect(self.db_path) as conn:
            exists = conn.execute("SELECT 1 FROM evaluation_runs WHERE id = ?", (run_id,)).fetchone()
            if exists is None:
                raise KeyError(f"Evaluation run not found: {run_id}")
            cursor = conn.execute(
                """
                INSERT INTO report_reviews (run_id, created_at, reviewer, status, comment)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    datetime.now().isoformat(timespec="seconds"),
                    reviewer.strip() or "未命名复核人",
                    status.strip() or "needs_review",
                    comment.strip(),
                ),
            )
            return int(cursor.lastrowid)

    def list_reviews(self, run_id: int) -> list[ReportReview]:
        self.init_db()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT id, run_id, created_at, reviewer, status, comment
                FROM report_reviews
                WHERE run_id = ?
                ORDER BY id DESC
                """,
                (run_id,),
            ).fetchall()
        return [
            ReportReview(
                id=row["id"],
                run_id=row["run_id"],
                created_at=row["created_at"],
                reviewer=row["reviewer"],
                status=row["status"],
                comment=row["comment"],
            )
            for row in rows
        ]


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    SqliteRunRepository(db_path).init_db()


def save_run(
    *,
    material_name: str,
    domain: str,
    part_name: str,
    topology: str,
    payload: dict[str, Any],
    report_markdown: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int:
    return SqliteRunRepository(db_path).save_run(
        material_name=material_name,
        domain=domain,
        part_name=part_name,
        topology=topology,
        payload=payload,
        report_markdown=report_markdown,
    )


def list_recent_runs(limit: int = 8, db_path: Path | str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    return [summary.__dict__ for summary in SqliteRunRepository(db_path).list_recent_runs(limit)]


def save_report_review(
    *,
    run_id: int,
    reviewer: str,
    status: str,
    comment: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> int:
    return SqliteRunRepository(db_path).save_review(
        run_id=run_id,
        reviewer=reviewer,
        status=status,
        comment=comment,
    )


def list_report_reviews(run_id: int, db_path: Path | str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    return [review.__dict__ for review in SqliteRunRepository(db_path).list_reviews(run_id)]
