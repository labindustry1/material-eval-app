"""End-to-end smoke tests covering MVP 3 scenarios × in/out-of-envelope paths.

Scenarios
---------
1. 人形机器人核心骨架 / 下肢大扭矩管状连杆 (BEAM)  + ti_6al_4v
2. 智能穿戴与柔性外骨骼 / 智能穿戴承力外壳 (PLATE) + pa66_gf30
3. 智能穿戴与柔性外骨骼 / 柔性外骨骼助力带 (STRAP) + kevlar_aramid_fiber

Each scenario exercises one in-envelope case (expects EvaluationDraft) and one
out-of-envelope case (expects EnvelopeRefusal with the correct violated axis).
"""
from __future__ import annotations

import unittest

from material_eval.catalog import Catalog
from material_eval.conditions import Condition, Quantity
from material_eval.evaluation import (
    EnvelopeRefusal,
    EvaluationDraft,
    EvaluationRequest,
    run_evaluation,
)
from material_eval.material_property_library import MaterialPropertyLibrary


class Phase1SmokeTest(unittest.TestCase):
    """End-to-end smoke covering MVP 3 scenarios × in/out-of-envelope paths."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.lib = MaterialPropertyLibrary()
        cls.catalog = Catalog()

    # ------------------------------------------------------------------
    # Scenario 1: humanoid skeleton tubular link + Ti-6Al-4V
    # Envelope: temperature_C [-200, 400], thickness_mm [0.5, 200]
    # ------------------------------------------------------------------

    def test_humanoid_skeleton_titanium_in_envelope(self) -> None:
        material = self.lib.build_candidate("ti_6al_4v")
        envelope = self.lib.envelope_for("ti_6al_4v")
        part = self.catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        dims = {"length": 250.0, "diameter": 40.0, "thickness": 3.0}
        condition = Condition.from_dimensions(dims, temperature=Quantity(value=25.0, unit="degC"))
        result = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions=dims,
                condition=condition,
                material_envelope=envelope,
            )
        )
        self.assertIsInstance(result, EvaluationDraft)
        # Markdown must include envelope and uncertainty sections
        self.assertIn("工况包络校验", result.report.markdown)
        self.assertIn("不确定度说明", result.report.markdown)
        # All metric intervals must satisfy low <= typical <= high
        for m in result.calculation.metrics:
            self.assertGreaterEqual(m.value.high, m.value.low)
            self.assertGreaterEqual(m.value.high, m.value.typical)
            self.assertLessEqual(m.value.low, m.value.typical)

    def test_humanoid_skeleton_titanium_out_of_envelope_temperature(self) -> None:
        material = self.lib.build_candidate("ti_6al_4v")
        envelope = self.lib.envelope_for("ti_6al_4v")
        # ti_6al_4v envelope.temperature_C is [-200, 400]; pick 500 to exceed
        part = self.catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        dims = {"length": 250.0, "diameter": 40.0, "thickness": 3.0}
        condition = Condition.from_dimensions(dims, temperature=Quantity(value=500.0, unit="degC"))
        result = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions=dims,
                condition=condition,
                material_envelope=envelope,
            )
        )
        self.assertIsInstance(result, EnvelopeRefusal)
        self.assertTrue(
            any(v.axis == "temperature_C" for v in result.envelope_report.violations)
        )
        self.assertIn("未出具评估", result.refusal_markdown)

    # ------------------------------------------------------------------
    # Scenario 2: wearable shell + PA66-GF30
    # Envelope: temperature_C [-30, 120], thickness_mm [0.5, 20]
    # ------------------------------------------------------------------

    def test_wearable_shell_pa66_in_envelope(self) -> None:
        material = self.lib.build_candidate("pa66_gf30")
        envelope = self.lib.envelope_for("pa66_gf30")
        part = self.catalog.get_part("智能穿戴与柔性外骨骼", "智能穿戴承力外壳")
        dims = {"length": 45.0, "width": 35.0, "thickness": 1.2}
        condition = Condition.from_dimensions(dims, temperature=Quantity(value=40.0, unit="degC"))
        result = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions=dims,
                condition=condition,
                material_envelope=envelope,
            )
        )
        self.assertIsInstance(result, EvaluationDraft)
        for m in result.calculation.metrics:
            self.assertGreaterEqual(m.value.high, m.value.low)

    def test_wearable_shell_pa66_out_of_envelope_high_temperature(self) -> None:
        material = self.lib.build_candidate("pa66_gf30")
        envelope = self.lib.envelope_for("pa66_gf30")
        # pa66_gf30 envelope.temperature_C is [-30, 120]; pick 150 to exceed
        part = self.catalog.get_part("智能穿戴与柔性外骨骼", "智能穿戴承力外壳")
        dims = {"length": 45.0, "width": 35.0, "thickness": 1.2}
        condition = Condition.from_dimensions(dims, temperature=Quantity(value=150.0, unit="degC"))
        result = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions=dims,
                condition=condition,
                material_envelope=envelope,
            )
        )
        self.assertIsInstance(result, EnvelopeRefusal)
        self.assertTrue(
            any(v.axis == "temperature_C" for v in result.envelope_report.violations)
        )
        self.assertIn("未出具评估", result.refusal_markdown)

    # ------------------------------------------------------------------
    # Scenario 3: flexible exoskeleton strap + Kevlar aramid fiber
    # Envelope: temperature_C [-40, 180], thickness_mm [0.05, 5]
    # ------------------------------------------------------------------

    def test_strap_kevlar_in_envelope(self) -> None:
        material = self.lib.build_candidate("kevlar_aramid_fiber")
        envelope = self.lib.envelope_for("kevlar_aramid_fiber")
        part = self.catalog.get_part("智能穿戴与柔性外骨骼", "柔性外骨骼助力带")
        # STRAP geometry: width + thickness; length defaults to 1000 mm in calculator
        dims = {"width": 40.0, "thickness": 2.5}
        condition = Condition.from_dimensions(dims, temperature=Quantity(value=25.0, unit="degC"))
        result = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions=dims,
                condition=condition,
                material_envelope=envelope,
            )
        )
        self.assertIsInstance(result, EvaluationDraft)
        for m in result.calculation.metrics:
            self.assertGreaterEqual(m.value.high, m.value.low)

    def test_strap_kevlar_out_of_envelope_thickness(self) -> None:
        material = self.lib.build_candidate("kevlar_aramid_fiber")
        envelope = self.lib.envelope_for("kevlar_aramid_fiber")
        # kevlar_aramid_fiber envelope.thickness_mm is [0.05, 5]; pick 10 to exceed
        part = self.catalog.get_part("智能穿戴与柔性外骨骼", "柔性外骨骼助力带")
        dims = {"width": 40.0, "thickness": 10.0}
        condition = Condition.from_dimensions(dims, temperature=Quantity(value=25.0, unit="degC"))
        result = run_evaluation(
            EvaluationRequest(
                material=material,
                part=part,
                dimensions=dims,
                condition=condition,
                material_envelope=envelope,
            )
        )
        self.assertIsInstance(result, EnvelopeRefusal)
        self.assertTrue(
            any(v.axis == "thickness_mm" for v in result.envelope_report.violations)
        )
        self.assertIn("未出具评估", result.refusal_markdown)


if __name__ == "__main__":
    unittest.main()
