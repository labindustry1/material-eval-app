import tempfile
import unittest
from pathlib import Path

from material_eval.storage import SqliteRunRepository


class ReviewWorkflowTest(unittest.TestCase):
    def test_repository_saves_and_lists_report_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteRunRepository(Path(tmp) / "runs.sqlite3")
            run_id = repo.save_run(
                material_name="材料A",
                domain="机器人",
                part_name="连杆",
                topology="BEAM",
                payload={"ok": True},
                report_markdown="# 报告",
            )

            review_id = repo.save_review(
                run_id=run_id,
                reviewer="研发负责人",
                status="needs_experiment",
                comment="需要补充疲劳实验。",
            )
            reviews = repo.list_reviews(run_id)

        self.assertEqual(review_id, 1)
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].status, "needs_experiment")
        self.assertEqual(reviews[0].comment, "需要补充疲劳实验。")


if __name__ == "__main__":
    unittest.main()
