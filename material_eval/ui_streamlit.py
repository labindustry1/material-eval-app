from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st

from material_eval.artifacts import write_markdown_report
from material_eval.blueprint_3d import render_3d_blueprint
from material_eval.catalog import Catalog
from material_eval.eight_dim_analysis import analyze_eight_dimensions
from material_eval.web_search import search_web
from material_eval.evaluation import EnvelopeRefusal, EvaluationRequest, run_evaluation, save_evaluation
from material_eval.laminates import Lamina, LaminateStack
from material_eval.material_property_library import MaterialPropertyLibrary
from material_eval.materials import MaterialCandidate, build_composite_material, build_single_material
from material_eval.llm_provider import polish_report_with_llm
from material_eval.openai_provider import polish_report_with_openai  # legacy alias
from material_eval.rag_eval import default_retrieval_questions, run_retrieval_evaluation
from material_eval.storage import append_refusal_log, list_recent_runs, list_report_reviews, save_report_review


def run_app() -> None:
    st.set_page_config(
        page_title="材料可行性评估 MVP",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    require_optional_access_code()
    catalog = load_catalog()

    st.title("材料可行性评估 MVP")
    st.caption("面向内部研发的轻量初筛工具：材料参数、零部件模板、内部资料证据和确定性计算先跑通。")

    request, use_openai, run_button, material_id = render_sidebar(catalog)
    render_material_summary(request.material, material_id=material_id)

    st.divider()

    if not run_button:
        render_recent_runs()
        render_rag_evaluation_panel()
        st.info("选择左侧配置后点击“运行内部初筛”。")
        return

    result = run_evaluation(request)
    if isinstance(result, EnvelopeRefusal):
        render_refusal_summary(result)
        st.markdown(result.refusal_markdown)
        try:
            append_refusal_log(result)
        except Exception as exc:
            st.warning(f"refusal 日志写入失败（不影响 UI 输出）：{exc}")
        return  # 不渲染任何 tab
    draft = result  # 现在确定是 EvaluationDraft
    report_markdown = maybe_polish_report(draft.report.markdown, use_openai=use_openai)
    run_id = save_evaluation(draft, report_markdown=report_markdown)
    report_path = write_markdown_report(filename=f"{run_id}-{draft.report.filename}", markdown=report_markdown)

    # 顶部一眼看结论面板（评估总览）
    render_evaluation_summary(draft, run_id=run_id)
    st.divider()

    (tab_calc, tab_safety, tab_eightdim, tab_evidence, tab_web,
     tab_report, tab_history, tab_rageval) = st.tabs([
         "工程初筛", "安全性评估", "商业八维剖析", "证据卡", "全网检索",
         "中文报告", "评估记录", "检索评估",
     ])
    with tab_calc:
        # 3D 蓝图：宏观几何 + 应力示意双视图
        render_blueprint_section(request.part.topology, request.dimensions)
        st.success(f"评估已保存，Run ID: {run_id}")
        render_calculation(draft.calculation)
        render_laminate_result(draft.laminate_result)
    with tab_safety:
        render_safety_report(draft.safety_report)
    with tab_eightdim:
        render_eight_dim_section(draft)
    with tab_evidence:
        render_evidence(draft.evidence_cards)
    with tab_web:
        render_web_search_section(draft)
    with tab_report:
        render_report(markdown=report_markdown, filename=draft.report.filename, report_path=report_path, run_id=run_id)
    with tab_history:
        render_recent_runs()
    with tab_rageval:
        render_rag_evaluation_panel()


def require_optional_access_code() -> None:
    access_code = os.getenv("MVP_ACCESS_CODE", "").strip()
    if not access_code:
        return
    if st.session_state.get("authenticated"):
        return

    st.markdown("<br><br>", unsafe_allow_html=True)
    col_left, col_mid, col_right = st.columns([1, 1, 1])
    with col_mid:
        st.info("该 MVP 已开启访问码保护。")
        submitted = st.text_input("访问码", type="password")
        if st.button("进入系统", type="primary", width="stretch"):
            if submitted == access_code:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("访问码不正确。")
    st.stop()


@st.cache_resource
def load_catalog() -> Catalog:
    return Catalog()


@st.cache_resource
def load_material_library() -> MaterialPropertyLibrary:
    return MaterialPropertyLibrary()


def render_sidebar(catalog: Catalog) -> tuple[EvaluationRequest, bool, bool, str | None]:
    with st.sidebar:
        st.header("1. 目标零部件")
        mvp_only = st.toggle(
            "只显示 MVP 首测场景",
            value=False,
            help="勾选后只显示原型期重点验证的 3 个零部件；默认关闭，展示全部行业和零件库。",
        )
        if mvp_only:
            available_parts = catalog.mvp_parts()
            domains = sorted({part.domain for part in available_parts})
        else:
            available_parts = catalog.parts
            domains = catalog.domains

        domain = st.selectbox("应用领域", domains)
        parts = [part for part in available_parts if part.domain == domain]
        part_name = st.selectbox("核心零部件", [part.name for part in parts])
        part = next(item for item in parts if item.name == part_name)

        st.caption(f"拓扑：{part.topology}")
        with st.expander("约束摘要", expanded=False):
            st.write(part.constraint)

        material, laminate_stack, material_id_chosen = render_material_form()
        dimensions = render_dimension_form(part)
        axial_force, bending_moment = render_load_inputs()

        st.header("4. 生成")
        retrieval_label = st.radio(
            "证据检索",
            ["BM25 关键词检索", "BGE-M3 语义检索（可选）"],
            horizontal=True,
        )
        retrieval_mode = "embedding" if retrieval_label.startswith("BGE-M3") else "bm25"
        if retrieval_mode == "embedding":
            st.caption("首次启用会加载 BAAI/bge-m3；未安装 FlagEmbedding 时自动回退 BM25。")
        use_openai = st.checkbox(
            "使用 LLM 润色报告（可选）",
            value=False,
            help="自动检测环境变量：DEEPSEEK_API_KEY 优先于 OPENAI_API_KEY。本地确定性报告永远是真源，润色只改文字不改数据。",
        )
        run_button = st.button("运行内部初筛", type="primary", width="stretch")

    # 若用户从材料库选了具体 ID，则注入 envelope 和 strength_allowables；自由输入时为 None
    material_envelope = None
    allowables = None
    if material_id_chosen is not None:
        library = load_material_library()
        material_envelope = library.envelope_for(material_id_chosen)
        allowables = library.allowables_for(material_id_chosen)

    # 构造包含反向载荷的 Condition（如果用户输入了轴向力或弯矩）
    from material_eval.conditions import Condition
    condition = Condition.from_dimensions(
        dimensions,
        **({} if axial_force is None else {"axial_force": axial_force}),
        **({} if bending_moment is None else {"bending_moment": bending_moment}),
    )

    return (
        EvaluationRequest(
            material=material,
            part=part,
            dimensions=dimensions,
            retrieval_mode=retrieval_mode,
            laminate_stack=laminate_stack,
            material_envelope=material_envelope,
            condition=condition,
            strength_allowables=allowables,
            material_id=material_id_chosen,
        ),
        use_openai,
        run_button,
        material_id_chosen,  # may be None for free-entry / composite modes
    )


def render_material_form() -> tuple[MaterialCandidate, LaminateStack | None, str | None]:
    """Return (material, laminate_stack, material_id_or_none).

    material_id_or_none is non-None only when the user picks from the library.
    """
    st.header("2. 材料体系")
    material_mode = st.radio("材料模式", ["单一均质材料", "从基准材料库选择", "复合/杂化材料体系"])
    if material_mode == "单一均质材料":
        return (
            build_single_material(
                name=st.text_input("材料名称", "候选高强蛋白纤维材料"),
                category=st.selectbox(
                    "材料大类",
                    ["合成蛋白/生物基大分子", "碳纤维复合", "特种工程塑料", "特种合金"],
                ),
                density_g_cm3=st.number_input("密度 (g/cm³)", value=1.30, min_value=0.01),
                tensile_strength_mpa=st.number_input("抗拉强度 (MPa)", value=9600.0, min_value=0.0),
                elastic_modulus_gpa=st.number_input("弹性模量 (GPa)", value=100.0, min_value=0.0),
            ),
            None,
            None,  # no material_id for free-entry mode
        )
    if material_mode == "从基准材料库选择":
        library = load_material_library()
        material_ids = sorted(library.materials)
        labels = {material_id: library.materials[material_id].name for material_id in material_ids}
        selected_id = st.selectbox("基准材料", material_ids, format_func=labels.get)
        candidate = library.build_candidate(selected_id)
        material = library.materials[selected_id]
        with st.expander("属性来源与条件", expanded=False):
            st.write(f"形态：{material.form}")
            st.write(f"工艺/状态：{material.process}")
            for observation in library.observations_for(material_id=selected_id):
                normalized_suffix = ""
                if (
                    abs(observation.value - observation.canonical_value) > 1e-9
                    or observation.unit != observation.canonical_unit
                ):
                    normalized_suffix = f" → 计算值 {observation.canonical_value:g} {observation.canonical_unit}"
                st.markdown(
                    f"- `{observation.property_name}` = {observation.value:g} {observation.unit}；"
                    f"{observation.test_condition}；confidence={observation.confidence:.2f}{normalized_suffix}"
                )
            conflicts = library.detect_conflicts(material_id=selected_id)
            if conflicts:
                st.warning("该材料存在属性来源差异，报告结论需复核。")
        return candidate, None, selected_id  # return library material_id

    st.caption("MVP 使用线性混合定律，只作为初筛估算。")
    matrix_name = st.selectbox("基体", ["环氧树脂", "PEEK", "PLA/PHA降解树脂", "铝合金"])
    fiber_name = st.selectbox("增强体", ["合成蛛丝蛋白纤维", "T1000 碳纤维", "高强芳纶纤维"])
    vf = st.slider("增强体体积分数 (%)", min_value=10, max_value=80, value=60) / 100.0
    col_m, col_f = st.columns(2)
    with col_m:
        st.markdown("**基体参数**")
        matrix_density = st.number_input("密度(基体)", value=1.2, min_value=0.01)
        matrix_strength = st.number_input("强度(基体)", value=80.0, min_value=0.0)
        matrix_modulus = st.number_input("模量(基体)", value=3.0, min_value=0.0)
    with col_f:
        st.markdown("**增强体参数**")
        fiber_density = st.number_input("密度(增强)", value=1.3, min_value=0.01)
        fiber_strength = st.number_input("强度(增强)", value=9600.0, min_value=0.0)
        fiber_modulus = st.number_input("模量(增强)", value=100.0, min_value=0.0)
    material = build_composite_material(
        matrix_name=matrix_name,
        fiber_name=fiber_name,
        fiber_volume_fraction=vf,
        matrix_density=matrix_density,
        matrix_strength=matrix_strength,
        matrix_modulus=matrix_modulus,
        fiber_density=fiber_density,
        fiber_strength=fiber_strength,
        fiber_modulus=fiber_modulus,
    )
    laminate_stack = render_laminate_form(
        matrix_modulus=matrix_modulus,
        fiber_modulus=fiber_modulus,
        fiber_volume_fraction=vf,
    )
    return material, laminate_stack, None  # composite mode has no library material_id


def render_laminate_form(*, matrix_modulus: float, fiber_modulus: float, fiber_volume_fraction: float) -> LaminateStack | None:
    enabled = st.checkbox("启用 CLT 铺层初筛", value=True)
    if not enabled:
        return None

    vf = max(0.01, min(0.99, fiber_volume_fraction))
    vm = 1.0 - vf
    e1 = fiber_modulus * vf + matrix_modulus * vm
    e2 = 1.0 / (vf / max(fiber_modulus, 1e-6) + vm / max(matrix_modulus, 1e-6))
    g12 = max(0.1, e2 / 2.6)
    col_a, col_b = st.columns(2)
    with col_a:
        ply_thickness = st.number_input("单层厚度 (mm)", value=0.125, min_value=0.01, step=0.01)
        layup = st.selectbox("铺层模板", ["[0/90]s", "[0]2", "[0/+45/-45/90]s"])
    with col_b:
        nu12 = st.number_input("ν12", value=0.30, min_value=0.0, max_value=0.49, step=0.01)
        st.caption(f"估算单层 E1/E2/G12：{e1:.3g}/{e2:.3g}/{g12:.3g} GPa")

    if layup == "[0]2":
        angles = (0, 0)
    elif layup == "[0/+45/-45/90]s":
        angles = (0, 45, -45, 90, 90, -45, 45, 0)
    else:
        angles = (0, 90, 90, 0)

    return LaminateStack(
        plies=tuple(
            Lamina(
                e1_gpa=e1,
                e2_gpa=e2,
                g12_gpa=g12,
                nu12=nu12,
                thickness_mm=ply_thickness,
                angle_deg=angle,
            )
            for angle in angles
        )
    )


def render_dimension_form(part) -> dict[str, float]:
    st.header("3. 几何参数")
    return {
        item.key: st.slider(item.label, item.minimum, item.maximum, item.default)
        for item in part.geometry_inputs
    }


def render_load_inputs() -> tuple["Quantity | None", "Quantity | None"]:
    """Render axial force and bending moment inputs; return (axial_force, bending_moment) Quantities."""
    from material_eval.conditions import Quantity

    st.subheader("反向载荷（可选）")
    col_f, col_m = st.columns(2)
    with col_f:
        axial_val = st.number_input("轴向力", value=0.0, step=1.0, key="axial_force_val")
        axial_unit = st.selectbox("单位", ["N", "kN"], key="axial_force_unit")
    with col_m:
        moment_val = st.number_input("弯矩", value=0.0, step=1.0, key="bending_moment_val")
        moment_unit = st.selectbox("单位", ["N·m", "kN·m"], key="bending_moment_unit")

    axial_force = Quantity(value=axial_val, unit=axial_unit) if axial_val != 0.0 else None
    # UI shows "N·m"/"kN·m" but Pint needs "N*m"/"kN*m"
    _moment_unit_map = {"N·m": "N*m", "kN·m": "kN*m"}
    bending_moment = (
        Quantity(value=moment_val, unit=_moment_unit_map.get(moment_unit, moment_unit))
        if moment_val != 0.0
        else None
    )
    return axial_force, bending_moment


def render_material_summary(material: MaterialCandidate, *, material_id: str | None = None) -> None:
    st.subheader("当前评估对象")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("材料", material.name)
    c2.metric("密度", f"{material.density_g_cm3.typical:.3g} g/cm³")
    c3.metric("抗拉强度", f"{material.tensile_strength_mpa.typical:.4g} MPa")
    c4.metric("弹性模量", f"{material.elastic_modulus_gpa.typical:.4g} GPa")

    if material_id is not None:
        lib = load_material_library()
        env = lib.envelope_for(material_id)
        if env is not None and env.has_any_axis():
            env_caption = "✅ 已声明适用域"
        else:
            env_caption = "⚠️ 未声明适用域"
        has_three_point = False
        for prop in ("density_g_cm3", "tensile_strength_mpa", "elastic_modulus_gpa"):
            iv = lib.property_interval(material_id, prop)
            if iv and iv.high > iv.low:
                has_three_point = True
                break
        iv_caption = "✅ 三点区间数据" if has_three_point else "⚠️ 单点数据（按 confidence 自动展开）"
        st.caption(f"{env_caption}　·　{iv_caption}")


def maybe_polish_report(markdown: str, *, use_openai: bool) -> str:
    if not use_openai:
        return markdown
    polished = polish_report_with_llm(markdown)
    if polished.ok:
        provider_label = {"deepseek": "DeepSeek", "openai": "OpenAI"}.get(polished.provider, polished.provider)
        st.success(f"{provider_label} 润色完成。")
    else:
        st.warning(polished.error)
    return polished.text


def render_calculation(calculation) -> None:
    rows = calculation.as_rows()
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch")
    if calculation.metrics:
        chart_df = pd.DataFrame([
            {
                "指标": m.name,
                "low": m.value.low,
                "typical": m.value.typical,
                "high": m.value.high,
                "单位": m.value.unit or "",
            }
            for m in calculation.metrics
        ])
        fig = px.bar(
            chart_df,
            x="typical",
            y="指标",
            orientation="h",
            error_x=chart_df["high"] - chart_df["typical"],
            error_x_minus=chart_df["typical"] - chart_df["low"],
            text="单位",
            title="初筛指标概览（典型值 + 不确定度区间）",
        )
        fig.update_layout(height=320, showlegend=False, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, width="stretch")

    if calculation.warnings:
        st.warning("\n".join(f"- {item}" for item in calculation.warnings))

    with st.expander("计算假设", expanded=True):
        for assumption in calculation.assumptions:
            st.markdown(f"- {assumption}")


def render_laminate_result(laminate_result) -> None:
    if laminate_result is None:
        return
    st.subheader("复合铺层初筛")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ex", f"{laminate_result.ex_gpa.typical:.3g} GPa")
    c2.metric("Ey", f"{laminate_result.ey_gpa.typical:.3g} GPa")
    c3.metric("Gxy", f"{laminate_result.gxy_gpa.typical:.3g} GPa")
    c4.metric("总厚度", f"{laminate_result.total_thickness_mm.typical:.3g} mm")
    st.dataframe(
        pd.DataFrame(laminate_result.a_matrix, columns=["A1", "A2", "A6"]),
        hide_index=True,
        width="stretch",
    )
    if laminate_result.warnings:
        st.warning("\n".join(f"- {item}" for item in laminate_result.warnings))


def render_evidence(evidence_cards) -> None:
    if not evidence_cards:
        st.warning("未找到内部资料证据。")
        return
    for idx, card in enumerate(evidence_cards, start=1):
        with st.container(border=True):
            st.markdown(f"**[{idx}] {card.source_type}：`{card.source}`**")
            st.caption(f"检索分数：{card.score}")
            st.write(card.text)


def render_report(*, markdown: str, filename: str, report_path, run_id: int) -> None:
    st.caption(f"已导出到：{report_path}")
    st.download_button(
        "下载 Markdown 报告",
        data=markdown,
        file_name=filename,
        mime="text/markdown",
        width="stretch",
    )
    render_report_review(run_id)
    st.markdown(markdown)


def render_report_review(run_id: int) -> None:
    with st.expander("研发复核", expanded=False):
        status = st.selectbox(
            "复核状态",
            ["needs_experiment", "approved_for_next_step", "blocked"],
            format_func={
                "needs_experiment": "需补充实验",
                "approved_for_next_step": "可进入下一步",
                "blocked": "暂缓/阻断",
            }.get,
            key=f"review_status_{run_id}",
        )
        reviewer = st.text_input("复核人", value="内部研发", key=f"reviewer_{run_id}")
        comment = st.text_area("复核意见", value="", key=f"review_comment_{run_id}")
        if st.button("保存复核意见", width="stretch", key=f"save_review_{run_id}"):
            save_report_review(run_id=run_id, reviewer=reviewer, status=status, comment=comment)
            st.success("复核意见已保存。")

        reviews = list_report_reviews(run_id)
        if reviews:
            st.dataframe(pd.DataFrame(reviews), hide_index=True, width="stretch")


def render_recent_runs() -> None:
    runs = list_recent_runs()
    st.subheader("最近评估记录")
    if not runs:
        st.caption("暂无记录。")
        return
    st.dataframe(pd.DataFrame(runs), hide_index=True, width="stretch")


def render_rag_evaluation_panel() -> None:
    st.subheader("检索评估")
    if not st.button("运行默认检索评估", width="stretch"):
        st.caption("使用固定问题集检查证据召回命中率和检索方法分布。")
        return
    result = run_retrieval_evaluation(default_retrieval_questions())
    c1, c2 = st.columns(2)
    c1.metric("问题数", result.total_questions)
    c2.metric("命中率", f"{result.hit_rate:.0%}")
    rows = [
        {
            "问题": item.query,
            "命中": "是" if item.hit else "否",
            "Top 方法": item.top_method,
            "返回来源": ", ".join(item.returned_sources),
        }
        for item in result.items
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def render_safety_report(safety_report) -> None:
    if safety_report is None:
        st.info("未启用失效分析：材料未声明 strength_allowables（核心材料：Ti-6Al-4V / PA66-GF30 / Carbon-Epoxy 准各向同性），或工况未输入轴向力/弯矩。")
        return

    method_label = {"von_mises": "von Mises 屈服", "tsai_wu": "Tsai-Wu 复合材料"}.get(safety_report.method, safety_report.method)
    st.subheader(f"安全性评估（{method_label}）")

    status = safety_report.status
    sf_iv = safety_report.governing.value

    if status == "pass":
        st.success(f"✓ pass — 控制层 {safety_report.governing.location}，SF.low = {sf_iv.low:.2f}")
    elif status == "marginal":
        st.warning(f"⚠ marginal — 控制层 {safety_report.governing.location}，SF.low = {sf_iv.low:.2f}（区间下界余量不足 1.5，建议补数据或加保险）")
    else:
        st.error(f"✗ fail — 控制层 {safety_report.governing.location}，SF.typical = {sf_iv.typical:.2f} < 1.0（典型工况下不通过）")

    rows = []
    for f in safety_report.factors:
        rows.append({
            "评估位置": f.location,
            "安全系数 (low / typical / high)": f.value.format(),
            "主导模式": f.dominant_mode,
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    if safety_report.method == "tsai_wu":
        st.caption("*Tsai-Wu F12 耦合系数 f12_star 采用 seed 中指定值（默认 0 = Tsai-Hill 退化，工程默认）；待业务专家用真实实验数据校准。*")


# ---------------------------------------------------------------------------
# 顶部"评估总览"面板 + 3D 蓝图（Phase 2.5 retro: legacy 视觉感回归）
# ---------------------------------------------------------------------------

def render_evaluation_summary(draft, *, run_id: int) -> None:
    """一眼看结论的顶部面板。汇总 SF 状态、控制点、关键风险。"""
    material_name = draft.material.name
    part_name = draft.part.name
    domain = draft.part.domain

    # 状态结论
    safety = draft.safety_report
    if safety is None:
        status = "info"
        status_text = "ℹ️ 未启用失效分析"
        sf_text = "—"
        location_text = "—"
        mode_text = "—"
        method_text = "—"
    else:
        s = safety.status
        if s == "pass":
            status, status_text = "success", "🟢 PASS — 满足设计安全余量"
        elif s == "marginal":
            status, status_text = "warning", "🟡 MARGINAL — 区间下界余量不足，建议补数据/做实验"
        else:
            status, status_text = "error", "🔴 FAIL — 典型工况下不通过，需换材料或改设计"
        sf_text = safety.governing.value.format()
        location_text = safety.governing.location
        mode_text = safety.governing.dominant_mode
        method_text = {"von_mises": "von Mises 屈服（金属/塑料）", "tsai_wu": "Tsai-Wu 复合材料失效"}.get(safety.method, safety.method)

    # 顶部 banner
    {"success": st.success, "warning": st.warning, "error": st.error, "info": st.info}[status](
        f"### {status_text}\n\n**评估对象**：{material_name} 用于 {domain} / {part_name}　·　Run #{run_id}"
    )

    # 5 个关键指标卡片
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("安全系数（low / typ / high）", sf_text)
    c2.metric("控制位置", location_text)
    c3.metric("失效模式", mode_text)
    c4.metric("评估方法", method_text, help="von Mises 用于金属/塑料；Tsai-Wu 用于复合材料")
    c5.metric("拓扑", draft.part.topology)

    # 工况包络一行汇总
    env = draft.envelope_report if hasattr(draft, "envelope_report") else None
    if env is not None:
        if env.violations:
            st.warning(f"⚠️ 工况包络越界 {len(env.violations)} 项")
        elif env.has_declared_envelope:
            st.caption("✅ 工况在材料适用域内")
        else:
            st.caption("⚠️ 该材料未声明工况适用域")


def render_refusal_summary(refusal) -> None:
    """Refusal 路径的红底大字总结。"""
    material_name = refusal.material.name
    part_name = refusal.part.name
    violations = refusal.envelope_report.violations
    st.error(
        f"### ⛔ REFUSAL — 未出具评估\n\n"
        f"**{material_name}** 用于 **{part_name}** 时，工况输入超出材料适用域：\n\n"
        + "\n".join(
            f"- **{v.axis}** = {v.input_value} 超出允许范围 [{v.allowed_range[0]}, {v.allowed_range[1]}]"
            for v in violations
        )
        + "\n\n→ 详细建议（替代材料 / 补数据）见下方报告。"
    )


def render_blueprint_section(topology: str, dims: dict[str, float]) -> None:
    """工程初筛 tab 顶部的 3D 蓝图双视图（宏观几何 + 应力示意）。"""
    with st.expander("📐 3D 结构蓝图 · 应力示意", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(render_3d_blueprint(topology, dims, "macro"), use_container_width=True)
        with col2:
            st.plotly_chart(render_3d_blueprint(topology, dims, "micro"), use_container_width=True)
        st.caption("*左：宏观几何示意；右：应力定性分布示意（非真实 CAE 仿真）。视觉用于工程直觉，数值结论以下方表格为准。*")


# ---------------------------------------------------------------------------
# 全网检索（Tavily） + 商业八维剖析（LLM 生成）
# ---------------------------------------------------------------------------

def render_web_search_section(draft) -> None:
    """全网检索 tab — Tavily 实时联网检索补充内部资料库。"""
    st.markdown("### 🌐 全网检索（Tavily 实时）")
    st.caption("内部知识库只有有限资料；全网检索可补充行业标准、供应商资料、最新论文等公开信息。需要 `TAVILY_API_KEY`。")

    default_query = f"{draft.material.name} {draft.part.name} {draft.part.domain} 应用 替代"
    query = st.text_input("检索 query", value=default_query, key="web_query")
    max_results = st.slider("结果数", 3, 10, 5, key="web_max")
    if not st.button("🔎 开始全网检索", key="web_run_btn"):
        st.info("点击按钮才会调用 Tavily（避免每次评估都消耗 API 配额）。")
        return

    with st.spinner("Tavily 检索中..."):
        result = search_web(query, max_results=max_results)
    if not result.ok:
        st.warning(result.error)
        return
    if result.answer:
        st.success(f"💡 **全网综合回答**：{result.answer}")
    if not result.hits:
        st.info("Tavily 未返回结果。")
        return
    st.markdown("#### 检索结果")
    for idx, hit in enumerate(result.hits, 1):
        with st.expander(f"[{idx}] {hit.title}　·　score={hit.score:.2f}", expanded=(idx == 1)):
            st.markdown(f"**URL**：{hit.url}")
            st.write(hit.content_snippet)


def render_eight_dim_section(draft) -> None:
    """商业八维剖析 tab — LLM 生成 8 维定性 + 数值对比。"""
    st.markdown("### 🏆 商业八维全生命周期剖析")
    st.caption(
        "用 LLM 把材料 + 零件 + 工程计算 + 证据汇总为 8 维商业级剖析，"
        "覆盖静载/疲劳/工艺/抗性/微观/经济/ESG/壁垒。需要 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY`。"
        "本视图为商业沟通用，不替代工程计算/失效分析。"
    )
    if not st.button("🚀 生成八维剖析（调用 LLM）", key="eightdim_run_btn"):
        st.info("点击按钮才会调用 LLM（避免每次评估都消耗 API 配额）。")
        return

    calc_summary_lines = [
        f"- {m.name}: {m.value.format()} — {m.description}"
        for m in draft.calculation.metrics
    ]
    if draft.safety_report is not None:
        calc_summary_lines.append(
            f"- 失效分析（{draft.safety_report.method}）: 控制点 {draft.safety_report.governing.location}，"
            f"SF={draft.safety_report.governing.value.format()}，状态={draft.safety_report.status}"
        )
    calc_summary = "\n".join(calc_summary_lines)
    evidence_lines = [f"- {ec.snippet[:200]}" for ec in (draft.evidence_cards or [])[:3]]
    evidence_summary = "\n".join(evidence_lines)

    with st.spinner("LLM 正在生成八维剖析（最长 2 分钟）..."):
        report = analyze_eight_dimensions(
            material_name=draft.material.name,
            part_name=draft.part.name,
            domain=draft.part.domain,
            constraint=getattr(draft.part, "constraint", ""),
            calculation_summary=calc_summary,
            evidence_summary=evidence_summary,
        )
    if not report.ok:
        st.error(f"八维剖析生成失败：{report.error}")
        if report.raw_json:
            with st.expander("LLM 原始输出（调试用）"):
                st.code(report.raw_json)
        return
    st.success(f"✅ 八维剖析生成完成（provider: {report.provider}）")

    # 顶部：市场定位
    st.markdown(f"#### 🎯 市场定位：{report.market_tier}")
    st.info(report.market_verdict)
    st.divider()

    # 八维：每维一个子 tab
    if report.dimensions:
        dim_tabs = st.tabs([d.dim for d in report.dimensions])
        for tab, d in zip(dim_tabs, report.dimensions):
            with tab:
                left, right = st.columns([1.5, 1])
                with left:
                    st.markdown("#### 🔍 定性论证")
                    for detail in d.details:
                        st.markdown(f"- {detail}")
                with right:
                    df = pd.DataFrame({
                        "对标对象": ["现役基准", "本案设计"],
                        d.chart_metric: [d.base_val, d.new_val],
                    })
                    fig = px.bar(
                        df, x=d.chart_metric, y="对标对象", orientation="h",
                        text=d.chart_metric, color="对标对象",
                        color_discrete_sequence=["#a9a9a9", "#1f77b4"],
                        title=d.chart_metric,
                    )
                    fig.update_layout(showlegend=False, height=200, margin=dict(l=10, r=10, t=40, b=10))
                    st.plotly_chart(fig, use_container_width=True)

    if report.summary:
        st.info(f"**📌 八维小结：** {report.summary}")
    st.divider()

    # 结案决议
    if report.grand_verdict is not None:
        gv = report.grand_verdict
        st.markdown("### ⚖️ 商业落地决议")
        st.success(gv.summary)
        col_pro, col_con = st.columns(2)
        with col_pro:
            st.markdown("##### 🌟 核心投产优势")
            for s in gv.strengths:
                st.markdown(f"- ✅ {s}")
        with col_con:
            st.markdown("##### ⚠️ 致命短板与风险")
            for w in gv.weaknesses:
                st.markdown(f"- ❌ {w}")

    if report.reference_sources:
        st.markdown("#### 📚 数据来源")
        for ref in report.reference_sources:
            st.markdown(f"- 🔗 {ref}")
