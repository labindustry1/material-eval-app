from __future__ import annotations

from dataclasses import dataclass, field

from material_eval.catalog import PartTemplate
from material_eval.materials import MaterialCandidate
from material_eval.section_analysis import (
    SectionProperties,
    analyze_hollow_circular_section,
    analyze_i_section,
    analyze_rectangular_section,
)


@dataclass(frozen=True)
class Metric:
    name: str
    value: float
    unit: str
    description: str


@dataclass(frozen=True)
class CalculationResult:
    topology: str
    metrics: tuple[Metric, ...]
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    version: str = "mvp_calc_v1"

    def as_rows(self) -> list[dict[str, str | float]]:
        return [
            {
                "指标": metric.name,
                "数值": metric.value,
                "单位": metric.unit,
                "说明": metric.description,
            }
            for metric in self.metrics
        ]


def calculate_part(part: PartTemplate, material: MaterialCandidate, dims: dict[str, float]) -> CalculationResult:
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


def _density_kg_per_mm3(material: MaterialCandidate) -> float:
    return material.density_g_cm3 * 1e-6


def _elastic_modulus_mpa(material: MaterialCandidate) -> float:
    return material.elastic_modulus_gpa * 1000.0


def _base_assumptions() -> tuple[str, ...]:
    return (
        "所有尺寸输入单位为 mm；强度单位 MPa = N/mm^2；密度单位 g/cm^3。",
        "MVP 计算用于内部研发初筛，不替代 FEA、台架实验或行业准入认证。",
        "材料按均质、线弹性、各向同性处理；复合材料方向性暂未进入该模块。",
    )


def _section_assumption(section: SectionProperties) -> tuple[str, ...]:
    if section.method == "sectionproperties":
        return ("截面面积和惯性矩使用 sectionproperties 开源截面分析库计算。",)
    return ("截面面积和惯性矩使用闭式公式计算；sectionproperties 不可用时自动回退。",)


def _calculate_beam(material: MaterialCandidate, dims: dict[str, float]) -> CalculationResult:
    length = dims["length"]
    diameter = dims["diameter"]
    thickness = dims["thickness"]
    warnings: list[str] = []
    if thickness * 2 >= diameter:
        warnings.append("壁厚已接近或超过外径一半，按最小内径 0.1 mm 进行初筛，建议修正几何输入。")

    section = analyze_hollow_circular_section(diameter, thickness)
    volume = section.area_mm2 * length
    inertia = section.inertia_x_mm4
    area = section.area_mm2
    weight = volume * _density_kg_per_mm3(material)
    bending_load = (material.tensile_strength_mpa * inertia / (diameter / 2)) / length if length > 0 else 0
    axial_load = material.tensile_strength_mpa * area * 0.8
    deflection = (
        bending_load * length**3 / (3 * _elastic_modulus_mpa(material) * inertia)
        if inertia > 0 and material.elastic_modulus_gpa > 0
        else 0
    )

    return CalculationResult(
        topology="BEAM",
        metrics=(
            Metric("结构总重量估算", weight, "kg", "按薄壁/厚壁圆管体积和密度估算。"),
            Metric("悬臂抗弯极限初筛", bending_load, "N", "按根部弯曲正应力达到抗拉强度估算。"),
            Metric("轴向承载初筛", axial_load, "N", "按截面积和 0.8 折减系数估算。"),
            Metric("端部弹性挠度估算", deflection, "mm", "按悬臂梁小变形公式估算。"),
        ),
        assumptions=_base_assumptions()
        + _section_assumption(section)
        + ("圆管视作等截面悬臂梁；未考虑局部屈曲、连接、冲击和疲劳。",),
        warnings=tuple(warnings) + section.warnings,
    )


def _calculate_i_beam(material: MaterialCandidate, dims: dict[str, float]) -> CalculationResult:
    length = dims["length"]
    height = dims["height"]
    width = dims["width"]
    thickness = dims["thickness"]
    warnings: list[str] = []
    if thickness * 2 >= height:
        warnings.append("壁厚过大导致腹板高度异常，建议修正工字梁高度或壁厚。")
    inner_height = max(0.0, height - 2 * thickness)
    section = analyze_i_section(
        depth=height,
        width=width,
        flange_thickness=thickness,
        web_thickness=thickness,
    )
    area = section.area_mm2
    volume = area * length
    inertia = section.inertia_x_mm4
    weight = volume * _density_kg_per_mm3(material)
    bending_load = (material.tensile_strength_mpa * inertia / (height / 2)) / length if length > 0 else 0
    shear_load = material.tensile_strength_mpa * 0.5 * inner_height * thickness
    deflection = (
        bending_load * length**3 / (3 * _elastic_modulus_mpa(material) * inertia)
        if inertia > 0 and material.elastic_modulus_gpa > 0
        else 0
    )
    return CalculationResult(
        topology="I_BEAM",
        metrics=(
            Metric("结构总重量估算", weight, "kg", "按简化工字截面面积估算。"),
            Metric("主轴抗弯极限初筛", bending_load, "N", "按截面边缘应力达到抗拉强度估算。"),
            Metric("腹板抗剪初筛", shear_load, "N", "按腹板面积和简化剪切折减估算。"),
            Metric("主轴挠度估算", deflection, "mm", "按悬臂梁小变形公式估算。"),
        ),
        assumptions=_base_assumptions()
        + _section_assumption(section)
        + ("工字梁使用简化截面；未考虑翼缘局部屈曲、孔洞、连接和扭转。",),
        warnings=tuple(warnings) + section.warnings,
    )


