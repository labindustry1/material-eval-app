# Phase 1 可信数字基础设施 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把材料评估 MVP 的所有数值结果升级为三点区间 (low/typical/high)，并在所有计算前校验工况是否在材料适用域内；越界硬拒绝出数。

**Architecture:** 引入两个正交值对象 `Interval` 和 `EnvelopeSpec`；扩展 Pint 单位系统覆盖几何/载荷/环境；用 `Condition` Pydantic 模型替换裸 `dict` 工况输入；从底层逐层（数据 → 计算 → 评分 → 报告 → UI）替换。

**Tech Stack:** Python 3.12 / Pint / Pydantic v2 / stdlib unittest / Streamlit。

**Spec:** `docs/superpowers/specs/2026-05-12-phase1-trustworthy-numbers-design.md`

---

## File Structure

### 新增

- `material_eval/uncertainty.py` — `Interval`, `EnvelopeSpec`, `EnvelopeReport`, `Violation`, 异常类，`CONFIDENCE_SPREAD` 常量
- `material_eval/conditions.py` — `Quantity` Pydantic 包装，`Condition` 工况聚合模型
- `tests/test_uncertainty.py`
- `tests/test_envelope.py`
- `tests/test_conditions.py`
- `tests/test_reporting.py`
- `tests/test_phase1_smoke.py` — MVP 三场景 × in/out-of-envelope 端到端

### 修改

- `material_eval/units.py` — Pint 维度扩展，`normalize_quantity()` 统一入口
- `material_eval/material_property_library.py` — seed schema 升级（向后兼容），多观察聚合为 Interval，加载 `envelope`
- `material_eval/materials.py` — `MaterialCandidate` 字段类型 float → Interval
- `material_eval/computation.py` — 区间算术，`Metric.value` float → Interval
- `material_eval/section_analysis.py` — 输出包装为零宽 Interval
- `material_eval/laminates.py` — 区间算术
- `material_eval/scoring.py` — 数据可信度从 Interval 宽度计算；工况风险从 envelope 余量计算
- `material_eval/report_schema.py` — `interval` 字段，`envelope_report` 字段
- `material_eval/reporting.py` — 区间渲染，工况包络章节，RefusalReport
- `material_eval/evaluation.py` — `Condition` 入参，`validate_envelope`，`EnvelopeRefusal`，refusal 短路
- `material_eval/storage.py` — `envelope_report` 写 payload，`data/refusal_log.jsonl`
- `material_eval/ui_streamlit.py` — 单位下拉，软校验，refusal banner
- `data/seed/material_property_library.json` — 核心 5 材料三点区间 + envelope
- `docs/implementation-log.md` — Phase 1 完成记录

### 关键类型契约（贯穿全 plan）

```python
# uncertainty.py
@dataclass(frozen=True)
class Interval:
    low: float
    typical: float
    high: float
    unit: str
    widened: bool = False

    @classmethod
    def point(cls, value: float, unit: str) -> "Interval": ...
    @classmethod
    def from_confidence(cls, value: float, unit: str, confidence: float) -> "Interval": ...
    def __add__(self, other) -> "Interval": ...
    def __sub__(self, other) -> "Interval": ...
    def __mul__(self, other) -> "Interval": ...
    def __truediv__(self, other) -> "Interval": ...
    def __pow__(self, n: int) -> "Interval": ...
    def relative_width(self) -> float: ...
    def format(self) -> str: ...

CONFIDENCE_SPREAD = ((0.7, 0.05), (0.5, 0.15), (0.0, 0.30))  # (threshold, spread_ratio)

class IntervalError(ValueError): ...
class NegativeWidthError(IntervalError): ...
class UnitMismatchError(IntervalError): ...

@dataclass(frozen=True)
class EnvelopeSpec:
    temperature_C: tuple[float, float] | None = None
    humidity_pct: tuple[float, float] | None = None
    stress_MPa: tuple[float, float] | None = None
    strain_rate_1_per_s: tuple[float, float] | None = None
    fatigue_cycles: tuple[float, float] | None = None
    thickness_mm: tuple[float, float] | None = None
    source: str | None = None
    def check(self, condition: "Condition") -> "EnvelopeReport": ...
    def has_any_axis(self) -> bool: ...

@dataclass(frozen=True)
class Violation:
    axis: str
    input_value: float
    allowed_range: tuple[float, float]
    source: str | None

@dataclass(frozen=True)
class EnvelopeReport:
    violations: tuple[Violation, ...]
    has_declared_envelope: bool
    @property
    def passed(self) -> bool: return not self.violations
```

```python
# conditions.py
class Quantity(BaseModel):
    value: float
    unit: str

class Condition(BaseModel):
    length: Quantity | None = None
    width: Quantity | None = None
    thickness: Quantity | None = None
    height: Quantity | None = None
    diameter: Quantity | None = None
    inner_diameter: Quantity | None = None
    axial_force: Quantity | None = None
    bending_moment: Quantity | None = None
    pressure: Quantity | None = None
    temperature: Quantity | None = None
    humidity: Quantity | None = None
    fatigue_cycles: float | None = None
    strain_rate: Quantity | None = None
    @classmethod
    def from_dimensions(cls, dimensions: dict[str, float], **env) -> "Condition": ...
    def geometry_mm(self) -> dict[str, float]: ...
```

```python
# evaluation.py
@dataclass(frozen=True)
class EvaluationRequest:
    material: MaterialCandidate
    part: PartTemplate
    condition: Condition
    evidence_query: str | None = None
    retrieval_mode: str = "bm25"
    laminate_stack: LaminateStack | None = None

@dataclass(frozen=True)
class EnvelopeRefusal:
    material: MaterialCandidate
    part: PartTemplate
    condition: Condition
    envelope_report: EnvelopeReport
    alternative_materials: tuple[str, ...]
    missing_data: tuple[str, ...]
    refusal_markdown: str
```

所有 task 中出现的类型、方法名严格与此一致。

---

## Task 1: `Interval` 值对象

**Files:**
- Create: `material_eval/uncertainty.py`（先建文件，本任务只填 Interval 部分）
- Test: `tests/test_uncertainty.py`

- [ ] **Step 1: 写第一组失败测试 — 构造与不变量**

`tests/test_uncertainty.py`:

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/bin/python -m unittest tests.test_uncertainty -v
```
Expected: `ImportError: cannot import name 'Interval' from 'material_eval.uncertainty'`

- [ ] **Step 3: 写最小实现满足这组测试**

`material_eval/uncertainty.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


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
    widened: bool = False

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


def _spread_for_confidence(confidence: float) -> float:
    for threshold, spread in CONFIDENCE_SPREAD:
        if confidence >= threshold:
            return spread
    return CONFIDENCE_SPREAD[-1][1]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
.venv/bin/python -m unittest tests.test_uncertainty -v
```
Expected: 7 passed.

- [ ] **Step 5: 加算术测试**

追加到 `tests/test_uncertainty.py`:

```python
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
```

- [ ] **Step 6: 实现算术（在 `material_eval/uncertainty.py` 类 `Interval` 中追加方法）**

```python
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
        if self.low >= 0 or n % 2 == 1:
            return Interval(self.low ** n, self.typical ** n, self.high ** n, _pow_unit(self.unit, n))
        endpoints = (self.low ** n, self.high ** n)
        return Interval(low=min(endpoints), typical=self.typical ** n, high=max(endpoints), unit=_pow_unit(self.unit, n))

    def relative_width(self) -> float:
        if self.typical == 0:
            return 0.0
        return (self.high - self.low) / abs(self.typical)


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
```

- [ ] **Step 7: 运行测试确认通过**

```bash
.venv/bin/python -m unittest tests.test_uncertainty -v
```
Expected: 18 passed.

- [ ] **Step 8: 加 `format()` 渲染方法和测试**

追加测试：

```python
class IntervalFormatTest(unittest.TestCase):
    def test_format_large_takes_integer(self):
        iv = Interval(low=1110.4, typical=1234.5, high=1380.7, unit="MPa")
        self.assertEqual(iv.format(), "1110 / 1234 / 1381 MPa")

    def test_format_point_collapses(self):
        iv = Interval.point(42.0, "kg")
        self.assertEqual(iv.format(), "42 kg")

    def test_format_mid_range_three_sigfig(self):
        iv = Interval(low=1.234, typical=2.345, high=3.456, unit="GPa")
        self.assertEqual(iv.format(), "1.23 / 2.34 / 3.46 GPa")

    def test_format_small_uses_scientific(self):
        iv = Interval(low=1.2e-3, typical=2.3e-3, high=3.4e-3, unit="m")
        self.assertEqual(iv.format(), "1.20e-03 / 2.30e-03 / 3.40e-03 m")
```

追加实现到 Interval 类：

```python
    def format(self) -> str:
        if self.low == self.typical == self.high:
            return f"{_fmt_num(self.typical)} {self.unit}".strip()
        return (
            f"{_fmt_num(self.low)} / {_fmt_num(self.typical)} / {_fmt_num(self.high)} {self.unit}"
        ).strip()


def _fmt_num(x: float) -> str:
    if x == 0:
        return "0"
    abs_x = abs(x)
    if abs_x >= 1000:
        return f"{round(x):d}"
    if abs_x >= 0.1:
        return f"{x:.3g}"
    return f"{x:.2e}"
```

- [ ] **Step 9: 运行全部 Interval 测试**

```bash
.venv/bin/python -m unittest tests.test_uncertainty -v
```
Expected: 22 passed.

- [ ] **Step 10: Commit**

```bash
git add material_eval/uncertainty.py tests/test_uncertainty.py
git commit -m "feat(uncertainty): add Interval value object with arithmetic and formatting"
```

---

## Task 2: `EnvelopeSpec` / `EnvelopeReport`

**Files:**
- Modify: `material_eval/uncertainty.py`（追加 EnvelopeSpec 等）
- Test: `tests/test_envelope.py`

注：本任务先用 stub Condition（dict 形式）测试 EnvelopeSpec.check，避免与 Task 4 互相依赖。Task 4 完成后会有一次小整合。

- [ ] **Step 1: 写失败测试**

`tests/test_envelope.py`:

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/bin/python -m unittest tests.test_envelope -v
```
Expected: ImportError.

