from __future__ import annotations

from dataclasses import dataclass

import pint


class UnitCompatibilityError(ValueError):
    pass


class UnsupportedMaterialPropertyError(KeyError):
    pass


@dataclass(frozen=True)
class NormalizedMeasurement:
    property_name: str
    value: float
    unit: str
    source_value: float
    source_unit: str


_UNIT_REGISTRY = pint.UnitRegistry()

_PROPERTY_CANONICAL_UNITS = {
    "density_g_cm3": "g/cm^3",
    "tensile_strength_mpa": "MPa",
    "elastic_modulus_gpa": "GPa",
}

_UNIT_ALIASES = {
    "g/cm3": "gram / centimeter ** 3",
    "g/cm^3": "gram / centimeter ** 3",
    "g / cm3": "gram / centimeter ** 3",
    "g / cm^3": "gram / centimeter ** 3",
    "kg/m3": "kilogram / meter ** 3",
    "kg/m^3": "kilogram / meter ** 3",
    "kg / m3": "kilogram / meter ** 3",
    "kg / m^3": "kilogram / meter ** 3",
    "Pa": "pascal",
    "MPa": "megapascal",
    "GPa": "gigapascal",
    "N/mm2": "newton / millimeter ** 2",
    "N/mm^2": "newton / millimeter ** 2",
    "N / mm2": "newton / millimeter ** 2",
    "N / mm^2": "newton / millimeter ** 2",
}


def canonical_unit_for_property(property_name: str) -> str:
    try:
        return _PROPERTY_CANONICAL_UNITS[property_name]
    except KeyError as exc:
        raise UnsupportedMaterialPropertyError(f"Unsupported material property: {property_name}") from exc


def normalize_material_property(property_name: str, value: float, unit: str) -> NormalizedMeasurement:
    canonical_unit = canonical_unit_for_property(property_name)
    source_unit = unit.strip()
    try:
        quantity = float(value) * _UNIT_REGISTRY(_to_pint_unit(source_unit))
        normalized = quantity.to(_to_pint_unit(canonical_unit))
    except pint.errors.DimensionalityError as exc:
        raise UnitCompatibilityError(
            f"Unit '{unit}' is not compatible with property '{property_name}' canonical unit '{canonical_unit}'."
        ) from exc
    except Exception as exc:
        raise UnitCompatibilityError(f"Could not parse unit '{unit}' for property '{property_name}'.") from exc

    return NormalizedMeasurement(
        property_name=property_name,
        value=float(normalized.magnitude),
        unit=canonical_unit,
        source_value=float(value),
        source_unit=source_unit,
    )


def _to_pint_unit(unit: str) -> str:
    cleaned = unit.strip()
    return _UNIT_ALIASES.get(cleaned, cleaned)
