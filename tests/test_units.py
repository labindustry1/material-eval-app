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


from material_eval.units import normalize_quantity


class QuantityNormalizationTest(unittest.TestCase):
    def test_length_mm_to_canonical(self):
        v, u = normalize_quantity(10.0, "cm", "length")
        self.assertAlmostEqual(v, 100.0)
        self.assertEqual(u, "mm")

    def test_length_inch_to_mm(self):
        v, u = normalize_quantity(1.0, "in", "length")
        self.assertAlmostEqual(v, 25.4)

    def test_force_kn_to_n(self):
        v, u = normalize_quantity(2.0, "kN", "force")
        self.assertAlmostEqual(v, 2000.0)
        self.assertEqual(u, "N")

    def test_pressure_gpa_to_mpa(self):
        v, u = normalize_quantity(1.0, "GPa", "stress")
        self.assertAlmostEqual(v, 1000.0)
        self.assertEqual(u, "MPa")

    def test_temperature_kelvin_to_c(self):
        v, u = normalize_quantity(300.0, "K", "temperature")
        self.assertAlmostEqual(v, 26.85, places=2)
        self.assertEqual(u, "degC")

    def test_humidity_passthrough(self):
        v, u = normalize_quantity(60.0, "%RH", "humidity")
        self.assertAlmostEqual(v, 60.0)
        self.assertEqual(u, "%RH")

    def test_strain_rate(self):
        v, u = normalize_quantity(0.01, "1/s", "strain_rate")
        self.assertAlmostEqual(v, 0.01)
        self.assertEqual(u, "1/s")

    def test_moment_nm(self):
        v, u = normalize_quantity(5.0, "N*m", "moment")
        self.assertAlmostEqual(v, 5.0)
        self.assertEqual(u, "N*m")

    def test_dimension_mismatch_raises(self):
        with self.assertRaises(UnitCompatibilityError):
            normalize_quantity(1.0, "kg", "length")


if __name__ == "__main__":
    unittest.main()