- [ ] **Step 3: 实现 EnvelopeSpec / Violation / EnvelopeReport，追加到 `material_eval/uncertainty.py`**

```python
_ENVELOPE_AXES: tuple[str, ...] = (
    "temperature_C",
    "humidity_pct",
    "stress_MPa",
    "strain_rate_1_per_s",
    "fatigue_cycles",
    "thickness_mm",
)


@dataclass(frozen=True)
class Violation:
    axis: str
    input_value: float
    allowed_range: tuple[float, float]
    source: str | None = None


@dataclass(frozen=True)
class EnvelopeReport:
    violations: tuple[Violation, ...]
    has_declared_envelope: bool

    @property
    def passed(self) -> bool:
        return not self.violations


@dataclass(frozen=True)
class EnvelopeSpec:
    temperature_C: tuple[float, float] | None = None
    humidity_pct: tuple[float, float] | None = None
    stress_MPa: tuple[float, float] | None = None
    strain_rate_1_per_s: tuple[float, float] | None = None
    fatigue_cycles: tuple[float, float] | None = None
    thickness_mm: tuple[float, float] | None = None
    source: str | None = None

    def has_any_axis(self) -> bool:
        return any(getattr(self, axis) is not None for axis in _ENVELOPE_AXES)

    def check(self, condition) -> EnvelopeReport:
        violations: list[Violation] = []
        inputs = condition.envelope_axes()
        for axis in _ENVELOPE_AXES:
            allowed: tuple[float, float] | None = getattr(self, axis)
            if allowed is None:
                continue
            actual = inputs.get(axis)
            if actual is None:
                continue
            lo, hi = allowed
            if actual < lo or actual > hi:
                violations.append(
                    Violation(axis=axis, input_value=float(actual), allowed_range=(lo, hi), source=self.source)
                )
        return EnvelopeReport(violations=tuple(violations), has_declared_envelope=self.has_any_axis())
```

- [ ] **Step 4: 运行测试确认通过**

```bash
.venv/bin/python -m unittest tests.test_envelope -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add material_eval/uncertainty.py tests/test_envelope.py
git commit -m "feat(uncertainty): add EnvelopeSpec and EnvelopeReport with violation detection"
```

---

## Task 3: 扩展 `units.py` 覆盖新维度

**Files:**
- Modify: `material_eval/units.py`
- Modify: `tests/test_units.py`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_units.py`:

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/bin/python -m unittest tests.test_units -v
```
Expected: ImportError on `normalize_quantity`.

- [ ] **Step 3: 实现**

在 `material_eval/units.py` 末尾追加：

```python
_DIMENSION_CANONICAL: dict[str, str] = {
    "length": "mm",
    "force": "N",
    "moment": "N*m",
    "stress": "MPa",
    "pressure": "MPa",
    "temperature": "degC",
    "humidity": "%RH",
    "strain_rate": "1/s",
}

_DIMENSION_ALIASES: dict[str, dict[str, str]] = {
    "length": {
        "m": "meter", "mm": "millimeter", "cm": "centimeter", "in": "inch", "inch": "inch",
    },
    "force": {
        "N": "newton", "kN": "kilonewton", "lbf": "pound_force",
    },
    "moment": {
        "N*m": "newton * meter", "N·m": "newton * meter", "Nm": "newton * meter",
    },
    "stress": {
        "Pa": "pascal", "kPa": "kilopascal", "MPa": "megapascal", "GPa": "gigapascal",
        "N/mm^2": "newton / millimeter ** 2", "N/mm2": "newton / millimeter ** 2", "psi": "psi",
    },
    "temperature": {
        "degC": "degC", "°C": "degC", "C": "degC", "K": "kelvin", "kelvin": "kelvin",
    },
    "humidity": {"%RH": "%RH", "%": "%RH"},
    "strain_rate": {"1/s": "1 / second", "/s": "1 / second", "s^-1": "1 / second"},
}


def _resolve_unit(dimension: str, unit: str) -> str:
    aliases = _DIMENSION_ALIASES.get(dimension, {})
    return aliases.get(unit.strip(), unit.strip())


def normalize_quantity(value: float, unit: str, dimension: str) -> tuple[float, str]:
    if dimension == "humidity":
        # Pint doesn't model %RH; pass through with a literal canonical tag.
        return float(value), _DIMENSION_CANONICAL["humidity"]
    if dimension not in _DIMENSION_CANONICAL:
        raise UnitCompatibilityError(f"Unknown dimension: {dimension!r}")
    canonical = _DIMENSION_CANONICAL[dimension]
    canonical_pint = _resolve_unit(dimension, canonical)
    source_pint = _resolve_unit(dimension, unit)
    try:
        if dimension == "temperature":
            quantity = _UNIT_REGISTRY.Quantity(float(value), source_pint)
            normalized = quantity.to(canonical_pint)
        else:
            quantity = float(value) * _UNIT_REGISTRY(source_pint)
            normalized = quantity.to(canonical_pint)
    except pint.errors.DimensionalityError as exc:
        raise UnitCompatibilityError(
            f"Unit '{unit}' is not compatible with dimension '{dimension}' canonical '{canonical}'."
        ) from exc
    except Exception as exc:
        raise UnitCompatibilityError(f"Could not parse unit '{unit}' for dimension '{dimension}'.") from exc
    return float(normalized.magnitude), canonical
```

- [ ] **Step 4: 运行测试确认通过**

```bash
.venv/bin/python -m unittest tests.test_units -v
```
Expected: 13 passed (4 旧 + 9 新).

- [ ] **Step 5: Commit**

```bash
git add material_eval/units.py tests/test_units.py
git commit -m "feat(units): extend Pint coverage to length/force/moment/temp/humidity/strain-rate via normalize_quantity"
```

---

## Task 4: `Condition` Pydantic 模型

**Files:**
- Create: `material_eval/conditions.py`
- Test: `tests/test_conditions.py`

- [ ] **Step 1: 写失败测试**

`tests/test_conditions.py`:

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
.venv/bin/python -m unittest tests.test_conditions -v
```
Expected: ImportError.

- [ ] **Step 3: 实现 `material_eval/conditions.py`**

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from material_eval.units import normalize_quantity


class Quantity(BaseModel):
    value: float
    unit: str

    model_config = {"frozen": True}


def _to_canonical(q: Quantity | None, dimension: str) -> float | None:
    if q is None:
        return None
    value, _ = normalize_quantity(q.value, q.unit, dimension)
    return value


class Condition(BaseModel):
    length: Quantity | None = None
    width: Quantity | None = None
    thickness: Quantity | None = None
    height: Quantity | None = None
    diameter: Quantity | None = None
    inner_diameter: Quantity | None = None
    axial_force: Quantity | None = None
    bending_moment: Quantity | None = None
    pressure: Quantity | None = None
    temperature: Quantity | None = None
    humidity: Quantity | None = None
    fatigue_cycles: float | None = None
    strain_rate: Quantity | None = None

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    @classmethod
    def from_dimensions(cls, dimensions: dict[str, float], **env: Any) -> "Condition":
        """Compat shim: old code passes dict[str, float] in mm."""
        mapped: dict[str, Any] = {}
        for key in ("length", "width", "thickness", "height", "diameter", "inner_diameter"):
            if key in dimensions:
                mapped[key] = Quantity(value=float(dimensions[key]), unit="mm")
        mapped.update(env)
        return cls(**mapped)

    def geometry_mm(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for key in ("length", "width", "thickness", "height", "diameter", "inner_diameter"):
            q = getattr(self, key)
            if q is None:
                continue
            value, _ = normalize_quantity(q.value, q.unit, "length")
            out[key] = value
        return out

    def envelope_axes(self) -> dict[str, float | None]:
        return {
            "temperature_C": _to_canonical(self.temperature, "temperature"),
            "humidity_pct": _to_canonical(self.humidity, "humidity"),
            "stress_MPa": _to_canonical(self.pressure, "stress"),
            "strain_rate_1_per_s": _to_canonical(self.strain_rate, "strain_rate"),
            "fatigue_cycles": float(self.fatigue_cycles) if self.fatigue_cycles is not None else None,
            "thickness_mm": _to_canonical(self.thickness, "length"),
        }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
.venv/bin/python -m unittest tests.test_conditions -v
```
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add material_eval/conditions.py tests/test_conditions.py
git commit -m "feat(conditions): add Condition pydantic model with unit-aware envelope_axes/geometry_mm"
```

---

## Task 5: 材料属性库 seed schema 升级（向后兼容）

**Files:**
- Modify: `material_eval/material_property_library.py`
- Modify: `tests/test_material_property_library.py`

读取层先升级，**不动 seed 文件**。逻辑：
1. 单点 `"value": x` 与新 `"value": {"low":..., "typical":..., "high":...}` 都解析为 Interval。
2. 多个 observation 合并为单 Interval：`low=min(all)`, `high=max(all)`, `typical=` 最高 confidence 那条的 typical。
3. 顶层新字段 `envelope` 解析为 `EnvelopeSpec`，缺省 None。

- [ ] **Step 1: 阅读现有实现**

```bash
.venv/bin/cat material_eval/material_property_library.py
```

- [ ] **Step 2: 写失败测试**

追加到 `tests/test_material_property_library.py`（不存在就建）：

```python
import json
import tempfile
import unittest
from pathlib import Path

from material_eval.material_property_library import load_material_library
from material_eval.uncertainty import EnvelopeSpec, Interval


