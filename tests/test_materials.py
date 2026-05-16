"""Tests for Task 6: MaterialCandidate with Interval-typed properties."""
from __future__ import annotations

import unittest

from material_eval.materials import build_composite_material, build_single_material
from material_eval.uncertainty import Interval


class TestMaterialCandidateIntervalFields(unittest.TestCase):
    def test_build_single_material_fields_are_intervals(self):
        m = build_single_material(
            name="Test Steel",
            category="金属",
            density_g_cm3=7.85,
            tensile_strength_mpa=800.0,
            elastic_modulus_gpa=210.0,
        )
        self.assertIsInstance(m.density_g_cm3, Interval)
        self.assertIsInstance(m.tensile_strength_mpa, Interval)
        self.assertIsInstance(m.elastic_modulus_gpa, Interval)
        # Point intervals: low == typical == high
        self.assertAlmostEqual(m.density_g_cm3.typical, 7.85)
        self.assertAlmostEqual(m.tensile_strength_mpa.typical, 800.0)
        self.assertAlmostEqual(m.elastic_modulus_gpa.typical, 210.0)
        self.assertAlmostEqual(m.density_g_cm3.low, 7.85)
        self.assertAlmostEqual(m.density_g_cm3.high, 7.85)

    def test_specific_strength_typical_and_specific_modulus_typical(self):
        m = build_single_material(
            name="Test",
            category="金属",
            density_g_cm3=2.0,
            tensile_strength_mpa=400.0,
            elastic_modulus_gpa=70.0,
        )
        self.assertAlmostEqual(m.specific_strength_typical, 400.0 / 2.0)
        self.assertAlmostEqual(m.specific_modulus_typical, 70.0 / 2.0)

    def test_build_composite_material_rule_of_mixtures(self):
        # vf=0.6: density=1.2*0.4+1.8*0.6=0.48+1.08=1.56, strength=50*0.4+1000*0.6=20+600=620
        # modulus=3.5*0.4+200*0.6=1.4+120=121.4
        m = build_composite_material(
            matrix_name="环氧",
            fiber_name="碳纤维",
            fiber_volume_fraction=0.6,
            matrix_density=1.2,
            matrix_strength=50.0,
            matrix_modulus=3.5,
            fiber_density=1.8,
            fiber_strength=1000.0,
            fiber_modulus=200.0,
        )
        self.assertIsInstance(m.density_g_cm3, Interval)
        self.assertAlmostEqual(m.density_g_cm3.typical, 1.56, places=6)
        self.assertAlmostEqual(m.tensile_strength_mpa.typical, 620.0, places=6)
        self.assertAlmostEqual(m.elastic_modulus_gpa.typical, 121.4, places=6)


if __name__ == "__main__":
    unittest.main()
