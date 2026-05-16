import math
import tempfile
import unittest
from pathlib import Path

from material_eval.embeddings import BgeM3DenseEmbeddingProvider, cosine_similarity
from material_eval.evidence import search_evidence


class FakeBgeM3Model:
    def __init__(self):
        self.calls = []

    def encode(self, texts, *, batch_size, max_length):
        self.calls.append({"texts": list(texts), "batch_size": batch_size, "max_length": max_length})
        vectors = []
        for text in texts:
            if "机器人" in text:
                vectors.append([1.0, 0.0, 0.0])
            elif "装甲" in text:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return {"dense_vecs": vectors}


class BrokenEmbeddingProvider:
    name = "bge-m3+dense"

    def embed_texts(self, texts):
        raise OSError("model cache is unavailable")


class EmbeddingTest(unittest.TestCase):
    def test_bge_m3_provider_adapts_dense_vectors(self):
        model = FakeBgeM3Model()
        provider = BgeM3DenseEmbeddingProvider(model=model, batch_size=2, max_length=128)

        vectors = provider.embed_texts(["机器人 连杆", "装甲 材料"])

        self.assertEqual(vectors, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        self.assertEqual(model.calls[0]["batch_size"], 2)
        self.assertEqual(model.calls[0]["max_length"], 128)

    def test_cosine_similarity_handles_zero_vectors(self):
        self.assertEqual(cosine_similarity([0, 0], [1, 0]), 0.0)
        self.assertAlmostEqual(cosine_similarity([1, 1], [1, 1]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_search_evidence_can_use_bge_m3_dense_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            (knowledge_dir / "robot.txt").write_text("机器人关节连杆需要轻量化和高比强度。", encoding="utf-8")
            (knowledge_dir / "armor.txt").write_text("装甲材料关注抗冲击和准入验证。", encoding="utf-8")

            cards = search_evidence(
                "机器人 连杆",
                knowledge_dir=knowledge_dir,
                evidence_db_path=Path(tmp) / "evidence.sqlite3",
                retrieval_mode="embedding",
                embedding_provider=BgeM3DenseEmbeddingProvider(model=FakeBgeM3Model()),
            )

        self.assertEqual(cards[0].source, "robot.txt")
        self.assertEqual(cards[0].retrieval_method, "bge-m3+dense")
        self.assertTrue(math.isclose(cards[0].score, 1.0))

    def test_embedding_mode_falls_back_when_model_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            knowledge_dir = Path(tmp)
            (knowledge_dir / "robot.txt").write_text("机器人关节连杆需要轻量化和高比强度。", encoding="utf-8")
            (knowledge_dir / "armor.txt").write_text("装甲材料关注抗冲击和准入验证。", encoding="utf-8")

            cards = search_evidence(
                "机器人 连杆",
                knowledge_dir=knowledge_dir,
                evidence_db_path=Path(tmp) / "evidence.sqlite3",
                retrieval_mode="embedding",
                embedding_provider=BrokenEmbeddingProvider(),
            )

        self.assertTrue(cards)
        self.assertIn(cards[0].retrieval_method, {"bm25", "keyword", "fallback"})


if __name__ == "__main__":
    unittest.main()