SAMPLE_SEED = {
    "version": "test",
    "notes": "test",
    "materials": [
        {"id": "matA", "name": "材料 A", "category": "test", "form": "x", "process": "y"},
        {"id": "matB", "name": "材料 B", "category": "test", "form": "x", "process": "y",
         "envelope": {"temperature_C": [-40, 120], "thickness_mm": [0.5, 10.0],
                      "source": "supplier datasheet"}},
    ],
    "observations": [
        # Legacy single-point form
        {"material_id": "matA", "property_name": "density_g_cm3", "value": 1.8,
         "unit": "g/cm^3", "test_condition": "RT", "source_type": "ref",
         "source_label": "seed", "confidence": 0.6},
        # New three-point form
        {"material_id": "matB", "property_name": "density_g_cm3",
         "value": {"low": 1.35, "typical": 1.40, "high": 1.45},
         "unit": "g/cm^3", "test_condition": "RT", "source_type": "ref",
         "source_label": "seed", "confidence": 0.7},
        # Multi-observation aggregation
        {"material_id": "matB", "property_name": "tensile_strength_mpa", "value": 90,
         "unit": "MPa", "test_condition": "RT high", "source_type": "ref",
         "source_label": "seedH", "confidence": 0.7},
        {"material_id": "matB", "property_name": "tensile_strength_mpa", "value": 70,
         "unit": "MPa", "test_condition": "RT low", "source_type": "ref",
         "source_label": "seedL", "confidence": 0.4},
    ],
}


class MaterialLibraryLoadingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(SAMPLE_SEED, self.tmp)
        self.tmp.close()
        self.lib = load_material_library(Path(self.tmp.name))

    def test_loads_two_materials(self):
        self.assertEqual({m.id for m in self.lib.materials}, {"matA", "matB"})

    def test_legacy_single_point_becomes_zero_width_expanded_by_confidence(self):
        matA = self.lib.get("matA")
        density = matA.property("density_g_cm3")
        self.assertIsInstance(density, Interval)
        # confidence 0.6 -> ±15%
        self.assertAlmostEqual(density.typical, 1.8)
        self.assertAlmostEqual(density.low, 1.53)
        self.assertAlmostEqual(density.high, 2.07)

    def test_three_point_form_preserved(self):
        matB = self.lib.get("matB")
        density = matB.property("density_g_cm3")
        self.assertEqual((density.low, density.typical, density.high), (1.35, 1.40, 1.45))

    def test_multi_observation_aggregates(self):
        matB = self.lib.get("matB")
        ts = matB.property("tensile_strength_mpa")
        self.assertAlmostEqual(ts.low, 70.0)
        self.assertAlmostEqual(ts.high, 90.0)
        # typical = highest-confidence observation's value
        self.assertAlmostEqual(ts.typical, 90.0)

    def test_envelope_loaded(self):
        matB = self.lib.get("matB")
        env: EnvelopeSpec = matB.envelope
        self.assertEqual(env.temperature_C, (-40.0, 120.0))
        self.assertEqual(env.thickness_mm, (0.5, 10.0))
        self.assertEqual(env.source, "supplier datasheet")

    def test_envelope_absent_is_none(self):
        matA = self.lib.get("matA")
        self.assertIsNone(matA.envelope)
```

- [ ] **Step 3: 运行测试确认失败**

```bash
.venv/bin/python -m unittest tests.test_material_property_library -v
```
Expected: 失败（旧接口可能不同 / 新接口未实现）。

- [ ] **Step 4: 重写 `material_eval/material_property_library.py`**

完整内容：

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from material_eval.uncertainty import EnvelopeSpec, Interval
from material_eval.units import canonical_unit_for_property, normalize_material_property


@dataclass(frozen=True)
class PropertyObservation:
    property_name: str
    value: Interval
    test_condition: str
    source_type: str
    source_label: str
    confidence: float


@dataclass(frozen=True)
class MaterialEntry:
    id: str
    name: str
    category: str
    form: str
    process: str
    envelope: EnvelopeSpec | None
    observations: tuple[PropertyObservation, ...]

    def property(self, name: str) -> Interval | None:
        observations = [o for o in self.observations if o.property_name == name]
        if not observations:
            return None
        if len(observations) == 1:
            return observations[0].value
        return _aggregate_observations(observations)


@dataclass(frozen=True)
class MaterialLibrary:
    materials: tuple[MaterialEntry, ...]

    def get(self, material_id: str) -> MaterialEntry:
        for m in self.materials:
            if m.id == material_id:
                return m
        raise KeyError(material_id)


DEFAULT_SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed" / "material_property_library.json"


def load_material_library(path: Path | None = None) -> MaterialLibrary:
    seed_path = path or DEFAULT_SEED_PATH
    raw = json.loads(seed_path.read_text(encoding="utf-8"))
    materials_meta = {m["id"]: m for m in raw["materials"]}
    grouped: dict[str, list[PropertyObservation]] = {mid: [] for mid in materials_meta}
    for obs in raw["observations"]:
        material_id = obs["material_id"]
        property_name = obs["property_name"]
        interval = _parse_value(obs, property_name)
        grouped.setdefault(material_id, []).append(
            PropertyObservation(
                property_name=property_name,
                value=interval,
                test_condition=obs.get("test_condition", ""),
                source_type=obs.get("source_type", ""),
                source_label=obs.get("source_label", ""),
                confidence=float(obs.get("confidence", 0.0)),
            )
        )
    materials: list[MaterialEntry] = []
    for mid, meta in materials_meta.items():
        envelope_payload = meta.get("envelope")
        envelope = _parse_envelope(envelope_payload) if envelope_payload else None
        materials.append(
            MaterialEntry(
                id=mid,
                name=meta["name"],
                category=meta.get("category", ""),
                form=meta.get("form", ""),
                process=meta.get("process", ""),
                envelope=envelope,
                observations=tuple(grouped.get(mid, ())),
            )
        )
    return MaterialLibrary(materials=tuple(materials))


def _parse_value(obs: dict[str, Any], property_name: str) -> Interval:
    canonical = canonical_unit_for_property(property_name)
    raw = obs["value"]
    unit = obs.get("unit", canonical)
    if isinstance(raw, dict):
        low_n = normalize_material_property(property_name, float(raw["low"]), unit).value
        typ_n = normalize_material_property(property_name, float(raw["typical"]), unit).value
        high_n = normalize_material_property(property_name, float(raw["high"]), unit).value
        return Interval(low=low_n, typical=typ_n, high=high_n, unit=canonical)
    point = normalize_material_property(property_name, float(raw), unit).value
    confidence = float(obs.get("confidence", 0.0))
    return Interval.from_confidence(point, canonical, confidence)


def _aggregate_observations(observations: list[PropertyObservation]) -> Interval:
    unit = observations[0].value.unit
    lows = [o.value.low for o in observations]
    highs = [o.value.high for o in observations]
    best = max(observations, key=lambda o: o.confidence)
    return Interval(low=min(lows), typical=best.value.typical, high=max(highs), unit=unit)


def _parse_envelope(payload: dict[str, Any]) -> EnvelopeSpec:
    def axis(key: str) -> tuple[float, float] | None:
        v = payload.get(key)
        if v is None:
            return None
        return (float(v[0]), float(v[1]))

    return EnvelopeSpec(
        temperature_C=axis("temperature_C"),
        humidity_pct=axis("humidity_pct"),
        stress_MPa=axis("stress_MPa"),
        strain_rate_1_per_s=axis("strain_rate_1_per_s"),
        fatigue_cycles=axis("fatigue_cycles"),
        thickness_mm=axis("thickness_mm"),
        source=payload.get("source"),
    )
```

- [ ] **Step 5: 运行新测试**

```bash
.venv/bin/python -m unittest tests.test_material_property_library -v
```
Expected: 6 passed.

- [ ] **Step 6: 跑全量测试确认旧用例还存在并通过**

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v 2>&1 | tail -40
```
若旧 `test_material_property_library.py` 已存在并对老接口断言，旧用例会失败。**修复策略**：把旧用例改成新接口（同一文件，删旧 case 替换为新 case 后回到 Step 5 重跑）。

- [ ] **Step 7: Commit**

```bash
git add material_eval/material_property_library.py tests/test_material_property_library.py
git commit -m "feat(material-lib): parse three-point intervals + envelope, aggregate multi-observations"
```

---

## Task 6: `MaterialCandidate` 字段类型升级为 Interval

**Files:**
- Modify: `material_eval/materials.py`

**注意**：`MaterialCandidate` 是 UI 和 computation 共用的核心数据类型。改完类型后调用方需要在 Task 7+ 跟着改。

- [ ] **Step 1: 写失败测试**

`tests/test_materials.py`（新建）:

```python
import unittest

from material_eval.materials import (
    MaterialCandidate,
    build_composite_material,
    build_single_material,
)
from material_eval.uncertainty import Interval


class MaterialCandidateIntervalTest(unittest.TestCase):
    def test_single_material_stores_intervals(self):
        m = build_single_material(
            name="测试材料",
            category="metal",
            density_g_cm3=Interval.point(2.7, "g/cm^3"),
            tensile_strength_mpa=Interval(low=200, typical=250, high=300, unit="MPa"),
            elastic_modulus_gpa=Interval.point(70.0, "GPa"),
        )
        self.assertIsInstance(m.density_g_cm3, Interval)
        self.assertEqual(m.tensile_strength_mpa.typical, 250)
        self.assertEqual(m.elastic_modulus_gpa.unit, "GPa")
        self.assertEqual(m.name, "测试材料")

    def test_specific_strength_uses_typical(self):
        m = build_single_material(
            name="x", category="metal",
            density_g_cm3=Interval.point(2.0, "g/cm^3"),
            tensile_strength_mpa=Interval.point(400.0, "MPa"),
            elastic_modulus_gpa=Interval.point(70.0, "GPa"),
        )
        self.assertAlmostEqual(m.specific_strength_typical, 200.0)

    def test_composite_rule_of_mixtures_with_intervals(self):
        m = build_composite_material(
            matrix_name="环氧", fiber_name="碳纤维",
            fiber_volume_fraction=0.6,
            matrix_density=Interval.point(1.2, "g/cm^3"),
            matrix_strength=Interval.point(80.0, "MPa"),
            matrix_modulus=Interval.point(3.5, "GPa"),
            fiber_density=Interval.point(1.8, "g/cm^3"),
            fiber_strength=Interval.point(4000.0, "MPa"),
            fiber_modulus=Interval.point(230.0, "GPa"),
        )
        # density = 0.4 * 1.2 + 0.6 * 1.8 = 0.48 + 1.08 = 1.56
        self.assertAlmostEqual(m.density_g_cm3.typical, 1.56)
        # modulus = 0.4 * 3.5 + 0.6 * 230 = 1.4 + 138 = 139.4
        self.assertAlmostEqual(m.elastic_modulus_gpa.typical, 139.4)
