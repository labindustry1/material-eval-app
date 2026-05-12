import unittest

from material_eval.catalog import Catalog
from material_eval.evaluation import EvaluationRequest, run_evaluation
from material_eval.materials import build_single_material
from material_eval.scoring import build_scorecard


class ScoringTest(unittest.TestCase):
    def test_scorecard_has_required_dimensions_and_weighted_total(self):
        catalog = Catalog()
        part = catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        material = build_single_material(
            name="评分测试材料",
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

        scorecard = draft.report.scorecard

        dimension_ids = {dimension.dimension_id for dimension in scorecard.dimensions}
        self.assertEqual(
            dimension_ids,
            {
                "data_confidence",
                "intrinsic_performance",
                "structural_fit",
                "operating_risk",
                "process_maturity",
                "compliance_risk",
            },
        )
        self.assertAlmostEqual(sum(dimension.weight for dimension in scorecard.dimensions), 1.0, places=6)
        self.assertGreaterEqual(scorecard.total_score, 0)
        self.assertLessEqual(scorecard.total_score, 100)
        for dimension in scorecard.dimensions:
            self.assertGreaterEqual(dimension.score, 0)
            self.assertLessEqual(dimension.score, 100)
            self.assertTrue(dimension.rationale)

    def test_operating_risk_score_drops_when_calculation_has_warnings(self):
        catalog = Catalog()
        material = build_single_material(
            name="风险测试材料",
            category="合成蛋白/生物基大分子",
            density_g_cm3=1.3,
            tensile_strength_mpa=9600,
            elastic_modulus_gpa=100,
        )
        beam_part = catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        strap_part = catalog.get_part("智能穿戴与柔性外骨骼", "柔性外骨骼助力带")

        beam_draft = run_evaluation(
            EvaluationRequest(
                material=material,
                part=beam_part,
                dimensions={"diameter": 30, "length": 350, "thickness": 3},
            )
        )
        strap_draft = run_evaluation(
            EvaluationRequest(
                material=material,
                part=strap_part,
                dimensions={"width": 40, "thickness": 2.5},
            )
        )

        beam_scorecard = build_scorecard(
            material=beam_draft.material,
            part=beam_draft.part,
            calculation=beam_draft.calculation,
            evidence_cards=beam_draft.evidence_cards,
            risks=beam_draft.report.report_json["risks"],
        )
        strap_scorecard = build_scorecard(
            material=strap_draft.material,
            part=strap_draft.part,
            calculation=strap_draft.calculation,
            evidence_cards=strap_draft.evidence_cards,
            risks=strap_draft.report.report_json["risks"],
        )

        self.assertLess(
            strap_scorecard.dimension("operating_risk").score,
            beam_scorecard.dimension("operating_risk").score,
        )

    def test_report_json_and_markdown_include_scorecard(self):
        catalog = Catalog()
        part = catalog.get_part("智能穿戴与柔性外骨骼", "智能穿戴承力外壳")
        material = build_single_material(
            name="报告评分测试材料",
            category="特种工程塑料",
            density_g_cm3=1.4,
            tensile_strength_mpa=220,
            elastic_modulus_gpa=18,
        )

        draft = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions={"length": 45, "width": 35, "thickness": 1.2},
            )
        )

        self.assertIn("scorecard", draft.report.report_json)
        self.assertIn("透明评分卡", draft.report.markdown)


class DataConfidenceScoreTest(unittest.TestCase):
    def test_narrow_interval_high_score(self):
        from material_eval.scoring import score_data_confidence
        from material_eval.uncertainty import Interval
        ivs = [Interval(low=99, typical=100, high=101, unit="MPa")]
        self.assertGreaterEqual(score_data_confidence(ivs), 0.9)

    def test_wide_interval_low_score(self):
        from material_eval.scoring import score_data_confidence
        from material_eval.uncertainty import Interval
        ivs = [Interval(low=10, typical=50, high=200, unit="MPa")]
        self.assertLessEqual(score_data_confidence(ivs), 0.2)

    def test_empty_returns_neutral(self):
        from material_eval.scoring import score_data_confidence
        self.assertAlmostEqual(score_data_confidence([]), 0.5)


class ConditionRiskScoreTest(unittest.TestCase):
    def _stub(self, **kwargs):
        class C:
            def envelope_axes(self):
                base = {k: None for k in
                        ("temperature_C","humidity_pct","stress_MPa",
                         "strain_rate_1_per_s","fatigue_cycles","thickness_mm")}
                base.update(kwargs); return base
        return C()

    def test_far_from_boundary_high(self):
        from material_eval.scoring import score_condition_risk
        from material_eval.uncertainty import EnvelopeSpec
        env = EnvelopeSpec(temperature_C=(-40.0, 120.0))
        self.assertGreaterEqual(score_condition_risk(env, self._stub(temperature_C=25.0)), 0.9)

    def test_near_boundary_low(self):
        from material_eval.scoring import score_condition_risk
        from material_eval.uncertainty import EnvelopeSpec
        env = EnvelopeSpec(temperature_C=(-40.0, 120.0))
        self.assertLessEqual(score_condition_risk(env, self._stub(temperature_C=118.0)), 0.4)

    def test_undeclared_envelope_neutral(self):
        from material_eval.scoring import score_condition_risk
        from material_eval.uncertainty import EnvelopeSpec
        self.assertAlmostEqual(score_condition_risk(EnvelopeSpec(), self._stub(temperature_C=25.0)), 0.5)


if __name__ == "__main__":
    unittest.main()
