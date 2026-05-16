import unittest

from material_eval.catalog import Catalog
from material_eval.evaluation import EvaluationRequest, run_evaluation
from material_eval.materials import build_single_material


class ReportSchemaTest(unittest.TestCase):
    def test_report_contains_structured_claims_with_bindings(self):
        catalog = Catalog()
        part = catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        material = build_single_material(
            name="结构化报告测试材料",
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
            )
        )

        structured = draft.report.structured_report

        self.assertGreaterEqual(len(structured.claims), 3)
        self.assertEqual(len({claim.claim_id for claim in structured.claims}), len(structured.claims))
        for claim in structured.claims:
            self.assertGreaterEqual(claim.confidence, 0)
            self.assertLessEqual(claim.confidence, 1)
            self.assertTrue(claim.bindings)

        source_types = {binding.source_type for claim in structured.claims for binding in claim.bindings}
        self.assertIn("calculation_metric", source_types)
        self.assertIn("evidence_card", source_types)
        self.assertIn("manual_judgement", source_types)

    def test_report_json_and_markdown_include_claim_traceability(self):
        catalog = Catalog()
        part = catalog.get_part("智能穿戴与柔性外骨骼", "柔性外骨骼助力带")
        material = build_single_material(
            name="claim JSON 测试材料",
            category="合成蛋白/生物基大分子",
            density_g_cm3=1.25,
            tensile_strength_mpa=5200,
            elastic_modulus_gpa=85,
        )

        draft = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions={"width": 40, "thickness": 2.5},
            )
        )

        self.assertIn("structured_report", draft.report.report_json)
        self.assertGreaterEqual(len(draft.report.report_json["structured_report"]["claims"]), 3)
        self.assertIn("结构化结论追踪", draft.report.markdown)


class IntervalPayloadTest(unittest.TestCase):
    def test_roundtrip_from_interval(self):
        from material_eval.uncertainty import Interval
        from material_eval.report_schema import IntervalPayload
        iv = Interval(low=1.0, typical=2.0, high=3.0, unit="MPa")
        p = IntervalPayload.from_interval(iv)
        self.assertEqual(p.low, 1.0)
        self.assertEqual(p.typical, 2.0)
        self.assertEqual(p.high, 3.0)
        self.assertEqual(p.unit, "MPa")
        self.assertFalse(p.widened)


class EnvelopeReportPayloadTest(unittest.TestCase):
    def test_from_report_with_violations(self):
        from material_eval.uncertainty import EnvelopeReport, Violation
        from material_eval.report_schema import EnvelopeReportPayload
        r = EnvelopeReport(
            violations=(Violation(axis="temperature_C", input_value=150.0,
                                  allowed_range=(-40.0, 120.0), source="seed"),),
            has_declared_envelope=True,
        )
        p = EnvelopeReportPayload.from_report(r)
        self.assertTrue(p.has_declared_envelope)
        self.assertEqual(len(p.violations), 1)
        self.assertEqual(p.violations[0].axis, "temperature_C")
        self.assertEqual(p.violations[0].allowed_low, -40.0)
        self.assertEqual(p.violations[0].allowed_high, 120.0)
        self.assertEqual(p.violations[0].source, "seed")


if __name__ == "__main__":
    unittest.main()