```

- [ ] **Step 2: 运行确认失败**

```bash
.venv/bin/python -m unittest tests.test_materials -v
```

- [ ] **Step 3: 改写 `material_eval/materials.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from material_eval.uncertainty import Interval


@dataclass(frozen=True)
class MaterialCandidate:
    name: str
    category: str
    density_g_cm3: Interval
    tensile_strength_mpa: Interval
    elastic_modulus_gpa: Interval
    notes: str = ""

    @property
    def specific_strength_typical(self) -> float:
        if self.density_g_cm3.typical == 0:
            return 0.0
        return self.tensile_strength_mpa.typical / self.density_g_cm3.typical

    @property
    def specific_modulus_typical(self) -> float:
        if self.density_g_cm3.typical == 0:
            return 0.0
        return self.elastic_modulus_gpa.typical / self.density_g_cm3.typical


def _as_interval(value: Interval | float, unit: str) -> Interval:
    if isinstance(value, Interval):
        return value
    return Interval.point(float(value), unit)


def build_single_material(
    *,
    name: str,
    category: str,
    density_g_cm3: Interval | float,
    tensile_strength_mpa: Interval | float,
    elastic_modulus_gpa: Interval | float,
) -> MaterialCandidate:
    return MaterialCandidate(
        name=name.strip() or "候选均质材料",
        category=category,
        density_g_cm3=_as_interval(density_g_cm3, "g/cm^3"),
        tensile_strength_mpa=_as_interval(tensile_strength_mpa, "MPa"),
        elastic_modulus_gpa=_as_interval(elastic_modulus_gpa, "GPa"),
        notes="用户输入的单一均质材料参数。",
    )


def build_composite_material(
    *,
    matrix_name: str,
    fiber_name: str,
    fiber_volume_fraction: float,
    matrix_density: Interval | float,
    matrix_strength: Interval | float,
    matrix_modulus: Interval | float,
    fiber_density: Interval | float,
    fiber_strength: Interval | float,
    fiber_modulus: Interval | float,
) -> MaterialCandidate:
    vf = max(0.0, min(1.0, float(fiber_volume_fraction)))
    vm = 1.0 - vf
    md = _as_interval(matrix_density, "g/cm^3")
    ms = _as_interval(matrix_strength, "MPa")
    mm = _as_interval(matrix_modulus, "GPa")
    fd = _as_interval(fiber_density, "g/cm^3")
    fs = _as_interval(fiber_strength, "MPa")
    fm = _as_interval(fiber_modulus, "GPa")
    density = md * vm + fd * vf
    strength = ms * vm + fs * vf
    modulus = mm * vm + fm * vf
    return MaterialCandidate(
        name=f"{fiber_name}增强{matrix_name}",
        category="复合/杂化材料体系",
        density_g_cm3=density,
        tensile_strength_mpa=strength,
        elastic_modulus_gpa=modulus,
        notes=(
            "基于线性混合定律的 MVP 初筛估算；尚未考虑铺层方向、界面、孔隙率、"
            "成型缺陷、疲劳和环境衰减。"
        ),
    )
```

- [ ] **Step 4: 运行新测试通过**

```bash
.venv/bin/python -m unittest tests.test_materials -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit（**全量测试此刻预期会因 computation 等下游模块未改造而失败，是预期中的**）**

```bash
git add material_eval/materials.py tests/test_materials.py
git commit -m "feat(materials): switch MaterialCandidate properties to Interval"
```

---

## Task 7: `computation.py` / `section_analysis.py` 区间化

**Files:**
- Modify: `material_eval/computation.py`
- Modify: `material_eval/section_analysis.py`
- Modify: `tests/test_computation.py`
- Modify: `tests/test_section_analysis.py`

**核心改造**：
- `Metric.value: float → Interval`
- 所有公式用 Interval 算术；输入零宽 → 输出零宽（旧用例数值仍成立）
- `section_analysis` 返回值字段升级为 Interval（零宽）
- `calculate_part(part, material, condition)` —— 入参从 `dims: dict[str, float]` 改为 `condition: Condition`

- [ ] **Step 1: 改 `section_analysis.py`**

读取现状：

```bash
.venv/bin/cat material_eval/section_analysis.py | head -80
```

修改：把 `SectionProperties` 数据类的 `area_mm2: float`, `inertia_x_mm4: float` 替换为 Interval；构造函数包装为零宽 `Interval.point(value, unit)`；`unit` 分别为 `"mm**2"`, `"mm**4"`。

具体伪代码（按实际现状对应修改）：

```python
from material_eval.uncertainty import Interval

@dataclass(frozen=True)
class SectionProperties:
    area_mm2: Interval
    inertia_x_mm4: Interval
    method: str
    warnings: tuple[str, ...] = ()
```

每个返回点把原 float 包装成 `Interval.point(value, "mm**2")` / `"mm**4"`。

- [ ] **Step 2: 改 `computation.py`**

完整替换 `Metric` 定义和所有计算函数：

```python
from __future__ import annotations

from dataclasses import dataclass, field

from material_eval.catalog import PartTemplate
from material_eval.conditions import Condition
from material_eval.materials import MaterialCandidate
from material_eval.section_analysis import (
    SectionProperties,
    analyze_hollow_circular_section,
    analyze_i_section,
    analyze_rectangular_section,
)
from material_eval.uncertainty import Interval


@dataclass(frozen=True)
class Metric:
    name: str
    value: Interval
    description: str

    @property
    def unit(self) -> str:
        return self.value.unit


@dataclass(frozen=True)
class CalculationResult:
    topology: str
    metrics: tuple[Metric, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    version: str = "mvp_calc_v2_interval"

    def as_rows(self) -> list[dict[str, str]]:
        return [
            {
                "指标": metric.name,
                "区间": metric.value.format(),
                "说明": metric.description,
            }
            for metric in self.metrics
        ]


def calculate_part(part: PartTemplate, material: MaterialCandidate, condition: Condition) -> CalculationResult:
    dims = condition.geometry_mm()
    topology = part.topology
    if topology == "BEAM":
        return _calculate_beam(material, dims)
    if topology == "I_BEAM":
        return _calculate_i_beam(material, dims)
    if topology == "PLATE":
        return _calculate_plate(material, dims)
    if topology == "CORRUGATED":
        return _calculate_corrugated(material, dims)
    if topology == "STRAP":
        return _calculate_strap(material, dims)
    return CalculationResult(
        topology=topology,
        metrics=(),
        assumptions=("该拓扑尚未实现计算模块。",),
        warnings=(f"Unsupported topology: {topology}",),
    )


def _density_kg_per_mm3(material: MaterialCandidate) -> Interval:
    # g/cm^3 * 1e-6 -> kg/mm^3 (numerically). We keep unit string semantic.
    return material.density_g_cm3 * 1e-6


def _elastic_modulus_mpa(material: MaterialCandidate) -> Interval:
    return material.elastic_modulus_gpa * 1000.0


def _base_assumptions() -> tuple[str, ...]:
    return (
        "所有尺寸输入单位为 mm；强度单位 MPa = N/mm^2；密度单位 g/cm^3。",
        "MVP 计算用于内部研发初筛，不替代 FEA、台架实验或行业准入认证。",
        "材料按均质、线弹性、各向同性处理；复合材料方向性暂未进入该模块。",
        "数值以三点区间 (low / typical / high) 表达，反映材料属性不确定度的传播。",
    )


def _section_assumption(section: SectionProperties) -> tuple[str, ...]:
    if section.method == "sectionproperties":
        return ("截面面积和惯性矩使用 sectionproperties 开源截面分析库计算。",)
    return ("截面面积和惯性矩使用闭式公式计算；sectionproperties 不可用时自动回退。",)


def _i(value: float, unit: str) -> Interval:
    return Interval.point(value, unit)


def _calculate_beam(material: MaterialCandidate, dims: dict[str, float]) -> CalculationResult:
    length = dims["length"]
    diameter = dims["diameter"]
    thickness = dims["thickness"]
    warnings: list[str] = []
    if thickness * 2 >= diameter:
        warnings.append("壁厚已接近或超过外径一半，按最小内径 0.1 mm 进行初筛，建议修正几何输入。")

    section = analyze_hollow_circular_section(diameter, thickness)
    area = section.area_mm2                                   # Interval mm**2
    inertia = section.inertia_x_mm4                           # Interval mm**4
    volume = area * length                                    # Interval mm**3
    weight = volume * _density_kg_per_mm3(material)           # Interval kg-ish
    half_d = _i(diameter / 2.0, "mm")
    bending_load = (
        material.tensile_strength_mpa * inertia / half_d / _i(length, "mm")
        if length > 0
        else _i(0.0, "N")
    )
    axial_load = material.tensile_strength_mpa * area * 0.8
    e_mpa = _elastic_modulus_mpa(material)
    deflection = (
        bending_load * (_i(length, "mm") ** 3) / (e_mpa * inertia * 3.0)
        if inertia.typical > 0 and material.elastic_modulus_gpa.typical > 0
        else _i(0.0, "mm")
    )

    return CalculationResult(
        topology="BEAM",
        metrics=(
            Metric("结构总重量估算", _retag(weight, "kg"), "按薄壁/厚壁圆管体积和密度估算。"),
            Metric("悬臂抗弯极限初筛", _retag(bending_load, "N"), "按根部弯曲正应力达到抗拉强度估算。"),
            Metric("轴向承载初筛", _retag(axial_load, "N"), "按截面积和 0.8 折减系数估算。"),
            Metric("端部弹性挠度估算", _retag(deflection, "mm"), "按悬臂梁小变形公式估算。"),
        ),
        assumptions=_base_assumptions() + _section_assumption(section)
        + ("圆管视作等截面悬臂梁；未考虑局部屈曲、连接、冲击和疲劳。",),
        warnings=tuple(warnings) + section.warnings,
    )


def _retag(iv: Interval, unit: str) -> Interval:
    """Rename derived interval's unit to engineering-friendly tag (numeric value unchanged)."""
    return Interval(low=iv.low, typical=iv.typical, high=iv.high, unit=unit, widened=iv.widened)


# _calculate_i_beam, _calculate_plate, _calculate_corrugated, _calculate_strap —
# 同样的改造模式：用 Interval 算术替换 float 算术，用 _retag 修正最终单位标签。
# 见 Step 3。
```

