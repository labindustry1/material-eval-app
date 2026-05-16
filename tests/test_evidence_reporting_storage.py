import tempfile
import unittest
from pathlib import Path

from material_eval.catalog import Catalog
from material_eval.computation import calculate_part
from material_eval.evidence import search_evidence
from material_eval.materials import build_single_material
from material_eval.reporting import build_internal_report
from material_eval.storage import SqliteRunRepository, list_recent_runs, save_run


class EvidenceReportingStorageTest(unittest.TestCase):
    def test_search_evidence_uses_seed_documents(self):
        cards = search_evidence("机器人 连杆 轻量化")

        self.assertTrue(cards)
        self.assertTrue(any("机器人" in card.text for card in cards))
        self.assertEqual(cards[0].retrieval_method, "bm25")
        self.assertGreater(cards[0].score, 0)

    def test_report_and_storage_round_trip(self):
        catalog = Catalog()
        part = catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        material = build_single_material(
            name="测试材料",
            category="合成蛋白/生物基大分子",
            density_g_cm3=1.3,
            tensile_strength_mpa=9600,
            elastic_modulus_gpa=100,
        )
        dimensions = {"diameter": 30, "length": 350, "thickness": 3}
        calculation = calculate_part(part, material, dimensions)
        evidence = search_evidence("机器人 连杆")
        report = build_internal_report(
            material=material,
            part=part,
            dimensions=dimensions,
            calculation=calculation,
            evidence_cards=evidence,
        )

        self.assertIn("内部研发 MVP 初筛", report.markdown)
        self.assertIn("bm25", report.markdown)
        self.assertEqual(report.filename, "测试材料-下肢大扭矩管状连杆-初筛报告.md")

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "runs.sqlite3"
            run_id = save_run(
                material_name=material.name,
                domain=part.domain,
                part_name=part.name,
                topology=part.topology,
                payload=report.report_json,
                report_markdown=report.markdown,
                db_path=db_path,
            )
            runs = list_recent_runs(db_path=db_path)
            detail = SqliteRunRepository(db_path).get_run(run_id)

        self.assertEqual(run_id, 1)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["material_name"], "测试材料")
        self.assertEqual(detail.id, run_id)
        self.assertIn("测试材料", detail.report_markdown)
        self.assertEqual(detail.payload["part"]["name"], "下肢大扭矩管状连杆")

    def test_repository_lists_runs_as_typed_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = SqliteRunRepository(Path(tmp) / "runs.sqlite3")
            run_id = repo.save_run(
                material_name="材料A",
                domain="领域A",
                part_name="零件A",
                topology="BEAM",
                payload={"ok": True},
                report_markdown="# 报告",
            )
            summaries = repo.list_recent_runs()

        self.assertEqual(run_id, 1)
        self.assertEqual(summaries[0].material_name, "材料A")
        self.assertEqual(summaries[0].topology, "BEAM")


if __name__ == "__main__":
    unittest.main()
