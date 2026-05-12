import unittest

from material_eval.uncertainty import (
    CONFIDENCE_SPREAD,
    Interval,
    IntervalError,
    NegativeWidthError,
    UnitMismatchError,
)


class IntervalConstructionTest(unittest.TestCase):
    def test_valid_interval_constructs(self):
        iv = Interval(low=1.0, typical=2.0, high=3.0, unit="MPa")
        self.assertEqual(iv.low, 1.0)
        self.assertEqual(iv.typical, 2.0)
        self.assertEqual(iv.high, 3.0)
        self.assertEqual(iv.unit, "MPa")
        self.assertFalse(iv.widened)

    def test_typical_below_low_raises(self):
        with self.assertRaises(NegativeWidthError):
            Interval(low=2.0, typical=1.0, high=3.0, unit="MPa")

    def test_high_below_typical_raises(self):
        with self.assertRaises(NegativeWidthError):
            Interval(low=1.0, typical=3.0, high=2.0, unit="MPa")

    def test_point_factory_zero_width(self):
        iv = Interval.point(value=5.0, unit="kg")
        self.assertEqual((iv.low, iv.typical, iv.high), (5.0, 5.0, 5.0))

    def test_from_confidence_high(self):
        iv = Interval.from_confidence(100.0, "MPa", confidence=0.8)
        self.assertAlmostEqual(iv.low, 95.0)
        self.assertAlmostEqual(iv.high, 105.0)
        self.assertEqual(iv.typical, 100.0)

    def test_from_confidence_medium(self):
        iv = Interval.from_confidence(100.0, "MPa", confidence=0.6)
        self.assertAlmostEqual(iv.low, 85.0)
        self.assertAlmostEqual(iv.high, 115.0)

    def test_from_confidence_low(self):
        iv = Interval.from_confidence(100.0, "MPa", confidence=0.3)
        self.assertAlmostEqual(iv.low, 70.0)
        self.assertAlmostEqual(iv.high, 130.0)