- [ ] **Step 3: 把剩余四个 `_calculate_*` 按同样模式改完**

每个函数遵循统一模式：
1. 把 `material.X` 直接使用（已是 Interval）。
2. 几何尺寸 dims 是 float（来自 `condition.geometry_mm()`），需要时用 `_i(value, unit)` 包成零宽 Interval 参与算术。
3. 最终 `Metric(...).value` 用 `_retag(iv, "kg" / "N" / "mm" / "J")` 给一个干净的单位字符串。

实现细节参照 §3.5 Spec —— 由 executor 在执行本步骤时严格按既有公式重写。

- [ ] **Step 4: 更新 `tests/test_computation.py`**

把所有断言改为对 `metric.value.typical` 比较；并新增一个区间宽度测试：

```python
class IntervalCalculationTest(unittest.TestCase):
    def _candidate_with_uncertainty(self):
        from material_eval.materials import MaterialCandidate
        from material_eval.uncertainty import Interval
        return MaterialCandidate(
            name="t", category="x",
            density_g_cm3=Interval(low=2.6, typical=2.7, high=2.8, unit="g/cm^3"),
            tensile_strength_mpa=Interval(low=200.0, typical=250.0, high=300.0, unit="MPa"),
            elastic_modulus_gpa=Interval(low=68.0, typical=70.0, high=72.0, unit="GPa"),
        )

    def test_strap_tensile_widens_with_strength_uncertainty(self):
        from material_eval.computation import calculate_part
        from material_eval.conditions import Condition, Quantity
        from material_eval.catalog import PartTemplate
        part = PartTemplate(domain="t", name="t", topology="STRAP")
        condition = Condition.from_dimensions({"length": 1000.0, "width": 30.0, "thickness": 2.0})
        result = calculate_part(part, self._candidate_with_uncertainty(), condition)
        tensile = next(m for m in result.metrics if "拉断" in m.name)
        # area = 60 mm**2, tensile = strength * area
        self.assertAlmostEqual(tensile.value.typical, 250.0 * 60, places=2)
        self.assertAlmostEqual(tensile.value.low, 200.0 * 60, places=2)
        self.assertAlmostEqual(tensile.value.high, 300.0 * 60, places=2)
```

- [ ] **Step 5: 更新 `tests/test_section_analysis.py` 的断言用 `.typical`**

跑测试逐项修复：

```bash
.venv/bin/python -m unittest tests.test_computation tests.test_section_analysis -v
```

- [ ] **Step 6: Commit**

```bash
git add material_eval/computation.py material_eval/section_analysis.py tests/test_computation.py tests/test_section_analysis.py
git commit -m "feat(computation): switch Metric value and section properties to Interval arithmetic"
```

---

## Task 8: `laminates.py` 区间化

**Files:**
- Modify: `material_eval/laminates.py`
- Modify: `tests/test_laminates.py`

- [ ] **Step 1: 读现状**

```bash
.venv/bin/cat material_eval/laminates.py | head -60
```

- [ ] **Step 2: 把 `LaminateResult` 的等效 Ex/Ey/Gxy 字段类型从 `float` 改为 `Interval`**

CLT A 矩阵的计算依赖每层 `E1/E2/G12/ν12`。本期：

- 输入 `LaminateStack.layers` 中的每层属性是 `float`（保持，避免动 UI 输入侧）。
- 内部计算时把每个标量包成 `Interval.point(...)`，A 矩阵元素是 Interval。
- 等效模量 `Ex = 1 / (h * A_inv[0][0])` 中的 `h` 是 float，`A_inv` 是 Interval 矩阵 → 等效结果是 Interval。
- 现有 CLT 函数若用 numpy 实现，需要替换为纯 Python 区间 2x2 / 3x3 矩阵求逆（公式简单：3x3 用 adjugate 法）。

实现要点：在 `material_eval/laminates.py` 增加 `_invert_3x3_interval(matrix)` 辅助函数。详细公式 executor 按教材实现即可，需保证：
- 输入 `[[Interval; 3]; 3]`
- 输出 `[[Interval; 3]; 3]`
- 用 `Interval.__add__/__sub__/__mul__/__truediv__` + `Interval.point` 完成

- [ ] **Step 3: 改测试**

```python
class LaminateIntervalTest(unittest.TestCase):
    def test_zero_uncertainty_input_gives_zero_width_output(self):
        from material_eval.laminates import LaminateStack, LaminateLayer, analyze_laminate
        stack = LaminateStack(layers=(
            LaminateLayer(angle_deg=0, thickness_mm=0.125, E1_gpa=140, E2_gpa=10, G12_gpa=5, nu12=0.3),
            LaminateLayer(angle_deg=90, thickness_mm=0.125, E1_gpa=140, E2_gpa=10, G12_gpa=5, nu12=0.3),
        ))
        result = analyze_laminate(stack)
        self.assertEqual(result.ex_gpa.low, result.ex_gpa.high)
```

- [ ] **Step 4: 运行**

```bash
.venv/bin/python -m unittest tests.test_laminates -v
```

修复直到所有用例通过。

- [ ] **Step 5: Commit**

```bash
git add material_eval/laminates.py tests/test_laminates.py
git commit -m "feat(laminates): switch CLT A-matrix and equivalent moduli to Interval arithmetic"
```

---

## Task 9: `scoring.py` —— 区间宽度驱动数据可信度 + envelope 余量驱动工况风险

**Files:**
- Modify: `material_eval/scoring.py`
- Modify: `tests/test_scoring.py`

- [ ] **Step 1: 写失败测试**

```python
import unittest

from material_eval.scoring import score_data_confidence, score_condition_risk
from material_eval.uncertainty import EnvelopeReport, EnvelopeSpec, Interval, Violation


class DataConfidenceScoreTest(unittest.TestCase):
    def test_narrow_interval_high_score(self):
        ivs = [Interval(low=99, typical=100, high=101, unit="MPa")]  # rel width 0.02
        score = score_data_confidence(ivs)
        self.assertGreaterEqual(score, 0.9)

    def test_wide_interval_low_score(self):
        ivs = [Interval(low=10, typical=50, high=200, unit="MPa")]  # rel width 3.8
        score = score_data_confidence(ivs)
        self.assertLessEqual(score, 0.2)


class ConditionRiskScoreTest(unittest.TestCase):
    def _stub_cond(self, **kwargs):
        class C:
            def envelope_axes(self):
                base = {k: None for k in
                        ("temperature_C", "humidity_pct", "stress_MPa",
                         "strain_rate_1_per_s", "fatigue_cycles", "thickness_mm")}
                base.update(kwargs)
                return base
        return C()

    def test_far_from_boundary_high_score(self):
        env = EnvelopeSpec(temperature_C=(-40.0, 120.0))
        score = score_condition_risk(env, self._stub_cond(temperature_C=25.0))
        self.assertGreaterEqual(score, 0.9)

    def test_near_boundary_lower_score(self):
        env = EnvelopeSpec(temperature_C=(-40.0, 120.0))
        score = score_condition_risk(env, self._stub_cond(temperature_C=118.0))
        self.assertLessEqual(score, 0.4)

    def test_no_envelope_returns_neutral(self):
        env = EnvelopeSpec()
        score = score_condition_risk(env, self._stub_cond(temperature_C=25.0))
        self.assertAlmostEqual(score, 0.5)
```

- [ ] **Step 2: 实现**

在 `scoring.py` 增加（保留现有 Scorecard / ScoreDimension）：

```python
def score_data_confidence(intervals: list[Interval]) -> float:
    if not intervals:
        return 0.5
    width = max(i.relative_width() for i in intervals)
    if width < 0.1:
        return 1.0
    if width < 0.3:
        return 0.7
    if width < 0.6:
        return 0.4
    return 0.1


def score_condition_risk(envelope: EnvelopeSpec, condition) -> float:
    if not envelope.has_any_axis():
        return 0.5
    axes = condition.envelope_axes()
    margins: list[float] = []
    for axis in _ENVELOPE_AXES:
        allowed = getattr(envelope, axis)
        actual = axes.get(axis)
        if allowed is None or actual is None:
            continue
        lo, hi = allowed
        span = hi - lo
        if span <= 0:
            continue
        margin = min(actual - lo, hi - actual) / span
        margins.append(margin)
    if not margins:
        return 0.5
    min_margin = min(margins)
    if min_margin > 0.3:
        return 1.0
    if min_margin > 0.15:
        return 0.7
    if min_margin > 0.05:
        return 0.4
    return 0.1
```

注意 `_ENVELOPE_AXES` 从 `uncertainty` 导入；如未导出加 `from material_eval.uncertainty import _ENVELOPE_AXES`（或公开化重命名为 `ENVELOPE_AXES`）。

- [ ] **Step 3: 把 `build_scorecard()` 接入这两个新评分**

定位现有 `build_scorecard`：把"数据可信度"和"工况风险可控性"维度的 raw_score 来源切换为新函数；其他维度暂保持原逻辑。如果旧实现把这两维度写死分值，本步骤替换为：

```python
# inside build_scorecard:
all_intervals = _collect_result_intervals(calc_result)  # helper that walks metrics
data_score = score_data_confidence(all_intervals)
risk_score = score_condition_risk(material.envelope or EnvelopeSpec(), condition) \
    if material.envelope is not None else 0.5
```

如 `MaterialCandidate` 没有 `envelope` 字段（当前确实没有），先在调用层把 envelope 单独传入：调整 `build_scorecard` 签名增加 `envelope: EnvelopeSpec | None = None, condition: Condition | None = None`。

