import unittest

from material_eval.laminates import Lamina, LaminateStack, analyze_laminate


class LaminateTest(unittest.TestCase):
    def test_unidirectional_zero_degree_laminate_keeps_fiber_direction_modulus(self):
        stack = LaminateStack(
            plies=(
                Lamina(e1_gpa=135, e2_gpa=10, g12_gpa=5, nu12=0.3, thickness_mm=0.125, angle_deg=0),
                Lamina(e1_gpa=135, e2_gpa=10, g12_gpa=5, nu12=0.3, thickness_mm=0.125, angle_deg=0),
            )
        )

        result = analyze_laminate(stack)

        self.assertAlmostEqual(result.total_thickness_mm, 0.25)
        self.assertGreater(result.ex_gpa, 120)
        self.assertLess(result.ey_gpa, 12)
        self.assertEqual(result.method, "classical-laminate-theory")

    def test_balanced_cross_ply_laminate_has_intermediate_modulus(self):
        stack = LaminateStack.symmetric_cross_ply(
            e1_gpa=135,
            e2_gpa=10,
            g12_gpa=5,
            nu12=0.3,
            ply_thickness_mm=0.125,
        )

        result = analyze_laminate(stack)

        self.assertGreater(result.ex_gpa, 40)
        self.assertLess(result.ex_gpa, 80)
        self.assertGreater(result.ey_gpa, 40)
        self.assertLess(result.ey_gpa, 80)
        self.assertFalse(result.warnings)


if __name__ == "__main__":
    unittest.main()
