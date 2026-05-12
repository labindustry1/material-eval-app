import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from material_eval.material_property_library import MaterialPropertyLibrary


class MaterialPropertyLibraryTest(unittest.TestCase):
    def setUp(self):
        self.library = MaterialPropertyLibrary()

    def test_seed_library_has_baseline_materials_and_observations(self):
        self.assertGreaterEqual(len(self.library.materials), 10)
        self.assertGreaterEqual(len(self.library.observations), 30)

    def test_observations_keep_source_conditions_units_and_confidence(self):
        observation = self.library.observations[0]

        self.assertTrue(observation.unit)
        self.assertTrue(observation.source_label)
        self.assertTrue(observation.test_condition)
        self.assertGreaterEqual(observation.confidence, 0)
        self.assertLessEqual(observation.confidence, 1)

    def test_build_candidate_from_baseline_material(self):
        candidate = self.library.build_candidate("t1000_carbon_fiber_ud")

        self.assertEqual(candidate.name, "T1000 碳纤维单向带")
        self.assertGreater(candidate.density_g_cm3, 1.0)
        self.assertGreater(candidate.tensile_strength_mpa, 4000)
        self.assertGreater(candidate.elastic_modulus_gpa, 200)
        self.assertIn("材料属性库", candidate.notes)

    def test_detects_property_conflicts(self):
        conflicts = self.library.detect_conflicts(material_id="peek_unfilled", property_name="tensile_strength_mpa")

        self.assertTrue(conflicts)
        self.assertEqual(conflicts[0].material_id, "peek_unfilled")
        self.assertEqual(conflicts[0].property_name, "tensile_strength_mpa")
        self.assertGreater(conflicts[0].relative_spread, 0.15)

    def test_build_candidate_normalizes_mixed_source_units(self):
        with TemporaryDirectory() as tmp_dir:
            seed_path = Path(tmp_dir) / "material_property_library.json"
            seed_path.write_text(
                """
{
  "version": "unit_test_seed",
  "materials": [
    {"id": "mixed_units", "name": "混合单位材料", "category": "测试材料", "form": "coupon", "process": "lab"}
  ],
  "observations": [
    {"material_id": "mixed_units", "property_name": "density_g_cm3", "value": 1800, "unit": "kg/m^3", "test_condition": "lab", "source_type": "test", "source_label": "density", "confidence": 0.9},
    {"material_id": "mixed_units", "property_name": "tensile_strength_mpa", "value": 6.37, "unit": "GPa", "test_condition": "lab", "source_type": "test", "source_label": "strength", "confidence": 0.9},
    {"material_id": "mixed_units", "property_name": "elastic_modulus_gpa", "value": 294000, "unit": "MPa", "test_condition": "lab", "source_type": "test", "source_label": "modulus", "confidence": 0.9}
  ]
}
                """.strip(),
                encoding="utf-8",
            )

            candidate = MaterialPropertyLibrary(seed_path).build_candidate("mixed_units")

        self.assertAlmostEqual(candidate.density_g_cm3, 1.8, places=6)
        self.assertAlmostEqual(candidate.tensile_strength_mpa, 6370, places=6)
        self.assertAlmostEqual(candidate.elastic_modulus_gpa, 294, places=6)


if __name__ == "__main__":
    unittest.main()
