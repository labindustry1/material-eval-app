from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError, model_validator

from material_eval.units import UnitCompatibilityError, normalize_quantity


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

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as exc:
            # Re-raise any UnitCompatibilityError that Pydantic wrapped.
            for err in exc.errors():
                inner = err.get("ctx", {}).get("error")
                if isinstance(inner, UnitCompatibilityError):
                    raise inner from None
            raise

    @model_validator(mode="after")
    def _validate_units(self) -> "Condition":
        """Eagerly validate that each Quantity's unit is compatible with its dimension.

        This ensures UnitCompatibilityError is raised at construction time rather
        than deferred until envelope_axes() or geometry_mm() is called.
        """
        dimension_map = {
            "temperature": ("temperature", self.temperature),
            "humidity": ("humidity", self.humidity),
            "pressure": ("stress", self.pressure),
            "strain_rate": ("strain_rate", self.strain_rate),
        }
        for _field, (dimension, q) in dimension_map.items():
            if q is not None:
                normalize_quantity(q.value, q.unit, dimension)

        for key in ("length", "width", "thickness", "height", "diameter", "inner_diameter"):
            q = getattr(self, key)
            if q is not None:
                normalize_quantity(q.value, q.unit, "length")

        return self

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
