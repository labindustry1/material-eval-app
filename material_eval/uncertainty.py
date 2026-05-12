from __future__ import annotations

from dataclasses import dataclass


class IntervalError(ValueError):
    pass


class NegativeWidthError(IntervalError):
    pass


class UnitMismatchError(IntervalError):
    pass


CONFIDENCE_SPREAD: tuple[tuple[float, float], ...] = (
    (0.7, 0.05),
    (0.5, 0.15),
    (0.0, 0.30),
)


@dataclass(frozen=True)
class Interval:
    low: float
    typical: float
    high: float
    unit: str
    widened: bool = False  # Set by safe_eval fallback (planned Phase 1 follow-up; not used by Task 1 arithmetic).

    def __post_init__(self) -> None:
        if not (self.low <= self.typical <= self.high):
            raise NegativeWidthError(
                f"Invalid interval order: low={self.low}, typical={self.typical}, high={self.high}"
            )

    @classmethod
    def point(cls, value: float, unit: str) -> "Interval":
        return cls(low=float(value), typical=float(value), high=float(value), unit=unit)

    @classmethod
    def from_confidence(cls, value: float, unit: str, confidence: float) -> "Interval":
        spread = _spread_for_confidence(float(confidence))
        return cls(
            low=float(value) * (1 - spread),
            typical=float(value),
            high=float(value) * (1 + spread),
            unit=unit,
        )

    def __add__(self, other: "Interval | float") -> "Interval":
        if isinstance(other, (int, float)):
            return Interval(self.low + other, self.typical + other, self.high + other, self.unit)
        _require_same_unit(self, other)
        return Interval(self.low + other.low, self.typical + other.typical, self.high + other.high, self.unit)

    def __sub__(self, other: "Interval | float") -> "Interval":
        if isinstance(other, (int, float)):
            return Interval(self.low - other, self.typical - other, self.high - other, self.unit)
        _require_same_unit(self, other)
        return Interval(self.low - other.high, self.typical - other.typical, self.high - other.low, self.unit)

    def __mul__(self, other: "Interval | float") -> "Interval":
        if isinstance(other, (int, float)):
            if other >= 0:
                return Interval(self.low * other, self.typical * other, self.high * other, self.unit)
            return Interval(self.high * other, self.typical * other, self.low * other, self.unit)
        endpoints = (self.low * other.low, self.low * other.high, self.high * other.low, self.high * other.high)
        return Interval(
            low=min(endpoints),
            typical=self.typical * other.typical,
            high=max(endpoints),
            unit=_combine_units(self.unit, other.unit, "*"),
        )

    __rmul__ = __mul__

    def __truediv__(self, other: "Interval | float") -> "Interval":
        if isinstance(other, (int, float)):
            if other == 0:
                raise IntervalError("Division by zero scalar")
            if other > 0:
                return Interval(self.low / other, self.typical / other, self.high / other, self.unit)
            return Interval(self.high / other, self.typical / other, self.low / other, self.unit)
        if other.low <= 0 <= other.high:
            raise IntervalError(f"Interval division by zero-crossing divisor [{other.low}, {other.high}]")
        endpoints = (self.low / other.low, self.low / other.high, self.high / other.low, self.high / other.high)
        return Interval(
            low=min(endpoints),
            typical=self.typical / other.typical,
            high=max(endpoints),
            unit=_combine_units(self.unit, other.unit, "/"),
        )

    def __pow__(self, n: int) -> "Interval":
        if not isinstance(n, int) or n < 1:
            raise IntervalError(f"Only positive integer powers supported, got {n!r}")
        if n % 2 == 1:
            # Odd power is monotone: preserves order
            return Interval(self.low ** n, self.typical ** n, self.high ** n, _pow_unit(self.unit, n))
        if self.low >= 0:
            return Interval(self.low ** n, self.typical ** n, self.high ** n, _pow_unit(self.unit, n))
        if self.high <= 0:
            # All non-positive: even power flips order
            return Interval(self.high ** n, self.typical ** n, self.low ** n, _pow_unit(self.unit, n))
        # Mixed-sign: minimum is 0 at x=0, maximum is the larger end raised
        low_n = 0.0
        high_n = max(self.low ** n, self.high ** n)
        # typical**n could still be 0 even if typical != 0 (when typical=0); ensure ordering
        return Interval(low=low_n, typical=self.typical ** n, high=high_n, unit=_pow_unit(self.unit, n))

    def relative_width(self) -> float:
        if self.typical == 0:
            return 0.0
        return (self.high - self.low) / abs(self.typical)

    def format(self) -> str:
        if self.low == self.typical == self.high:
            return f"{_fmt_num(self.typical)} {self.unit}".strip()
        return (
            f"{_fmt_num(self.low)} / {_fmt_num(self.typical)} / {_fmt_num(self.high)} {self.unit}"
        ).strip()


def _spread_for_confidence(confidence: float) -> float:
    for threshold, spread in CONFIDENCE_SPREAD:
        if confidence >= threshold:
            return spread
    return CONFIDENCE_SPREAD[-1][1]


def _require_same_unit(a: Interval, b: Interval) -> None:
    if a.unit != b.unit:
        raise UnitMismatchError(f"Unit mismatch: {a.unit!r} vs {b.unit!r}")


def _combine_units(a: str, b: str, op: str) -> str:
    if a == b and op == "/":
        return ""
    return f"{a}{op}{b}"


def _pow_unit(unit: str, n: int) -> str:
    if not unit:
        return unit
    return f"{unit}**{n}"


def _fmt_num(x: float) -> str:
    if x == 0:
        return "0"
    abs_x = abs(x)
    if abs_x >= 1000:
        return f"{round(x):d}"
    if abs_x >= 0.1:
        return f"{x:.3g}"
    return f"{x:.2e}"

