import unittest

from material_eval.catalog import Catalog
from material_eval.computation import calculate_part
from material_eval.materials import build_single_material


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
        self.assertGreater(result.metrics[0].value, 0)
        self.assertGreater(result.metrics[1].value, 0)
        self.assertIn("sectionproperties", " ".join(result.assumptions))

    def test_plate_calculation_returns_metrics(self):
        part = self.catalog.get_part("智能穿戴与柔性外骨骼", "智能穿戴承力外壳")
        result = calculate_part(part, self.material, {"length": 45, "width": 35, "thickness": 1.2})

        self.assertEqual(result.topology, "PLATE")
        self.assertEqual(len(result.metrics), 4)
        self.assertGreater(result.metrics[0].value, 0)

    def test_strap_calculation_warns_about_fatigue(self):
        part = self.catalog.get_part("智能穿戴与柔性外骨骼", "柔性外骨骼助力带")
        result = calculate_part(part, self.material, {"width": 40, "thickness": 2.5})

        self.assertEqual(result.topology, "STRAP")
        self.assertEqual(len(result.metrics), 4)
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
