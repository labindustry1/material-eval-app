import json
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


SAMPLE_SEED = {
    "version": "test_v1",
    "materials": [
        {
            "id": "mat_a",
            "name": "Material A",
            "category": "polymer",
            "form": "sheet",
            "process": "injection",
            "envelope": {
                "temperature_C": [-40, 120],
                "humidity_pct": [0, 70],
                "thickness_mm": [0.5, 10],
                "source": "supplier datasheet",
            },
        },
        {
            "id": "mat_b",
            "name": "Material B",
            "category": "composite",
            "form": "tape",
            "process": "autoclave",
        },
    ],
    "observations": [
        # single-point for mat_a density
        {
            "material_id": "mat_a",
            "property_name": "density_g_cm3",
            "value": 1.8,
            "unit": "g/cm^3",
            "test_condition": "23°C",
            "source_type": "datasheet",
            "source_label": "Supplier A",
            "confidence": 0.9,
        },
        # three-point for mat_a tensile strength
        {
            "material_id": "mat_a",
            "property_name": "tensile_strength_mpa",
            "value": {"low": 100.0, "typical": 120.0, "high": 140.0},
            "unit": "MPa",
            "test_condition": "23°C",
            "source_type": "datasheet",
            "source_label": "Supplier A",
            "confidence": 0.85,
        },
        # two observations for mat_b density (for aggregation test)
        {
            "material_id": "mat_b",
            "property_name": "density_g_cm3",
            "value": 1.5,
            "unit": "g/cm^3",
            "test_condition": "23°C",
            "source_type": "datasheet",
            "source_label": "Supplier B low",
            "confidence": 0.7,
        },
        {
            "material_id": "mat_b",
            "property_name": "density_g_cm3",
            "value": 1.6,
            "unit": "g/cm^3",
            "test_condition": "23°C",
            "source_type": "test",
            "source_label": "Lab B high",
            "confidence": 0.9,
        },
        # mat_b elastic modulus for build_candidate completeness
        {
            "material_id": "mat_b",
            "property_name": "elastic_modulus_gpa",
            "value": 70.0,
            "unit": "GPa",
            "test_condition": "23°C",
            "source_type": "datasheet",
            "source_label": "Supplier B",
            "confidence": 0.8,
        },
        # mat_a elastic modulus
        {
            "material_id": "mat_a",
            "property_name": "elastic_modulus_gpa",
            "value": 3.5,
            "unit": "GPa",
            "test_condition": "23°C",
            "source_type": "datasheet",
            "source_label": "Supplier A",
            "confidence": 0.8,
        },
        # mat_b tensile strength
        {
            "material_id": "mat_b",
            "property_name": "tensile_strength_mpa",
            "value": 300.0,
            "unit": "MPa",
            "test_condition": "23°C",
            "source_type": "datasheet",
            "source_label": "Supplier B",
            "confidence": 0.8,
        },
    ],
}


class IntervalAndEnvelopeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        seed_path = Path(self._tmp.name) / "material_property_library.json"
        seed_path.write_text(json.dumps(SAMPLE_SEED), encoding="utf-8")
        self.lib = MaterialPropertyLibrary(seed_path)

    def tearDown(self):
        self._tmp.cleanup()

    # Test 1: single-point seed produces interval with typical==value, low/high spread by confidence
    def test_single_point_interval_typical_equals_value(self):
        obs = self.lib.best_observation("mat_a", "density_g_cm3")
        self.assertAlmostEqual(obs.interval.typical, 1.8)
        self.assertEqual(obs.interval.unit, "g/cm^3")
        # confidence=0.9 → spread=0.05, so low = 1.8*0.95, high = 1.8*1.05
        self.assertAlmostEqual(obs.interval.low, 1.8 * 0.95, places=6)
        self.assertAlmostEqual(obs.interval.high, 1.8 * 1.05, places=6)

    # Test 2: three-point seed produces interval with exact low/typical/high (normalized)
    def test_three_point_interval_exact_bounds(self):
        obs = self.lib.best_observation("mat_a", "tensile_strength_mpa")
        # MPa → MPa, so no conversion
        self.assertAlmostEqual(obs.interval.low, 100.0, places=6)
        self.assertAlmostEqual(obs.interval.typical, 120.0, places=6)
        self.assertAlmostEqual(obs.interval.high, 140.0, places=6)
        self.assertEqual(obs.interval.unit, "MPa")

    # Test 3: multi-observation aggregation via property_interval
    def test_property_interval_aggregates_multiple_observations(self):
        # mat_b has two density observations: 1.5 (conf=0.7) and 1.6 (conf=0.9)
        # CONFIDENCE_SPREAD: conf>=0.7 -> spread=0.05; conf>=0.5 -> spread=0.15
        # obs1: conf=0.7 >= 0.7 -> spread=0.05 -> low=1.5*0.95=1.425, high=1.5*1.05=1.575
        # obs2: conf=0.9 >= 0.7 -> spread=0.05 -> low=1.6*0.95=1.52,  high=1.6*1.05=1.68
        interval = self.lib.property_interval("mat_b", "density_g_cm3")
        self.assertIsNotNone(interval)
        # low = min(1.425, 1.52) = 1.425
        # high = max(1.575, 1.68) = 1.68
        # typical = highest-confidence observation (conf=0.9, value=1.6)
        self.assertAlmostEqual(interval.typical, 1.6, places=6)
        self.assertAlmostEqual(interval.low, 1.5 * 0.95, places=6)
        self.assertAlmostEqual(interval.high, 1.6 * 1.05, places=6)

    # Test 4: envelope_for returns correct EnvelopeSpec
    def test_envelope_for_returns_correct_spec(self):
        env = self.lib.envelope_for("mat_a")
        self.assertIsNotNone(env)
        self.assertEqual(env.temperature_C, (-40.0, 120.0))
        self.assertEqual(env.humidity_pct, (0.0, 70.0))
        self.assertEqual(env.thickness_mm, (0.5, 10.0))
        self.assertEqual(env.source, "supplier datasheet")

    # Test 5: envelope_for returns None when no envelope declared
    def test_envelope_for_returns_none_when_absent(self):
        env = self.lib.envelope_for("mat_b")
        self.assertIsNone(env)

    # Test 6: property_interval returns None when no observations
    def test_property_interval_returns_none_when_no_observations(self):
        result = self.lib.property_interval("mat_a", "nonexistent_property")
        self.assertIsNone(result)

    # Test 7: single observation property_interval returns that observation's interval
    def test_property_interval_single_observation_returns_interval(self):
        interval = self.lib.property_interval("mat_a", "density_g_cm3")
        self.assertIsNotNone(interval)
        obs = self.lib.best_observation("mat_a", "density_g_cm3")
        self.assertAlmostEqual(interval.typical, obs.interval.typical, places=6)
        self.assertAlmostEqual(interval.low, obs.interval.low, places=6)
        self.assertAlmostEqual(interval.high, obs.interval.high, places=6)

    # Test 8: existing fields still present on observations (backward compat)
    def test_existing_observation_fields_still_present(self):
        obs = self.lib.best_observation("mat_a", "density_g_cm3")
        self.assertAlmostEqual(obs.value, 1.8)
        self.assertAlmostEqual(obs.canonical_value, 1.8)
        self.assertEqual(obs.unit, "g/cm^3")
        self.assertEqual(obs.canonical_unit, "g/cm^3")
        self.assertAlmostEqual(obs.confidence, 0.9)


if __name__ == "__main__":
    unittest.main()