- [ ] **Step 4: 运行测试**

```bash
.venv/bin/python -m unittest tests.test_scoring -v
```

修到通过。

- [ ] **Step 5: Commit**

```bash
git add material_eval/scoring.py tests/test_scoring.py
git commit -m "feat(scoring): drive data confidence by interval width, condition risk by envelope margin"
```

---

## Task 10: `report_schema.py` —— interval/envelope payload

**Files:**
- Modify: `material_eval/report_schema.py`
- Modify: `tests/test_report_schema.py`

- [ ] **Step 1: 加 payload 模型**

在 `report_schema.py` 增加：

```python
from pydantic import BaseModel


class IntervalPayload(BaseModel):
    low: float
    typical: float
    high: float
    unit: str
    widened: bool = False

    @classmethod
    def from_interval(cls, iv) -> "IntervalPayload":
        return cls(low=iv.low, typical=iv.typical, high=iv.high, unit=iv.unit, widened=iv.widened)


class ViolationPayload(BaseModel):
    axis: str
    input_value: float
    allowed_low: float
    allowed_high: float
    source: str | None = None


class EnvelopeReportPayload(BaseModel):
    has_declared_envelope: bool
    violations: list[ViolationPayload] = []

    @classmethod
    def from_report(cls, report) -> "EnvelopeReportPayload":
        return cls(
            has_declared_envelope=report.has_declared_envelope,
            violations=[
                ViolationPayload(
                    axis=v.axis, input_value=v.input_value,
                    allowed_low=v.allowed_range[0], allowed_high=v.allowed_range[1],
                    source=v.source,
                )
                for v in report.violations
            ],
        )
```

- [ ] **Step 2: 给 `ClaimBinding` 加 `interval: IntervalPayload | None = None` 字段；给 `StructuredReport` 加 `envelope_report: EnvelopeReportPayload | None = None`**

- [ ] **Step 3: 写测试**

```python
class IntervalPayloadTest(unittest.TestCase):
    def test_roundtrip(self):
        from material_eval.uncertainty import Interval
        from material_eval.report_schema import IntervalPayload
        iv = Interval(low=1.0, typical=2.0, high=3.0, unit="MPa")
        p = IntervalPayload.from_interval(iv)
        self.assertEqual(p.low, 1.0)
        self.assertEqual(p.unit, "MPa")
```

- [ ] **Step 4: 运行 + Commit**

```bash
.venv/bin/python -m unittest tests.test_report_schema -v
git add material_eval/report_schema.py tests/test_report_schema.py
git commit -m "feat(report-schema): add IntervalPayload and EnvelopeReportPayload to claim/structured report"
```

---

## Task 11: `evaluation.py` —— `Condition` 入参 + `validate_envelope` + `EnvelopeRefusal` 短路

**Files:**
- Modify: `material_eval/evaluation.py`
- Modify: `material_eval/evidence.py`, `material_eval/reporting.py`（如调用签名涉及）
- Modify: `tests/test_evaluation_workflow.py`

- [ ] **Step 1: 改写 `evaluation.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from material_eval.catalog import PartTemplate
from material_eval.computation import CalculationResult, calculate_part
from material_eval.conditions import Condition
from material_eval.evidence import EvidenceCard, search_evidence
from material_eval.laminates import LaminateResult, LaminateStack, analyze_laminate
from material_eval.materials import MaterialCandidate
from material_eval.reporting import ReportDraft, RefusalReport, build_internal_report, build_refusal_report
from material_eval.uncertainty import EnvelopeReport, EnvelopeSpec


@dataclass(frozen=True)
class EvaluationRequest:
    material: MaterialCandidate
    part: PartTemplate
    condition: Condition
    evidence_query: str | None = None
    retrieval_mode: str = "bm25"
    laminate_stack: LaminateStack | None = None
    material_envelope: EnvelopeSpec | None = None  # supplied alongside material for now


@dataclass(frozen=True)
class EvaluationDraft:
    material: MaterialCandidate
    part: PartTemplate
    condition: Condition
    calculation: CalculationResult
    laminate_result: LaminateResult | None
    evidence_cards: list[EvidenceCard]
    report: ReportDraft
    envelope_report: EnvelopeReport


@dataclass(frozen=True)
class EnvelopeRefusal:
    material: MaterialCandidate
    part: PartTemplate
    condition: Condition
    envelope_report: EnvelopeReport
    alternative_materials: tuple[str, ...]
    missing_data: tuple[str, ...]
    refusal_report: "RefusalReport"


def validate_envelope(envelope: EnvelopeSpec | None, condition: Condition) -> EnvelopeReport:
    if envelope is None:
        return EnvelopeReport(violations=(), has_declared_envelope=False)
    return envelope.check(condition)


def run_evaluation(request: EvaluationRequest) -> EvaluationDraft | EnvelopeRefusal:
    envelope_report = validate_envelope(request.material_envelope, request.condition)
    if envelope_report.violations:
        refusal_report = build_refusal_report(
            material=request.material,
            part=request.part,
            condition=request.condition,
            envelope_report=envelope_report,
        )
        return EnvelopeRefusal(
            material=request.material,
            part=request.part,
            condition=request.condition,
            envelope_report=envelope_report,
            alternative_materials=tuple(),  # populated by UI layer if catalog lookup available
            missing_data=tuple(),
            refusal_report=refusal_report,
        )
    calculation = calculate_part(request.part, request.material, request.condition)
    laminate_result = analyze_laminate(request.laminate_stack) if request.laminate_stack else None
    evidence_cards = search_evidence(
        request.evidence_query or _default_evidence_query(request),
        retrieval_mode=request.retrieval_mode,
    )
    report = build_internal_report(
        material=request.material,
        part=request.part,
        condition=request.condition,
        calculation=calculation,
        laminate_result=laminate_result,
        evidence_cards=evidence_cards,
        envelope_report=envelope_report,
    )
    return EvaluationDraft(
        material=request.material,
        part=request.part,
        condition=request.condition,
        calculation=calculation,
        laminate_result=laminate_result,
        evidence_cards=evidence_cards,
        report=report,
        envelope_report=envelope_report,
    )


def _default_evidence_query(request: EvaluationRequest) -> str:
    return f"{request.material.name} {request.part.name}"
```

- [ ] **Step 2: 改 `tests/test_evaluation_workflow.py`**

把所有 `dimensions={"length": 100.0, ...}` 改成 `condition=Condition.from_dimensions({"length": 100.0, ...})`，加 in/out-of-envelope 两个 case：

```python
class EnvelopeShortCircuitTest(unittest.TestCase):
    def test_out_of_envelope_returns_refusal(self):
        from material_eval.evaluation import EvaluationRequest, EnvelopeRefusal, run_evaluation
        from material_eval.conditions import Condition, Quantity
        from material_eval.uncertainty import EnvelopeSpec
        ...
        envelope = EnvelopeSpec(temperature_C=(-40, 80), source="seed")
        cond = Condition.from_dimensions(
            {"length": 1000, "width": 30, "thickness": 2},
            temperature=Quantity(value=150.0, unit="degC"),
        )
        request = EvaluationRequest(
            material=material, part=part, condition=cond,
            material_envelope=envelope,
        )
        result = run_evaluation(request)
        self.assertIsInstance(result, EnvelopeRefusal)
        self.assertEqual(len(result.envelope_report.violations), 1)
```

- [ ] **Step 3: 运行测试逐项修复**

```bash
.venv/bin/python -m unittest tests.test_evaluation_workflow -v
```

- [ ] **Step 4: Commit**

```bash
git add material_eval/evaluation.py tests/test_evaluation_workflow.py
git commit -m "feat(evaluation): switch to Condition input, add validate_envelope + EnvelopeRefusal short-circuit"
```

---

## Task 12: `reporting.py` —— 区间渲染 + 工况包络章节 + RefusalReport

**Files:**
- Modify: `material_eval/reporting.py`
- Create: `tests/test_reporting.py`

- [ ] **Step 1: 在 `reporting.py` 中**

1. `build_internal_report(...)` 新签名增加 `condition: Condition, envelope_report: EnvelopeReport`。
2. Markdown 渲染部分：所有数值列改用 `metric.value.format()`。
3. 新增 section helper `_render_envelope_section(envelope_report, condition)` 返回 Markdown 表格：

```
## 工况包络校验
| 工况轴 | 输入值 | 允许范围 | 数据来源 | 状态 |
| --- | --- | --- | --- | --- |
| 温度 | 80 °C | [-40, 120] °C | supplier datasheet | ✓ |
| 厚度 | 2 mm | [0.5, 10] mm | supplier datasheet | ✓ |
```

4. 新增 `_render_uncertainty_note(intervals)` section：

```
## 不确定度说明
本次报告所有数值以三点区间 (low / typical / high) 表达。
主导区间宽度的输入属性：[列出 top-3 关键属性 + confidence]。
若需收窄区间，请补充：[来源建议]。
```

5. 新增 `RefusalReport` dataclass 和 `build_refusal_report(...)`：

```python
@dataclass(frozen=True)
class RefusalReport:
    markdown: str
    violations: tuple[Violation, ...]
    suggested_alternatives: tuple[str, ...]
    missing_data_hints: tuple[str, ...]


def build_refusal_report(*, material, part, condition, envelope_report,
                         suggested_alternatives=(), missing_data_hints=()) -> RefusalReport:
    lines = [
        f"# 未出具评估：{material.name} 用于 {part.name}",
        "",
        "## 拒绝原因",
        "",
        "本次评估未出具数值结论，因为以下工况输入超出材料适用域：",
        "",
        "| 工况轴 | 输入值 | 允许范围 | 数据来源 |",
        "| --- | --- | --- | --- |",
    ]
    for v in envelope_report.violations:
        lines.append(f"| {v.axis} | {v.input_value} | [{v.allowed_range[0]}, {v.allowed_range[1]}] | {v.source or '未声明'} |")
    if suggested_alternatives:
        lines += ["", "## 已知适用该工况的同类材料", ""]
        lines += [f"- {name}" for name in suggested_alternatives]
    if missing_data_hints:
        lines += ["", "## 若要继续评估需要补充的数据", ""]
        lines += [f"- {hint}" for hint in missing_data_hints]
    lines += ["", "*本工具拒绝在材料适用域之外出具数值结论，以避免误导内部研发判断。*"]
    return RefusalReport(
        markdown="\n".join(lines),
        violations=envelope_report.violations,
        suggested_alternatives=tuple(suggested_alternatives),
        missing_data_hints=tuple(missing_data_hints),
    )
```

