from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable


@dataclass(frozen=True)
class SectionProperties:
    area_mm2: float
    inertia_x_mm4: float
    inertia_y_mm4: float
    product_inertia_mm4: float
    centroid_x_mm: float
    centroid_y_mm: float
    method: str
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _sectionproperties_result(
    build_geometry: Callable[[object], object],
    fallback: Callable[[tuple[str, ...]], SectionProperties],
) -> SectionProperties:
    try:
        from sectionproperties.analysis.section import Section
        from sectionproperties.pre import library

        geometry = build_geometry(library)
        mesh = geometry.create_mesh(mesh_sizes=[0])
        section = Section(geometry=mesh)
        section.calculate_geometric_properties()
        inertia_x, inertia_y, product_inertia = section.get_ic()
        centroid_x, centroid_y = section.get_c()
        return SectionProperties(
            area_mm2=float(section.get_area()),
            inertia_x_mm4=float(inertia_x),
            inertia_y_mm4=float(inertia_y),
            product_inertia_mm4=float(product_inertia),
            centroid_x_mm=float(centroid_x),
            centroid_y_mm=float(centroid_y),
            method="sectionproperties",
        )
    except Exception as exc:  # pragma: no cover - exercised only when optional backend is unavailable/broken.
        return fallback((f"sectionproperties 截面分析不可用，已回退闭式公式：{exc}",))


@lru_cache(maxsize=256)
def analyze_hollow_circular_section(outer_diameter: float, thickness: float) -> SectionProperties:
    if outer_diameter <= 0:
        raise ValueError("outer_diameter must be positive")
    if thickness <= 0:
        raise ValueError("thickness must be positive")

    effective_thickness = min(thickness, max(0.05, (outer_diameter - 0.1) / 2))
    validation_warnings = ()
    if effective_thickness != thickness:
        validation_warnings = ("圆管壁厚已按最小内径 0.1 mm 修正后进行截面分析。",)

    def fallback(extra_warnings: tuple[str, ...] = ()) -> SectionProperties:
        inner_diameter = max(0.1, outer_diameter - 2 * effective_thickness)
        area = math.pi / 4 * (outer_diameter**2 - inner_diameter**2)
        inertia = math.pi / 64 * (outer_diameter**4 - inner_diameter**4)
        return SectionProperties(
            area_mm2=area,
            inertia_x_mm4=inertia,
            inertia_y_mm4=inertia,
            product_inertia_mm4=0.0,
            centroid_x_mm=0.0,
            centroid_y_mm=0.0,
            method="closed-form",
            warnings=validation_warnings + extra_warnings,
        )

    def build_geometry(library: object) -> object:
        return library.circular_hollow_section(d=outer_diameter, t=effective_thickness, n=96)

    result = _sectionproperties_result(build_geometry, fallback)
    if validation_warnings and result.method == "sectionproperties":
        return SectionProperties(**{**result.__dict__, "warnings": validation_warnings})
    return result


@lru_cache(maxsize=256)
def analyze_i_section(
    depth: float,
    width: float,
    flange_thickness: float,
    web_thickness: float,
) -> SectionProperties:
    if min(depth, width, flange_thickness, web_thickness) <= 0:
        raise ValueError("I section dimensions must be positive")

    effective_flange = min(flange_thickness, max(0.05, (depth - 0.1) / 2))
    effective_web = min(web_thickness, max(0.05, width - 0.1))
    validation_warnings = ()
    if effective_flange != flange_thickness or effective_web != web_thickness:
        validation_warnings = ("工字截面尺寸已修正到可计算范围，建议复核高度、宽度和壁厚。",)

    def fallback(extra_warnings: tuple[str, ...] = ()) -> SectionProperties:
        web_height = max(0.0, depth - 2 * effective_flange)
        area = 2 * width * effective_flange + web_height * effective_web
        inertia_x = (width * depth**3 - max(0.0, width - effective_web) * web_height**3) / 12
        inertia_y = (
            2 * effective_flange * width**3 / 12
            + web_height * effective_web**3 / 12
        )
        return SectionProperties(
            area_mm2=area,
            inertia_x_mm4=inertia_x,
            inertia_y_mm4=inertia_y,
            product_inertia_mm4=0.0,
            centroid_x_mm=width / 2,
            centroid_y_mm=depth / 2,
            method="closed-form",
            warnings=validation_warnings + extra_warnings,
        )

    def build_geometry(library: object) -> object:
        return library.i_section(
            d=depth,
            b=width,
            t_f=effective_flange,
            t_w=effective_web,
            r=0,
            n_r=1,
        )

    result = _sectionproperties_result(build_geometry, fallback)
    if validation_warnings and result.method == "sectionproperties":
        return SectionProperties(**{**result.__dict__, "warnings": validation_warnings})
    return result


@lru_cache(maxsize=256)
def analyze_rectangular_section(width: float, depth: float) -> SectionProperties:
    if width <= 0 or depth <= 0:
        raise ValueError("width and depth must be positive")

    def fallback(extra_warnings: tuple[str, ...] = ()) -> SectionProperties:
        return SectionProperties(
            area_mm2=width * depth,
            inertia_x_mm4=width * depth**3 / 12,
            inertia_y_mm4=depth * width**3 / 12,
            product_inertia_mm4=0.0,
            centroid_x_mm=width / 2,
            centroid_y_mm=depth / 2,
            method="closed-form",
            warnings=extra_warnings,
        )

    def build_geometry(library: object) -> object:
        return library.rectangular_section(d=depth, b=width)

    return _sectionproperties_result(build_geometry, fallback)
