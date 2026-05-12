from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st

from material_eval.artifacts import write_markdown_report
from material_eval.catalog import Catalog
from material_eval.evaluation import EvaluationRequest, run_evaluation, save_evaluation
from material_eval.laminates import Lamina, LaminateStack
from material_eval.material_property_library import MaterialPropertyLibrary
from material_eval.materials import MaterialCandidate, build_composite_material, build_single_material
from material_eval.openai_provider import polish_report_with_openai
from material_eval.rag_eval import default_retrieval_questions, run_retrieval_evaluation
from material_eval.storage import list_recent_runs, list_report_reviews, save_report_review


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

    request, use_openai, run_button = render_sidebar(catalog)
    render_material_summary(request.material)

    st.divider()

    if not run_button:
        render_recent_runs()
        render_rag_evaluation_panel()
        st.info("选择左侧配置后点击“运行内部初筛”。")
        return

    draft = run_evaluation(request)
    report_markdown = maybe_polish_report(draft.report.markdown, use_openai=use_openai)
    run_id = save_evaluation(draft, report_markdown=report_markdown)
    report_path = write_markdown_report(filename=f"{run_id}-{draft.report.filename}", markdown=report_markdown)

    tab_calc, tab_evidence, tab_report, tab_history, tab_eval = st.tabs(["工程初筛", "证据卡", "中文报告", "评估记录", "检索评估"])
    with tab_calc:
        st.success(f"评估已保存，Run ID: {run_id}")
        render_calculation(draft.calculation)
        render_laminate_result(draft.laminate_result)
    with tab_evidence:
        render_evidence(draft.evidence_cards)
    with tab_report:
        render_report(markdown=report_markdown, filename=draft.report.filename, report_path=report_path, run_id=run_id)
    with tab_history:
        render_recent_runs()
    with tab_eval:
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


def render_sidebar(catalog: Catalog) -> tuple[EvaluationRequest, bool, bool]:
    with st.sidebar:
        st.header("1. 目标零部件")
        mvp_only = st.toggle("只显示 MVP 首测场景", value=True)
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

        material, laminate_stack = render_material_form()
        dimensions = render_dimension_form(part)

        st.header("4. 生成")
        retrieval_label = st.radio(
            "证据检索",
            ["BM25 关键词检索", "BGE-M3 语义检索（可选）"],
            horizontal=True,
        )
        retrieval_mode = "embedding" if retrieval_label.startswith("BGE-M3") else "bm25"
        if retrieval_mode == "embedding":
            st.caption("首次启用会加载 BAAI/bge-m3；未安装 FlagEmbedding 时自动回退 BM25。")
        use_openai = st.checkbox("使用 OpenAI 润色报告（可选）", value=False)
        run_button = st.button("运行内部初筛", type="primary", width="stretch")

    return (
        EvaluationRequest(
            material=material,
            part=part,
            dimensions=dimensions,
            retrieval_mode=retrieval_mode,
            laminate_stack=laminate_stack,
        ),
        use_openai,
        run_button,
    )


def render_material_form() -> tuple[MaterialCandidate, LaminateStack | None]:
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
        return candidate, None

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
    return material, laminate_stack


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


def render_material_summary(material: MaterialCandidate) -> None:
    st.subheader("当前评估对象")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("材料", material.name)
    c2.metric("密度", f"{material.density_g_cm3:.3g} g/cm³")
    c3.metric("抗拉强度", f"{material.tensile_strength_mpa:.4g} MPa")
    c4.metric("弹性模量", f"{material.elastic_modulus_gpa:.4g} GPa")


def maybe_polish_report(markdown: str, *, use_openai: bool) -> str:
    if not use_openai:
        return markdown
    polished = polish_report_with_openai(markdown)
    if polished.ok:
        st.success("OpenAI 润色完成。")
    else:
        st.warning(polished.error)
    return polished.text


def render_calculation(calculation) -> None:
    rows = calculation.as_rows()
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch")
    if rows:
        fig = px.bar(
            df,
            x="数值",
            y="指标",
            orientation="h",
            text="单位",
            title="初筛指标概览",
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
    c1.metric("Ex", f"{laminate_result.ex_gpa:.3g} GPa")
    c2.metric("Ey", f"{laminate_result.ey_gpa:.3g} GPa")
    c3.metric("Gxy", f"{laminate_result.gxy_gpa:.3g} GPa")
    c4.metric("总厚度", f"{laminate_result.total_thickness_mm:.3g} mm")
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