- [ ] **Step 2: 写测试 `tests/test_reporting.py`**

```python
import unittest

from material_eval.reporting import build_refusal_report
from material_eval.uncertainty import EnvelopeReport, Violation


class RefusalReportTest(unittest.TestCase):
    def test_refusal_lists_violation_and_alternatives(self):
        report = EnvelopeReport(
            violations=(Violation(axis="temperature_C", input_value=150.0,
                                  allowed_range=(-40.0, 120.0), source="supplier"),),
            has_declared_envelope=True,
        )
        class _MockMat: name = "PA66-GF30"
        class _MockPart: name = "外壳"
        result = build_refusal_report(
            material=_MockMat(), part=_MockPart(), condition=None,
            envelope_report=report,
            suggested_alternatives=("PEEK CF30",),
            missing_data_hints=("补充 150°C 拉伸数据",),
        )
        self.assertIn("未出具评估", result.markdown)
        self.assertIn("temperature_C", result.markdown)
        self.assertIn("[-40.0, 120.0]", result.markdown)
        self.assertIn("PEEK CF30", result.markdown)
        self.assertIn("补充 150°C 拉伸数据", result.markdown)
```

并把 build_internal_report 的快照测试调整，断言新增 "工况包络校验" / "不确定度说明" 章节出现。

- [ ] **Step 3: 跑测试 + Commit**

```bash
.venv/bin/python -m unittest tests.test_reporting -v
git add material_eval/reporting.py tests/test_reporting.py
git commit -m "feat(reporting): render intervals, envelope section, and RefusalReport"
```

---

## Task 13: `storage.py` —— payload 增字段 + refusal log

**Files:**
- Modify: `material_eval/storage.py`
- Modify: `tests/test_evidence_reporting_storage.py`

- [ ] **Step 1: `save_run(...)` 接受可选 `envelope_report` 并写进 payload JSON**

具体改造：原 `payload` JSON 增加 `"envelope_report": {...}` 段；旧记录读取时缺该字段则注入默认 `{"has_declared_envelope": false, "violations": []}`。

- [ ] **Step 2: 新增 `append_refusal_log(refusal: EnvelopeRefusal) -> Path`**

```python
DEFAULT_REFUSAL_LOG = Path(__file__).resolve().parents[1] / "data" / "refusal_log.jsonl"


def append_refusal_log(refusal, *, log_path: Path | None = None) -> Path:
    path = log_path or DEFAULT_REFUSAL_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "material": refusal.material.name,
        "part": refusal.part.name,
        "violations": [
            {"axis": v.axis, "input": v.input_value, "allowed": list(v.allowed_range), "source": v.source}
            for v in refusal.envelope_report.violations
        ],
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path
```

- [ ] **Step 3: 写测试**

```python
class RefusalLogTest(unittest.TestCase):
    def test_append_creates_jsonl_record(self):
        import json, tempfile
        from pathlib import Path
        from material_eval.evaluation import EnvelopeRefusal
        from material_eval.uncertainty import EnvelopeReport, Violation
        from material_eval.storage import append_refusal_log

        with tempfile.TemporaryDirectory() as tmpdir:
            log = Path(tmpdir) / "refusal.jsonl"
            class _Mat: name = "PA66"
            class _Part: name = "外壳"
            refusal = EnvelopeRefusal(
                material=_Mat(), part=_Part(), condition=None,
                envelope_report=EnvelopeReport(
                    violations=(Violation(axis="temperature_C", input_value=150.0,
                                          allowed_range=(-40.0, 120.0), source="seed"),),
                    has_declared_envelope=True,
                ),
                alternative_materials=(), missing_data=(), refusal_report=None,
            )
            append_refusal_log(refusal, log_path=log)
            content = log.read_text().strip()
            data = json.loads(content)
            self.assertEqual(data["material"], "PA66")
            self.assertEqual(data["violations"][0]["axis"], "temperature_C")
```

- [ ] **Step 4: 跑测试 + Commit**

```bash
.venv/bin/python -m unittest tests.test_evidence_reporting_storage -v
git add material_eval/storage.py tests/test_evidence_reporting_storage.py
git commit -m "feat(storage): persist envelope_report in run payload, add refusal_log.jsonl"
```

---

## Task 14: `ui_streamlit.py` —— 单位下拉 + 软校验 + refusal banner

**Files:**
- Modify: `material_eval/ui_streamlit.py`

本任务**没有传统单元测试**（Streamlit AppTest 在新版可用，但我们当前 baseline 是手测）。改完后用 `streamlit run app.py` 手动验证下列清单：

- [ ] **Step 1: 工况输入区每个字段增加 unit selectbox**

对 length/width/thickness/height/diameter，单位下拉选项 `["mm", "cm", "m", "in"]`，默认 `mm`。
对 temperature 字段加单位 `["degC", "K"]`，默认 `degC`。
对 force 字段 `["N", "kN", "lbf"]`，pressure 字段 `["MPa", "GPa", "Pa", "psi"]`。

每次读取构造 `Quantity(value, unit)`，最终聚合为 `Condition`。

- [ ] **Step 2: 实时软校验**

提交按钮上方新增一段：

```python
preview_envelope = material_envelope_for_selected_material(material_id)
if preview_envelope and preview_envelope.has_any_axis():
    preview_report = preview_envelope.check(condition_preview)
    for v in preview_report.violations:
        st.warning(f"⚠️ {v.axis}={v.input_value} 超出 {selected_material} 适用域 [{v.allowed_range[0]}, {v.allowed_range[1]}]")
```

- [ ] **Step 3: 提交后处理 refusal**

```python
result = run_evaluation(request)
if isinstance(result, EnvelopeRefusal):
    st.error("本次评估未出具数值结论，详见下方说明。")
    st.markdown(result.refusal_report.markdown)
    append_refusal_log(result)
    return  # do not render any chart/score/calc
# else: 原有渲染逻辑
```

- [ ] **Step 4: 材料库详情页**

加两个标签：

```python
status_envelope = "✅ 已声明适用域" if material.envelope and material.envelope.has_any_axis() else "⚠️ 未声明适用域"
status_interval = "✅ 三点区间" if material_has_three_point_property(material) else "⚠️ 单点（按 confidence 自动展开）"
st.caption(f"{status_envelope}　·　{status_interval}")
```

- [ ] **Step 5: 手测 checklist（写到 commit message 里）**

- [ ] 输入 `length=10 cm` 提交后报告显示 `length=100 mm`
- [ ] 选 PA66-GF30（envelope declared）+ 温度 150°C → 提交后看到红底 refusal report，无图表
- [ ] 选 PA66-GF30 + 温度 80°C → 正常出报告，看到 "工况包络校验" 章节
- [ ] 选未声明 envelope 的材料 → 材料详情页显示 "⚠️ 未声明适用域"

- [ ] **Step 6: Commit**

```bash
git add material_eval/ui_streamlit.py
git commit -m "feat(ui): unit dropdowns, soft envelope warnings, refusal banner"
```

---

## Task 15: 核心 5 材料 seed 数据升级

**Files:**
- Modify: `data/seed/material_property_library.json`

升级目标材料（覆盖 MVP 首测 3 场景）：
1. `aluminum_7075_t6` — 人形机器人骨架候选
2. `ti_6al_4v` — 人形机器人骨架候选
3. `peek_cf30` — 智能穿戴外壳候选
4. `pa66_gf30` — 智能穿戴外壳候选
5. `kevlar_aramid_fiber` — 柔性外骨骼助力带候选

每个材料：
- 把 3 条核心属性观察的 `value: x` 改为 `value: {low: x*0.95 or 工程下限, typical: x, high: x*1.05 or 工程上限}`。

  原则：若手册数值带"典型值"标注，采用 ±10% 区间；若是单点引用，采用 ±20%；区间端点取整到合理工程精度。  
  source_label 加后缀 `, three-point interval seeded by engineering judgement, needs supplier/test confirmation`。
- 新增顶层 `envelope` 字段，由 executor 按下表填充：

| Material | temperature_C | humidity_pct | stress_MPa | thickness_mm | source |
|---|---|---|---|---|---|
| aluminum_7075_t6 | [-50, 150] | [0, 95] | [0, 460] | [0.5, 200] | engineering default |
| ti_6al_4v | [-200, 400] | [0, 100] | [0, 800] | [0.5, 200] | engineering default |
| peek_cf30 | [-40, 240] | [0, 90] | [0, 180] | [0.5, 25] | engineering default |
| pa66_gf30 | [-30, 120] | [0, 60] | [0, 130] | [0.5, 20] | engineering default |
| kevlar_aramid_fiber | [-40, 180] | [0, 90] | [0, 2800] | [0.05, 5] | engineering default |

注：所有数值是**工程缺省占位**，必须在 seed 文件的 `notes` 字段显式标注"engineering default, needs supplier/test confirmation"。

- [ ] **Step 1: 修改 `data/seed/material_property_library.json`**

按上述规则修改 5 个材料的对应记录。

- [ ] **Step 2: 加完整 seed 验证测试 `tests/test_material_property_library.py::SeedIntegrityTest`**