class IntervalArithmeticTest(unittest.TestCase):
    def setUp(self):
        self.a = Interval(low=1.0, typical=2.0, high=3.0, unit="MPa")
        self.b = Interval(low=10.0, typical=20.0, high=30.0, unit="MPa")

    def test_add_same_unit(self):
        c = self.a + self.b
        self.assertEqual((c.low, c.typical, c.high), (11.0, 22.0, 33.0))
        self.assertEqual(c.unit, "MPa")

    def test_add_unit_mismatch_raises(self):
        c = Interval.point(1.0, unit="kg")
        with self.assertRaises(UnitMismatchError):
            _ = self.a + c

    def test_sub_same_unit_widens(self):
        # [1,2,3] - [10,20,30] -> [1-30, 2-20, 3-10] = [-29, -18, -7]
        c = self.a - self.b
        self.assertEqual(c.low, -29.0)
        self.assertEqual(c.typical, -18.0)
        self.assertEqual(c.high, -7.0)

    def test_mul_positive(self):
        c = self.a * self.b
        # endpoint exhaustion: min/max of [1*10, 1*30, 3*10, 3*30] = [10, 90]
        self.assertEqual(c.low, 10.0)
        self.assertEqual(c.high, 90.0)
        self.assertEqual(c.typical, 40.0)  # 2*20
        self.assertEqual(c.unit, "MPa*MPa")

    def test_mul_with_scalar(self):
        c = self.a * 2.0
        self.assertEqual((c.low, c.typical, c.high), (2.0, 4.0, 6.0))
        self.assertEqual(c.unit, "MPa")

    def test_truediv_scalar(self):
        c = self.a / 2.0
        self.assertEqual((c.low, c.typical, c.high), (0.5, 1.0, 1.5))

    def test_truediv_interval_positive(self):
        c = self.b / self.a  # [10..30] / [1..3]
        # endpoints: 10/1=10, 10/3≈3.33, 30/1=30, 30/3=10
        self.assertAlmostEqual(c.low, 10.0 / 3.0)
        self.assertAlmostEqual(c.high, 30.0)
        self.assertEqual(c.typical, 10.0)  # 20/2

    def test_truediv_interval_crossing_zero_widens(self):
        crossing = Interval(low=-1.0, typical=0.0, high=1.0, unit="N")
        with self.assertRaises(IntervalError):
            _ = self.a / crossing

    def test_pow_positive_integer(self):
        c = self.a ** 2
        self.assertEqual((c.low, c.typical, c.high), (1.0, 4.0, 9.0))
        self.assertEqual(c.unit, "MPa**2")

    def test_pow_three(self):
        c = self.a ** 3
        self.assertEqual((c.low, c.typical, c.high), (1.0, 8.0, 27.0))

    def test_relative_width(self):
        iv = Interval(low=9.0, typical=10.0, high=11.0, unit="MPa")
        self.assertAlmostEqual(iv.relative_width(), 0.2)

    def test_relative_width_zero_typical(self):
        iv = Interval.point(0.0, "N")
        self.assertEqual(iv.relative_width(), 0.0)

    def test_add_scalar(self):
        c = self.a + 5.0
        self.assertEqual((c.low, c.typical, c.high), (6.0, 7.0, 8.0))
        self.assertEqual(c.unit, "MPa")

    def test_sub_scalar(self):
        c = self.a - 1.0
        self.assertEqual((c.low, c.typical, c.high), (0.0, 1.0, 2.0))

    def test_mul_negative_scalar_flips(self):
        c = self.a * -2.0
        self.assertEqual((c.low, c.typical, c.high), (-6.0, -4.0, -2.0))

    def test_truediv_negative_scalar_flips(self):
        c = self.a / -2.0
        self.assertEqual((c.low, c.typical, c.high), (-1.5, -1.0, -0.5))

    def test_truediv_zero_scalar_raises(self):
        with self.assertRaises(IntervalError):
            _ = self.a / 0.0

    def test_pow_zero_or_negative_raises(self):
        with self.assertRaises(IntervalError):
            _ = self.a ** 0
        with self.assertRaises(IntervalError):
            _ = self.a ** -1

    def test_pow_float_raises(self):
        with self.assertRaises(IntervalError):
            _ = self.a ** 2.0  # type: ignore[operator]

    def test_pow_two_on_mixed_sign_uses_zero_min(self):
        mixed = Interval(low=-2.0, typical=1.0, high=3.0, unit="m")
        c = mixed ** 2
        self.assertEqual(c.low, 0.0)
        self.assertEqual(c.high, 9.0)
        self.assertEqual(c.typical, 1.0)
        self.assertEqual(c.unit, "m**2")

    def test_pow_three_on_negative_interval(self):
        neg = Interval(low=-3.0, typical=-2.0, high=-1.0, unit="m")
        c = neg ** 3
        self.assertEqual((c.low, c.typical, c.high), (-27.0, -8.0, -1.0))

    def test_pow_two_on_all_negative(self):
        neg = Interval(low=-3.0, typical=-2.0, high=-1.0, unit="m")
        c = neg ** 2
        self.assertEqual((c.low, c.typical, c.high), (1.0, 4.0, 9.0))


class IntervalFormatTest(unittest.TestCase):
    def test_format_large_takes_integer(self):
        iv = Interval(low=1110.4, typical=1234.5, high=1380.7, unit="MPa")
        self.assertEqual(iv.format(), "1110 / 1234 / 1381 MPa")

    def test_format_point_collapses(self):
        iv = Interval.point(42.0, "kg")
        self.assertEqual(iv.format(), "42 kg")

    def test_format_mid_range_three_sigfig(self):
        iv = Interval(low=1.234, typical=2.344, high=3.456, unit="GPa")
        self.assertEqual(iv.format(), "1.23 / 2.34 / 3.46 GPa")

    def test_format_small_uses_scientific(self):
        iv = Interval(low=1.2e-3, typical=2.3e-3, high=3.4e-3, unit="m")
        self.assertEqual(iv.format(), "1.20e-03 / 2.30e-03 / 3.40e-03 m")


if __name__ == "__main__":
    unittest.main()
