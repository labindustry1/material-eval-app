import unittest

from material_eval.evidence import EvidenceCard
from material_eval.rag_eval import RetrievalQuestion, default_retrieval_questions, run_retrieval_evaluation


class RagEvaluationTest(unittest.TestCase):
    def test_retrieval_evaluation_reports_hit_rate_and_method_counts(self):
        def fake_search(query, limit=4):
            if "机器人" in query:
                return [
                    EvidenceCard(
                        source="人形机器人关节连杆减重白皮书.txt",
                        text="机器人关节连杆需要轻量化。",
                        score=1.0,
                        retrieval_method="bm25",
                    )
                ]
            return [
                EvidenceCard(
                    source="军工装甲材料准入标准_2025.txt",
                    text="装甲材料需要准入验证。",
                    score=0.8,
                    retrieval_method="bge-m3+dense",
                )
            ]

        result = run_retrieval_evaluation(
            [
                RetrievalQuestion(query="机器人 连杆", expected_sources=("人形机器人关节连杆减重白皮书.txt",)),
                RetrievalQuestion(query="装甲 准入", expected_sources=("军工装甲材料准入标准_2025.txt",)),
            ],
            search_fn=fake_search,
        )

        self.assertEqual(result.total_questions, 2)
        self.assertEqual(result.hit_rate, 1.0)
        self.assertEqual(result.method_counts, {"bm25": 1, "bge-m3+dense": 1})
        self.assertTrue(all(item.hit for item in result.items))

    def test_default_retrieval_questions_run_against_seed_knowledge_base(self):
        result = run_retrieval_evaluation(default_retrieval_questions())

        self.assertGreaterEqual(result.total_questions, 3)
        self.assertGreater(result.hit_rate, 0)
        self.assertTrue(result.method_counts)


if __name__ == "__main__":
    unittest.main()