```python
class SeedIntegrityTest(unittest.TestCase):
    def setUp(self):
        from material_eval.material_property_library import load_material_library
        self.lib = load_material_library()

    def test_core_materials_have_envelope(self):
        core = {"aluminum_7075_t6", "ti_6al_4v", "peek_cf30", "pa66_gf30", "kevlar_aramid_fiber"}
        for mid in core:
            mat = self.lib.get(mid)
            self.assertIsNotNone(mat.envelope, f"{mid} missing envelope")
            self.assertTrue(mat.envelope.has_any_axis(), f"{mid} envelope has no axis")

    def test_core_materials_have_three_point_intervals(self):
        from material_eval.material_property_library import load_material_library
        for mid in ("aluminum_7075_t6", "ti_6al_4v", "peek_cf30", "pa66_gf30"):
            mat = self.lib.get(mid)
            for prop in ("density_g_cm3", "tensile_strength_mpa", "elastic_modulus_gpa"):
                iv = mat.property(prop)
                self.assertIsNotNone(iv, f"{mid}.{prop} missing")
                self.assertGreater(iv.high, iv.low, f"{mid}.{prop} not a true interval")
```

- [ ] **Step 3: 跑测试**

```bash
.venv/bin/python -m unittest tests.test_material_property_library.SeedIntegrityTest -v
```

- [ ] **Step 4: Commit**

```bash
git add data/seed/material_property_library.json tests/test_material_property_library.py
git commit -m "data(seed): upgrade 5 core materials with three-point intervals and engineering-default envelopes"
```

---

## Task 16: 端到端 smoke 测试 —— MVP 3 场景 × in/out-of-envelope

**Files:**
- Create: `tests/test_phase1_smoke.py`

3 个场景（来自 README）：
1. 人形机器人核心骨架 / 下肢大扭矩管状连杆（BEAM）+ Ti-6Al-4V
2. 智能穿戴 / 智能穿戴承力外壳（PLATE）+ PA66-GF30
3. 智能穿戴 / 柔性外骨骼助力带（STRAP）+ Kevlar

每场景两个 case：
- in-envelope：典型工况，必须返回 `EvaluationDraft`，报告 Markdown 包含 "工况包络校验" 章节
- out-of-envelope：例如温度超 PA66-GF30 上限，必须返回 `EnvelopeRefusal`

- [ ] **Step 1: 写测试**

`tests/test_phase1_smoke.py`:

```python
import unittest

from material_eval.catalog import load_catalog
from material_eval.conditions import Condition, Quantity
from material_eval.evaluation import EnvelopeRefusal, EvaluationDraft, EvaluationRequest, run_evaluation
from material_eval.material_property_library import load_material_library
from material_eval.materials import MaterialCandidate


def _candidate_from(material_entry) -> MaterialCandidate:
    return MaterialCandidate(
        name=material_entry.name,
        category=material_entry.category,
        density_g_cm3=material_entry.property("density_g_cm3"),
        tensile_strength_mpa=material_entry.property("tensile_strength_mpa"),
        elastic_modulus_gpa=material_entry.property("elastic_modulus_gpa"),
    )


class Phase1SmokeTest(unittest.TestCase):
    def setUp(self):
        self.lib = load_material_library()
        self.catalog = load_catalog()

    def _part(self, domain, name):
        for d in self.catalog.domains:
            if d.name == domain:
                for p in d.parts:
                    if p.name == name:
                        return p
        raise KeyError(f"part not found: {domain}/{name}")

    def test_humanoid_skeleton_titanium_in_envelope(self):
        mat = self.lib.get("ti_6al_4v")
        part = self._part("人形机器人核心骨架", "下肢大扭矩管状连杆")
        cond = Condition.from_dimensions(
            {"length": 250.0, "diameter": 40.0, "thickness": 3.0},
            temperature=Quantity(value=25.0, unit="degC"),
        )
        result = run_evaluation(EvaluationRequest(
            material=_candidate_from(mat), part=part, condition=cond, material_envelope=mat.envelope,
        ))
        self.assertIsInstance(result, EvaluationDraft)
        self.assertIn("工况包络校验", result.report.markdown)

    def test_wearable_shell_pa66_out_of_envelope_high_temperature(self):
        mat = self.lib.get("pa66_gf30")
        part = self._part("智能穿戴与柔性外骨骼", "智能穿戴承力外壳")
        cond = Condition.from_dimensions(
            {"length": 150.0, "width": 80.0, "thickness": 3.0},
            temperature=Quantity(value=150.0, unit="degC"),  # exceeds PA66-GF30 envelope upper bound
        )
        result = run_evaluation(EvaluationRequest(
            material=_candidate_from(mat), part=part, condition=cond, material_envelope=mat.envelope,
        ))
        self.assertIsInstance(result, EnvelopeRefusal)
        self.assertTrue(any(v.axis == "temperature_C" for v in result.envelope_report.violations))

    def test_strap_kevlar_in_envelope(self):
        mat = self.lib.get("kevlar_aramid_fiber")
        part = self._part("智能穿戴与柔性外骨骼", "柔性外骨骼助力带")
        cond = Condition.from_dimensions(
            {"length": 1000.0, "width": 40.0, "thickness": 1.5},
            temperature=Quantity(value=25.0, unit="degC"),
        )
        result = run_evaluation(EvaluationRequest(
            material=_candidate_from(mat), part=part, condition=cond, material_envelope=mat.envelope,
        ))
        self.assertIsInstance(result, EvaluationDraft)
        # all metric values are Intervals with non-negative widths
        for m in result.calculation.metrics:
            self.assertGreaterEqual(m.value.high, m.value.low)
```

- [ ] **Step 2: 运行**

```bash
.venv/bin/python -m unittest tests.test_phase1_smoke -v
```

修复直到 3 个 case 全过。

- [ ] **Step 3: 跑全量测试**

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v 2>&1 | tail -30
.venv/bin/python -m compileall material_eval app.py tests
```

预期：全绿。

- [ ] **Step 4: Commit**

```bash
git add tests/test_phase1_smoke.py
git commit -m "test(phase1): add MVP 3-scenario smoke tests covering in/out-of-envelope paths"
```

---

## Task 17: 文档更新

**Files:**
- Modify: `docs/implementation-log.md`
- Modify: `CLAUDE.md`（如需补充）

- [ ] **Step 1: 在 `docs/implementation-log.md` 的"已完成"末尾追加 Phase 1 章节**

```markdown
### 10. Phase 1 可信数字基础设施（2026-05-12）

- 新增 `material_eval/uncertainty.py`：`Interval`、`EnvelopeSpec`、`EnvelopeReport`、`Violation`、`CONFIDENCE_SPREAD`。
- 新增 `material_eval/conditions.py`：`Quantity`/`Condition` Pydantic 模型，单位归一化入口。
- 扩展 `material_eval/units.py`：覆盖长度/力/力矩/应力/温度/湿度/应变率，新增 `normalize_quantity()` 统一入口。
- 升级 `material_property_library.py`：解析三点区间与单点（按 confidence 自动展开），多观察聚合为 Interval，加载 `envelope`。
- 升级 `materials.py` / `computation.py` / `section_analysis.py` / `laminates.py` / `scoring.py` / `report_schema.py` / `reporting.py` / `evaluation.py` / `storage.py` / `ui_streamlit.py`，全链路 Interval + envelope。
- `EnvelopeRefusal` 在工况越界时短路：不出数、不写主表、写 `data/refusal_log.jsonl`。
- 报告 Markdown 新增"工况包络校验"和"不确定度说明"章节。
- Streamlit UI 加单位下拉、实时软校验、refusal banner。
- 核心 5 材料（7075-T6、Ti-6Al-4V、PEEK-CF30、PA66-GF30、Kevlar）seed 已升级为三点区间 + envelope；其余材料保持兼容占位。

#### 新发现

- 区间宽度对评分影响显著，部分材料 confidence < 0.5 的属性主导了"数据可信度"分；需要业务专家在 Phase 2 用真实实验数据校准 `CONFIDENCE_SPREAD`。
- 越界硬拒绝实际触发后用户体验良好，但需要后续填充 `suggested_alternatives` / `missing_data_hints` 才能让用户有"建设性出口"。
```

- [ ] **Step 2: 写 commit**

```bash
git add docs/implementation-log.md
git commit -m "docs: log Phase 1 completion and new findings"
```

---

## 验收命令（Phase 1 完成时执行）

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m compileall material_eval app.py tests
.venv/bin/streamlit run app.py &  # 手动跑 Task 14 checklist
```

预期：
- 全量 unittest 绿（含新增 ~40+ 测试）
- compileall 无语法错误
- Streamlit 手测清单全通过

---

## 自检（writing-plans skill 要求）

**Spec coverage check：**

| Spec 段落 | 对应 Task |
|---|---|
| §3.1 Interval | Task 1 |
| §3.1 EnvelopeSpec/EnvelopeReport | Task 2 |
| §3.2 units 扩展 | Task 3 |
| §3.3 Condition | Task 4 |
| §3.4 material_property_library 升级 | Task 5 |
| §3.5 computation + section_analysis + laminates | Task 7, 8 |
| §3.6 evaluation 短路 | Task 11 |
| §3.7 scoring | Task 9 |
| §3.8 report_schema | Task 10 |
| §3.9 reporting + RefusalReport | Task 12 |
| §3.10 UI | Task 14 |
| §3.11 storage + refusal log | Task 13 |
| §5.2 5 材料 seed 升级 | Task 15 |
| §7 验收清单 / DoD | Task 16, 17 + 末尾验收命令 |

无遗漏。

**Placeholder scan：** 无 TBD / TODO / "实现 later"；所有代码块给出完整签名与可执行片段；细节实现（如 CLT 3x3 求逆、_calculate_i_beam 等已有公式的区间化重写）明确指向"按原公式 + Interval 算术"的固定模式，executor 不需要新增设计判断。

**类型一致性：** `EvaluationRequest.material_envelope`、`EnvelopeSpec.check(condition)`、`Condition.envelope_axes()` 在 Task 2 / 4 / 11 中签名一致。`Metric.value: Interval` 在 Task 7 / 9 / 12 中一致。`IntervalPayload.from_interval` 在 Task 10 / 12 一致。

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-12-phase1-trustworthy-numbers.md`. 两种执行方式：**

**1. Subagent-Driven（推荐）** — 每个 Task 派发一个独立 subagent，主流程在 Task 之间审查，快速迭代

**2. Inline Execution** — 在当前会话内顺序执行所有 Task，按检查点暂停审核

**选哪种？**
