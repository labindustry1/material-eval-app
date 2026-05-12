import tempfile
import unittest
from pathlib import Path

from material_eval.catalog import Catalog
from material_eval.evaluation import EvaluationRequest, run_evaluation, save_evaluation
from material_eval.laminates import LaminateStack
from material_eval.materials import build_single_material
from material_eval.storage import list_recent_runs


class EvaluationWorkflowTest(unittest.TestCase):
    def test_run_evaluation_builds_complete_draft(self):
        catalog = Catalog()
        part = catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        material = build_single_material(
            name="测试材料",
            category="合成蛋白/生物基大分子",
            density_g_cm3=1.3,
            tensile_strength_mpa=9600,
            elastic_modulus_gpa=100,
        )

        draft = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions={"diameter": 30, "length": 350, "thickness": 3},
                retrieval_mode="bm25",
            )
        )

        self.assertEqual(draft.part.name, "下肢大扭矩管状连杆")
        self.assertEqual(draft.calculation.topology, "BEAM")
        self.assertTrue(draft.evidence_cards)
        self.assertIn("可行性初筛报告", draft.report.title)
        self.assertIn("内部研发 MVP 初筛", draft.report.markdown)

    def test_save_evaluation_uses_storage_boundary(self):
        catalog = Catalog()
        part = catalog.get_part("智能穿戴与柔性外骨骼", "柔性外骨骼助力带")
        material = build_single_material(
            name="测试带材",
            category="合成蛋白/生物基大分子",
            density_g_cm3=1.3,
            tensile_strength_mpa=9600,
            elastic_modulus_gpa=100,
        )
        draft = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions={"width": 40, "thickness": 2.5},
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "runs.sqlite3"
            run_id = save_evaluation(draft, db_path=db_path)
            rows = list_recent_runs(db_path=db_path)

        self.assertEqual(run_id, 1)
        self.assertEqual(rows[0]["material_name"], "测试带材")
        self.assertEqual(rows[0]["topology"], "STRAP")

    def test_run_evaluation_adds_laminate_result_to_report(self):
        catalog = Catalog()
        part = catalog.get_part("智能穿戴与柔性外骨骼", "智能穿戴承力外壳")
        material = build_single_material(
            name="测试复材",
            category="复合/杂化材料体系",
            density_g_cm3=1.4,
            tensile_strength_mpa=1200,
            elastic_modulus_gpa=70,
        )

        draft = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions={"length": 45, "width": 35, "thickness": 1.2},
                laminate_stack=LaminateStack.symmetric_cross_ply(
                    e1_gpa=135,
                    e2_gpa=10,
                    g12_gpa=5,
                    nu12=0.3,
                    ply_thickness_mm=0.125,
                ),
            )
        )

        self.assertIsNotNone(draft.laminate_result)
        self.assertIn("复合铺层初筛", draft.report.markdown)
        self.assertIn("classical-laminate-theory", draft.report.markdown)
        self.assertIn("laminate", draft.report.report_json)


class EnvelopeShortCircuitTest(unittest.TestCase):
    def _make_material(self) -> "MaterialCandidate":
        from material_eval.materials import MaterialCandidate
        from material_eval.uncertainty import Interval

        return MaterialCandidate(
            name="test",
            category="m",
            density_g_cm3=Interval.point(2.7, "g/cm^3"),
            tensile_strength_mpa=Interval.point(300, "MPa"),
            elastic_modulus_gpa=Interval.point(70, "GPa"),
        )

    def _make_part(self) -> "PartTemplate":
        from material_eval.catalog import PartTemplate

        return PartTemplate(
            domain="d",
            name="测试零件",
            topology="STRAP",
            constraint="",
            search_suffix="",
            geometry_inputs=(),
        )

    def test_out_of_envelope_returns_refusal(self):
        from material_eval.evaluation import EnvelopeRefusal, EvaluationRequest, run_evaluation
        from material_eval.conditions import Condition, Quantity
        from material_eval.uncertainty import EnvelopeSpec

        material = self._make_material()
        part = self._make_part()
        envelope = EnvelopeSpec(temperature_C=(-40, 80), source="seed")
        condition = Condition.from_dimensions(
            {"length": 1000, "width": 30, "thickness": 2},
            temperature=Quantity(value=150.0, unit="degC"),
        )
        request = EvaluationRequest(
            material=material,
            part=part,
            dimensions={"length": 1000, "width": 30, "thickness": 2},
            condition=condition,
            material_envelope=envelope,
        )
        result = run_evaluation(request)
        self.assertIsInstance(result, EnvelopeRefusal)
        self.assertEqual(len(result.envelope_report.violations), 1)
        self.assertEqual(result.envelope_report.violations[0].axis, "temperature_C")
        self.assertIn("未出具评估", result.refusal_markdown)

    def test_in_envelope_returns_normal_draft(self):
        from material_eval.evaluation import EvaluationDraft, EvaluationRequest, run_evaluation
        from material_eval.conditions import Condition, Quantity
        from material_eval.uncertainty import EnvelopeSpec

        material = self._make_material()
        part = self._make_part()
        envelope = EnvelopeSpec(temperature_C=(-40, 80), source="seed")
        condition = Condition.from_dimensions(
            {"length": 1000, "width": 30, "thickness": 2},
            temperature=Quantity(value=25.0, unit="degC"),
        )
        request = EvaluationRequest(
            material=material,
            part=part,
            dimensions={"length": 1000, "width": 30, "thickness": 2},
            condition=condition,
            material_envelope=envelope,
        )
        result = run_evaluation(request)
        self.assertIsInstance(result, EvaluationDraft)


if __name__ == "__main__":
    unittest.main()
