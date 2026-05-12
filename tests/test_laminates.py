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

        self.assertAlmostEqual(result.total_thickness_mm.typical, 0.25)
        self.assertGreater(result.ex_gpa.typical, 120)
        self.assertLess(result.ey_gpa.typical, 12)
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

        self.assertGreater(result.ex_gpa.typical, 40)
        self.assertLess(result.ex_gpa.typical, 80)
        self.assertGreater(result.ey_gpa.typical, 40)
        self.assertLess(result.ey_gpa.typical, 80)
        self.assertFalse(result.warnings)

    def test_laminate_result_uses_zero_width_intervals(self):
        stack = LaminateStack.symmetric_cross_ply(
            e1_gpa=135,
            e2_gpa=10,
            g12_gpa=5,
            nu12=0.3,
            ply_thickness_mm=0.125,
        )

        result = analyze_laminate(stack)

        # Phase 1: single-ply inputs are float → output is zero-width Interval
        self.assertEqual(result.ex_gpa.low, result.ex_gpa.high)
        self.assertEqual(result.ex_gpa.unit, "GPa")
        self.assertEqual(result.ey_gpa.low, result.ey_gpa.high)
        self.assertEqual(result.ey_gpa.unit, "GPa")
        self.assertEqual(result.gxy_gpa.low, result.gxy_gpa.high)
        self.assertEqual(result.gxy_gpa.unit, "GPa")
        self.assertEqual(result.nuxy.low, result.nuxy.high)
        self.assertEqual(result.nuxy.unit, "")
        self.assertEqual(result.total_thickness_mm.low, result.total_thickness_mm.high)
        self.assertEqual(result.total_thickness_mm.unit, "mm")


if __name__ == "__main__":
    unittest.main()
