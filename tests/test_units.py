import unittest

from material_eval.units import UnitCompatibilityError, normalize_material_property


class UnitNormalizationTest(unittest.TestCase):
    def test_normalizes_density_to_g_per_cm3(self):
        measurement = normalize_material_property("density_g_cm3", 1800, "kg/m^3")

        self.assertEqual(measurement.unit, "g/cm^3")
        self.assertAlmostEqual(measurement.value, 1.8, places=6)

    def test_normalizes_strength_to_mpa(self):
        measurement = normalize_material_property("tensile_strength_mpa", 6.37, "GPa")

        self.assertEqual(measurement.unit, "MPa")
        self.assertAlmostEqual(measurement.value, 6370, places=6)

    def test_normalizes_modulus_to_gpa(self):
        measurement = normalize_material_property("elastic_modulus_gpa", 294000, "MPa")

        self.assertEqual(measurement.unit, "GPa")
        self.assertAlmostEqual(measurement.value, 294, places=6)

    def test_rejects_incompatible_dimension(self):
        with self.assertRaises(UnitCompatibilityError):
            normalize_material_property("tensile_strength_mpa", 1.8, "kg/m^3")


if __name__ == "__main__":
    unittest.main()
