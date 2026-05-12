import unittest

from material_eval.catalog import Catalog
from material_eval.conditions import Condition, Quantity
from material_eval.evaluation import EvaluationDraft, EvaluationRequest, run_evaluation
from material_eval.material_property_library import MaterialPropertyLibrary
from material_eval.laminates import Lamina, LaminateStack


class Phase2SafetySmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = MaterialPropertyLibrary()
        cls.catalog = Catalog()

    def _part(self, domain_name: str, part_name: str):
        return self.catalog.get_part(domain_name, part_name)

    def test_humanoid_skeleton_ti6al4v_with_axial_and_bending(self):
        """Ti-6Al-4V BEAM + axial=10kN + bending=50 N·m → von Mises with yield → SafetyReport non-empty."""
        material = self.lib.build_candidate("ti_6al_4v")
        envelope = self.lib.envelope_for("ti_6al_4v")
        allowables = self.lib.allowables_for("ti_6al_4v")
        part = self._part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        condition = Condition.from_dimensions(
            {"length": 250.0, "diameter": 40.0, "thickness": 3.0},
            temperature=Quantity(value=25.0, unit="degC"),
            axial_force=Quantity(value=10.0, unit="kN"),
            bending_moment=Quantity(value=50.0, unit="N*m"),
        )
        result = run_evaluation(EvaluationRequest(
            material=material, part=part,
            dimensions={"length": 250.0, "diameter": 40.0, "thickness": 3.0},
            condition=condition,
            material_envelope=envelope,
            strength_allowables=allowables,
            material_id="ti_6al_4v",
        ))
        self.assertIsInstance(result, EvaluationDraft)
        self.assertIsNotNone(result.safety_report)
        self.assertEqual(result.safety_report.method, "von_mises")
        # Should pass for these loads (Ti-6Al-4V is strong)
        self.assertIn(result.safety_report.status, ("pass", "marginal"))

    def test_wearable_shell_pa66_with_membrane_load(self):
        """PA66-GF30 PLATE + axial=2kN + bending=10 N·m → von Mises with yield."""
        material = self.lib.build_candidate("pa66_gf30")
        envelope = self.lib.envelope_for("pa66_gf30")
        allowables = self.lib.allowables_for("pa66_gf30")
        part = self._part("智能穿戴与柔性外骨骼", "智能穿戴承力外壳")
        condition = Condition.from_dimensions(
            {"length": 150.0, "width": 80.0, "thickness": 3.0},
            temperature=Quantity(value=40.0, unit="degC"),
            axial_force=Quantity(value=2.0, unit="kN"),
            bending_moment=Quantity(value=10.0, unit="N*m"),
        )
        result = run_evaluation(EvaluationRequest(
            material=material, part=part,
            dimensions={"length": 150.0, "width": 80.0, "thickness": 3.0},
            condition=condition,
            material_envelope=envelope,
            strength_allowables=allowables,
            material_id="pa66_gf30",
        ))
        self.assertIsInstance(result, EvaluationDraft)
        self.assertIsNotNone(result.safety_report)
        self.assertEqual(result.safety_report.method, "von_mises")
        self.assertTrue(len(result.safety_report.factors) >= 1)

    def test_kevlar_strap_fallback_to_tensile_strength(self):
        """Kevlar strap with no strength_allowables → fallback to material.tensile_strength_mpa,
        but evaluation should skip safety analysis entirely (allowables=None).
        Verifies graceful degradation."""
        material = self.lib.build_candidate("kevlar_aramid_fiber")
        envelope = self.lib.envelope_for("kevlar_aramid_fiber")
        allowables = self.lib.allowables_for("kevlar_aramid_fiber")  # → None
        self.assertIsNone(allowables, "Kevlar should not have strength_allowables in seed")
        part = self._part("智能穿戴与柔性外骨骼", "柔性外骨骼助力带")
        condition = Condition.from_dimensions(
            {"width": 40.0, "thickness": 1.5},
            temperature=Quantity(value=25.0, unit="degC"),
            axial_force=Quantity(value=5.0, unit="kN"),
        )
        result = run_evaluation(EvaluationRequest(
            material=material, part=part,
            dimensions={"width": 40.0, "thickness": 1.5},
            condition=condition,
            material_envelope=envelope,
            strength_allowables=None,
            material_id="kevlar_aramid_fiber",
        ))
        self.assertIsInstance(result, EvaluationDraft)
        # Kevlar 没有 strength_allowables → safety_report 应为 None（向后兼容路径）
        self.assertIsNone(result.safety_report)

    def test_carbon_epoxy_laminate_tsai_wu(self):
        """Carbon-Epoxy 4-ply [0/90/90/0] + axial=1kN → Tsai-Wu per ply."""
        material = self.lib.build_candidate("carbon_epoxy_quasi_iso")
        allowables = self.lib.allowables_for("carbon_epoxy_quasi_iso")
        self.assertIsNotNone(allowables, "carbon_epoxy_quasi_iso should have orthotropic allowables")
        self.assertTrue(allowables.has_orthotropic())

        # Build a quasi-iso laminate stack from a known ply property set
        # (CLT-based tests in test_laminates already cover the math; here just need any valid stack)
        stack = LaminateStack(plies=(
            Lamina(e1_gpa=140, e2_gpa=10, g12_gpa=5, nu12=0.3, thickness_mm=0.125, angle_deg=0),
            Lamina(e1_gpa=140, e2_gpa=10, g12_gpa=5, nu12=0.3, thickness_mm=0.125, angle_deg=90),
            Lamina(e1_gpa=140, e2_gpa=10, g12_gpa=5, nu12=0.3, thickness_mm=0.125, angle_deg=90),
            Lamina(e1_gpa=140, e2_gpa=10, g12_gpa=5, nu12=0.3, thickness_mm=0.125, angle_deg=0),
        ))
        # Use the same part as humanoid skeleton (any BEAM-like part) — laminate_stack overrides isotropic path
        part = self._part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        condition = Condition.from_dimensions(
            {"length": 250.0, "diameter": 40.0, "thickness": 3.0, "width": 30.0},
            temperature=Quantity(value=25.0, unit="degC"),
            axial_force=Quantity(value=1.0, unit="kN"),
        )
        result = run_evaluation(EvaluationRequest(
            material=material, part=part,
            dimensions={"length": 250.0, "diameter": 40.0, "thickness": 3.0},
            condition=condition,
            strength_allowables=allowables,
            laminate_stack=stack,
            material_id="carbon_epoxy_quasi_iso",
        ))
        self.assertIsInstance(result, EvaluationDraft)
        self.assertIsNotNone(result.safety_report)
        self.assertEqual(result.safety_report.method, "tsai_wu")
        self.assertEqual(len(result.safety_report.factors), 4)  # 4 plies


if __name__ == "__main__":
    unittest.main()
