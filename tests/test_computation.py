import unittest

from material_eval.catalog import Catalog
from material_eval.computation import calculate_part
from material_eval.conditions import Condition, Quantity
from material_eval.materials import build_single_material
from material_eval.uncertainty import Interval


class ComputationTest(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.material = build_single_material(
            name="测试材料",
            category="合成蛋白/生物基大分子",
            density_g_cm3=1.3,
            tensile_strength_mpa=9600,
            elastic_modulus_gpa=100,
        )

    def test_beam_calculation_returns_metrics(self):
        part = self.catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        result = calculate_part(part, self.material, {"diameter": 30, "length": 350, "thickness": 3})

        self.assertEqual(result.topology, "BEAM")
        self.assertEqual(len(result.metrics), 4)
        # Metric.value is now Interval; for zero-width input, typical == old float result
        self.assertIsInstance(result.metrics[0].value, Interval)
        self.assertGreater(result.metrics[0].value.typical, 0)
        self.assertGreater(result.metrics[1].value.typical, 0)
        self.assertIn("sectionproperties", " ".join(result.assumptions))

    def test_plate_calculation_returns_metrics(self):
        part = self.catalog.get_part("智能穿戴与柔性外骨骼", "智能穿戴承力外壳")
        result = calculate_part(part, self.material, {"length": 45, "width": 35, "thickness": 1.2})

        self.assertEqual(result.topology, "PLATE")
        self.assertEqual(len(result.metrics), 4)
        self.assertIsInstance(result.metrics[0].value, Interval)
        self.assertGreater(result.metrics[0].value.typical, 0)

    def test_strap_calculation_warns_about_fatigue(self):
        part = self.catalog.get_part("智能穿戴与柔性外骨骼", "柔性外骨骼助力带")
        result = calculate_part(part, self.material, {"width": 40, "thickness": 2.5})

        self.assertEqual(result.topology, "STRAP")
        self.assertEqual(len(result.metrics), 4)
        self.assertTrue(result.warnings)

    def test_calculate_part_accepts_condition_object(self):
        """calculate_part accepts Condition objects as well as legacy dicts."""
        part = self.catalog.get_part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        condition = Condition(
            diameter=Quantity(value=30, unit="mm"),
            length=Quantity(value=350, unit="mm"),
            thickness=Quantity(value=3, unit="mm"),
        )
        result_cond = calculate_part(part, self.material, condition)
        result_dict = calculate_part(part, self.material, {"diameter": 30, "length": 350, "thickness": 3})

        # Both paths should produce the same typical values
        self.assertEqual(result_cond.topology, result_dict.topology)
        for mc, md in zip(result_cond.metrics, result_dict.metrics):
            self.assertAlmostEqual(mc.value.typical, md.value.typical, places=6)


class IntervalCalculationTest(unittest.TestCase):
    """Verify that width-bearing material inputs produce width-bearing Metric outputs.

    The STRAP topology is used: tensile_load = tensile_strength_mpa * area.
    For a material with 10 % relative width on tensile_strength_mpa:
      low  = 0.9 * tensile_strength_mpa.typical * area.typical
      high = 1.1 * tensile_strength_mpa.typical * area.typical
    giving a relative width of ~10 % on the output.
    """

    def setUp(self):
        self.catalog = Catalog()
        # Material with explicit interval on tensile strength (±10 %)
        typical = 9600.0
        self.material = build_single_material(
            name="区间材料",
            category="合成蛋白/生物基大分子",
            density_g_cm3=1.3,
            tensile_strength_mpa=Interval(
                low=typical * 0.9,
                typical=typical,
                high=typical * 1.1,
                unit="MPa",
            ),
            elastic_modulus_gpa=100,
        )

    def test_strap_tensile_load_propagates_material_interval_width(self):
        """A 10 % interval on tensile strength propagates to ~10 % width on tensile load."""
        part = self.catalog.get_part("智能穿戴与柔性外骨骼", "柔性外骨骼助力带")
        result = calculate_part(part, self.material, {"width": 40, "thickness": 2.5})

        tensile_load = result.metrics[1].value  # "单向拉断载荷初筛"
        self.assertIsInstance(tensile_load, Interval)
        self.assertEqual(tensile_load.unit, "N")

        # Verify width has propagated: relative_width should be ~10 %
        rel_width = tensile_load.relative_width()
        self.assertGreater(rel_width, 0.05, "Expected > 5 % relative width on tensile load")
        self.assertLess(rel_width, 0.25, "Expected < 25 % relative width on tensile load")

        # low < typical < high
        self.assertLess(tensile_load.low, tensile_load.typical)
        self.assertLess(tensile_load.typical, tensile_load.high)

        # Typical value should match point-material result
        point_material = build_single_material(
            name="点材料",
            category="合成蛋白/生物基大分子",
            density_g_cm3=1.3,
            tensile_strength_mpa=9600.0,
            elastic_modulus_gpa=100,
        )
        result_point = calculate_part(part, point_material, {"width": 40, "thickness": 2.5})
        self.assertAlmostEqual(
            tensile_load.typical,
            result_point.metrics[1].value.typical,
            places=4,
        )


if __name__ == "__main__":
    unittest.main()
