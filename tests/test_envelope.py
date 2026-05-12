import unittest

from material_eval.uncertainty import EnvelopeReport, EnvelopeSpec, Violation


class _StubCondition:
    """Minimal duck-typed Condition for testing EnvelopeSpec in isolation."""

    def __init__(self, **kwargs):
        # values stored as canonical floats: temperature in °C, humidity in %RH, etc.
        self._values = kwargs

    def envelope_axes(self) -> dict[str, float | None]:
        return {
            "temperature_C": self._values.get("temperature_C"),
            "humidity_pct": self._values.get("humidity_pct"),
            "stress_MPa": self._values.get("stress_MPa"),
            "strain_rate_1_per_s": self._values.get("strain_rate_1_per_s"),
            "fatigue_cycles": self._values.get("fatigue_cycles"),
            "thickness_mm": self._values.get("thickness_mm"),
        }


class EnvelopeSpecCheckTest(unittest.TestCase):
    def test_all_axes_none_pass_but_undeclared(self):
        env = EnvelopeSpec()
        report = env.check(_StubCondition(temperature_C=25.0))
        self.assertTrue(report.passed)
        self.assertFalse(report.has_declared_envelope)

    def test_temperature_in_range_passes(self):
        env = EnvelopeSpec(temperature_C=(-40.0, 120.0), source="supplier datasheet")
        report = env.check(_StubCondition(temperature_C=80.0))
        self.assertTrue(report.passed)
        self.assertTrue(report.has_declared_envelope)

    def test_temperature_above_high_violates(self):
        env = EnvelopeSpec(temperature_C=(-40.0, 120.0), source="supplier datasheet")
        report = env.check(_StubCondition(temperature_C=150.0))
        self.assertFalse(report.passed)
        self.assertEqual(len(report.violations), 1)
        v = report.violations[0]
        self.assertEqual(v.axis, "temperature_C")
        self.assertEqual(v.input_value, 150.0)
        self.assertEqual(v.allowed_range, (-40.0, 120.0))
        self.assertEqual(v.source, "supplier datasheet")

    def test_temperature_at_boundary_passes(self):
        env = EnvelopeSpec(temperature_C=(-40.0, 120.0))
        self.assertTrue(env.check(_StubCondition(temperature_C=-40.0)).passed)
        self.assertTrue(env.check(_StubCondition(temperature_C=120.0)).passed)

    def test_missing_input_for_declared_axis_is_not_violation(self):
        env = EnvelopeSpec(temperature_C=(-40.0, 120.0))
        report = env.check(_StubCondition())
        self.assertTrue(report.passed)
        self.assertTrue(report.has_declared_envelope)

    def test_multiple_violations_collected(self):
        env = EnvelopeSpec(
            temperature_C=(-40.0, 120.0),
            humidity_pct=(0.0, 70.0),
            stress_MPa=(0.0, 200.0),
        )
        report = env.check(
            _StubCondition(temperature_C=150.0, humidity_pct=85.0, stress_MPa=300.0)
        )
        self.assertFalse(report.passed)
        self.assertEqual({v.axis for v in report.violations}, {"temperature_C", "humidity_pct", "stress_MPa"})

    def test_has_any_axis_false_for_empty(self):
        self.assertFalse(EnvelopeSpec().has_any_axis())

    def test_has_any_axis_true_when_any_set(self):
        self.assertTrue(EnvelopeSpec(temperature_C=(-40.0, 120.0)).has_any_axis())
