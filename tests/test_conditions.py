import unittest

from material_eval.conditions import Condition, Quantity
from material_eval.units import UnitCompatibilityError


class QuantityTest(unittest.TestCase):
    def test_quantity_stores_value_and_unit(self):
        q = Quantity(value=10.0, unit="mm")
        self.assertEqual(q.value, 10.0)
        self.assertEqual(q.unit, "mm")


class ConditionConstructionTest(unittest.TestCase):
    def test_empty_condition_returns_no_envelope_inputs(self):
        c = Condition()
        axes = c.envelope_axes()
        self.assertTrue(all(v is None for v in axes.values()))

    def test_temperature_normalized_to_celsius(self):
        c = Condition(temperature=Quantity(value=300.0, unit="K"))
        self.assertAlmostEqual(c.envelope_axes()["temperature_C"], 26.85, places=2)

    def test_length_input_normalized_to_mm(self):
        c = Condition(length=Quantity(value=10.0, unit="cm"))
        self.assertAlmostEqual(c.geometry_mm()["length"], 100.0)

    def test_inch_normalized(self):
        c = Condition(length=Quantity(value=1.0, unit="in"))
        self.assertAlmostEqual(c.geometry_mm()["length"], 25.4)

    def test_pressure_normalized_for_envelope_stress(self):
        c = Condition(pressure=Quantity(value=1.0, unit="GPa"))
        self.assertAlmostEqual(c.envelope_axes()["stress_MPa"], 1000.0)

    def test_strain_rate_normalized(self):
        c = Condition(strain_rate=Quantity(value=0.01, unit="1/s"))
        self.assertAlmostEqual(c.envelope_axes()["strain_rate_1_per_s"], 0.01)

    def test_thickness_normalized_for_envelope(self):
        c = Condition(thickness=Quantity(value=0.5, unit="cm"))
        self.assertAlmostEqual(c.envelope_axes()["thickness_mm"], 5.0)

    def test_bad_unit_raises(self):
        with self.assertRaises(UnitCompatibilityError):
            Condition(temperature=Quantity(value=10.0, unit="MPa"))


class ConditionLegacyShimTest(unittest.TestCase):
    def test_from_dimensions_dict(self):
        c = Condition.from_dimensions({"length": 100.0, "diameter": 30.0, "thickness": 2.0})
        self.assertEqual(c.geometry_mm()["length"], 100.0)
        self.assertEqual(c.geometry_mm()["diameter"], 30.0)
        self.assertEqual(c.geometry_mm()["thickness"], 2.0)

    def test_from_dimensions_with_environment(self):
        c = Condition.from_dimensions(
            {"length": 100.0},
            temperature=Quantity(value=80.0, unit="degC"),
        )
        self.assertAlmostEqual(c.envelope_axes()["temperature_C"], 80.0)
