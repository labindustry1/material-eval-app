import tempfile
import unittest
from pathlib import Path

from material_eval.evidence import search_evidence
from material_eval.evidence_store import SqliteEvidenceRepository, chunk_text


class CountingEmbeddingProvider:
    name = "bge-m3+dense"

    def __init__(self):
        self.calls = []

    def embed_texts(self, texts):
        batch = list(texts)
        self.calls.append(batch)
        vectors = []
        for text in batch:
            if "机器人" in text:
                vectors.append([1.0, 0.0, 0.0])
            elif "装甲" in text:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


class EvidenceStoreTest(unittest.TestCase):
    def test_chunk_text_preserves_short_documents(self):
        chunks = chunk_text("机器人连杆需要轻量化。\n\n高比强度是关键。", max_chars=100)

        self.assertEqual(chunks, ["机器人连杆需要轻量化。\n\n高比强度是关键。"])

    def test_repository_syncs_documents_chunks_and_reuses_embeddings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            knowledge_dir = root / "kb"
            knowledge_dir.mkdir()
            (knowledge_dir / "robot.txt").write_text("机器人连杆需要轻量化和高比强度。", encoding="utf-8")
            (knowledge_dir / "armor.txt").write_text("装甲材料关注抗冲击和准入验证。", encoding="utf-8")
            repo = SqliteEvidenceRepository(root / "evidence.sqlite3")

            chunks = repo.sync_knowledge_base(knowledge_dir)
            provider = CountingEmbeddingProvider()
            first_vectors = repo.get_or_create_embeddings(provider, chunks)
            second_vectors = repo.get_or_create_embeddings(provider, chunks)
            counts = repo.counts()

        self.assertEqual(counts, {"documents": 2, "document_chunks": 2, "chunk_embeddings": 2})
        self.assertEqual(len(chunks), 2)
        self.assertEqual(first_vectors, second_vectors)
        self.assertEqual(len(provider.calls), 1)

    def test_search_evidence_uses_sqlite_chunk_store_for_bm25(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            knowledge_dir = root / "kb"
            knowledge_dir.mkdir()
            db_path = root / "evidence.sqlite3"
            (knowledge_dir / "robot.txt").write_text("机器人关节连杆需要轻量化和高比强度。", encoding="utf-8")
            (knowledge_dir / "armor.txt").write_text("装甲材料关注抗冲击和准入验证。", encoding="utf-8")

            cards = search_evidence("机器人 连杆", knowledge_dir=knowledge_dir, evidence_db_path=db_path)
            repo = SqliteEvidenceRepository(db_path)
            chunk_count = repo.counts()["document_chunks"]

        self.assertEqual(cards[0].source, "robot.txt")
        self.assertEqual(cards[0].retrieval_method, "bm25")
        self.assertEqual(chunk_count, 2)

    def test_embedding_search_reuses_cached_chunk_embeddings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            knowledge_dir = root / "kb"
            knowledge_dir.mkdir()
            db_path = root / "evidence.sqlite3"
            (knowledge_dir / "robot.txt").write_text("机器人关节连杆需要轻量化和高比强度。", encoding="utf-8")
            (knowledge_dir / "armor.txt").write_text("装甲材料关注抗冲击和准入验证。", encoding="utf-8")
            provider = CountingEmbeddingProvider()

            first = search_evidence(
                "机器人 连杆",
                knowledge_dir=knowledge_dir,
                evidence_db_path=db_path,
                retrieval_mode="embedding",
                embedding_provider=provider,
            )
            second = search_evidence(
                "机器人 连杆",
                knowledge_dir=knowledge_dir,
                evidence_db_path=db_path,
                retrieval_mode="embedding",
                embedding_provider=provider,
            )

        self.assertEqual(first[0].retrieval_method, "bge-m3+dense")
        self.assertEqual(second[0].source, first[0].source)
        self.assertEqual(len(provider.calls), 3)
        self.assertEqual(provider.calls[0], ["机器人 连杆"])
        self.assertCountEqual(provider.calls[1], ["机器人关节连杆需要轻量化和高比强度。", "装甲材料关注抗冲击和准入验证。"])
        self.assertEqual(provider.calls[2], ["机器人 连杆"])


if __name__ == "__main__":
    unittest.main()
