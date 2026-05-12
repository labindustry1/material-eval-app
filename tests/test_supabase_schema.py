import re
import unittest
from pathlib import Path


MIGRATION_DIR = Path(__file__).resolve().parents[1] / "supabase" / "migrations"


class SupabaseSchemaTest(unittest.TestCase):
    def setUp(self):
        migration_files = sorted(MIGRATION_DIR.glob("*_material_eval_core.sql"))
        self.assertTrue(migration_files, "material_eval_core migration is missing")
        self.sql = migration_files[-1].read_text(encoding="utf-8")
        self.normalized = re.sub(r"\s+", " ", self.sql.lower())

    def test_enables_private_schema_and_pgvector(self):
        self.assertIn("create schema if not exists material_eval", self.normalized)
        self.assertIn("create extension if not exists vector with schema extensions", self.normalized)
        self.assertIn("create extension if not exists pgcrypto with schema extensions", self.normalized)

    def test_creates_core_tables_aligned_with_sqlite_mvp(self):
        expected_tables = [
            "evaluation_runs",
            "documents",
            "document_chunks",
            "chunk_embeddings",
            "report_reviews",
        ]

        for table in expected_tables:
            self.assertIn(f"create table if not exists material_eval.{table}", self.normalized)

        self.assertIn("payload_json jsonb not null", self.normalized)
        self.assertIn("content_hash text not null", self.normalized)
        self.assertIn("chunk_index integer not null", self.normalized)
        self.assertIn("embedding extensions.vector(1024) not null", self.normalized)
        self.assertIn("unique (chunk_id, provider_name, model_name)", self.normalized)

    def test_enables_rls_without_public_api_grants(self):
        for table in ["evaluation_runs", "documents", "document_chunks", "chunk_embeddings", "report_reviews"]:
            self.assertIn(f"alter table material_eval.{table} enable row level security", self.normalized)

        self.assertNotIn("grant all on schema material_eval to anon", self.normalized)
        self.assertNotIn("grant all on schema material_eval to authenticated", self.normalized)

    def test_indexes_vector_search_and_common_filters(self):
        self.assertIn("document_chunks_document_id_idx", self.normalized)
        self.assertIn("documents_source_path_idx", self.normalized)
        self.assertIn("chunk_embeddings_chunk_id_provider_idx", self.normalized)
        self.assertIn("report_reviews_run_id_idx", self.normalized)
        self.assertIn("using hnsw (embedding extensions.vector_cosine_ops)", self.normalized)

    def test_match_document_chunks_rpc_uses_cosine_distance(self):
        self.assertIn("create or replace function material_eval.match_document_chunks", self.normalized)
        self.assertIn("query_embedding extensions.vector(1024)", self.normalized)
        self.assertIn("1 - (ce.embedding <=> query_embedding)", self.normalized)
        self.assertIn("order by ce.embedding <=> query_embedding", self.normalized)


if __name__ == "__main__":
    unittest.main()