def _calculate_plate(material: MaterialCandidate, dims: dict[str, float]) -> CalculationResult:
    length = dims["length"]
    width = dims["width"]
    thickness = dims["thickness"]
    section = analyze_rectangular_section(width=width, depth=thickness)
    volume = length * section.area_mm2
    weight = volume * _density_kg_per_mm3(material)
    punch_load = 4 * material.tensile_strength_mpa * (thickness**2) / length if length > 0 else 0
    shear_load = material.tensile_strength_mpa * 0.577 * width * thickness
    inertia = section.inertia_x_mm4
    deflection = (
        punch_load * length**3 / (48 * _elastic_modulus_mpa(material) * inertia)
        if inertia > 0 and material.elastic_modulus_gpa > 0
        else 0
    )
    return CalculationResult(
        topology="PLATE",
        metrics=(
            Metric("结构总重量估算", weight, "kg", "按矩形薄板体积和密度估算。"),
            Metric("中心抗冲压初筛", punch_load, "N", "按简化中心载荷和厚度平方关系估算。"),
            Metric("边缘抗剪初筛", shear_load, "N", "按 von Mises 剪切折减 0.577 估算。"),
            Metric("中心变形估算", deflection, "mm", "按简化板/梁等效小变形估算。"),
        ),
        assumptions=_base_assumptions()
        + _section_assumption(section)
        + ("薄板按简化等效模型处理；未考虑边界约束、跌落冲击、开孔和加强筋。",),
        warnings=section.warnings,
    )


def _calculate_corrugated(material: MaterialCandidate, dims: dict[str, float]) -> CalculationResult:
    length = dims["length"]
    width = dims["width"]
    thickness = dims["thickness"]
    volume = length * width * thickness * 1.22
    weight = volume * _density_kg_per_mm3(material)
    inertia_equivalent = width * (thickness * 3) ** 3 / 12
    bending_load = (
        material.tensile_strength_mpa * inertia_equivalent / (thickness * 1.5) / length
        if length > 0 and thickness > 0
        else 0
    )
    crush_energy = material.tensile_strength_mpa * volume * 0.4 / 1000
    return CalculationResult(
        topology="CORRUGATED",
        metrics=(
            Metric("结构总重量估算", weight, "kg", "按 1.22 展开系数估算波纹体积。"),
            Metric("波纹等效抗弯初筛", bending_load, "N", "按三倍厚度等效高度估算。"),
            Metric("压溃吸能初筛", crush_energy, "J", "按强度、体积和经验折减估算。"),
            Metric("结构刚度经验提升", 3.2, "倍", "旧原型经验值，仅可作示意。"),
        ),
        assumptions=_base_assumptions()
        + ("波纹板模块仍是经验初筛；真实吸能必须用实验或显式动力学仿真验证。",),
        warnings=("压溃吸能为经验估算，不可作为碰撞安全结论。",),
    )


def _calculate_strap(material: MaterialCandidate, dims: dict[str, float]) -> CalculationResult:
    width = dims["width"]
    thickness = dims["thickness"]
    ref_length = dims.get("length", 1000.0)
    section = analyze_rectangular_section(width=width, depth=thickness)
    area = section.area_mm2
    volume = ref_length * area
    weight = volume * _density_kg_per_mm3(material)
    tensile_load = material.tensile_strength_mpa * area
    elongation = (
        tensile_load * ref_length / (_elastic_modulus_mpa(material) * area)
        if area > 0 and material.elastic_modulus_gpa > 0
        else 0
    )
    return CalculationResult(
        topology="STRAP",
        metrics=(
            Metric("标准长度重量估算", weight, "kg/m", "按 1000 mm 标准长度估算。"),
            Metric("单向拉断载荷初筛", tensile_load, "N", "按截面积和抗拉强度估算。"),
            Metric("弹性伸长估算", elongation, "mm/m", "按一维拉伸线弹性公式估算。"),
            Metric("疲劳验证需求", 1.0, "需实验", "织带/柔性件疲劳寿命不能由静拉公式确定。"),
        ),
        assumptions=_base_assumptions()
        + _section_assumption(section)
        + ("带状件按一维单向拉伸处理；未考虑编织结构、缝合、打结、摩擦和循环疲劳。",),
        warnings=("柔性带疲劳、舒适性和人体工效必须后续实验验证。",) + section.warnings,
    )
