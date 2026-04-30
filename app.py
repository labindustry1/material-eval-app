import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ================= UI 页面配置 =================
st.set_page_config(page_title="工业级材料量化推演系统", layout="wide", initial_sidebar_state="expanded")

st.title("⚙️ 材料本征与零部件代换量化推演系统 (v8.0 工业生产版)")
st.caption("基准对标 | 等刚度/等强度代换计算 | 多维矩阵分析 | 纯数据推演")

# ================= 侧边栏：全参数输入 =================
with st.sidebar:
    st.header("1. 目标应用与基准")
    domain = st.selectbox(
        "下游目标工况",
        ["工业机器人 (关注刚度与末端挠度)", "航空航天与无人机 (关注极致轻量化)", "医疗器械结构件 (关注疲劳与相容性)"]
    )

    st.header("2. 核心物性参数")
    density = st.number_input("密度 (g/cm³)", value=1.30, format="%.2f")
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    
    st.header("3. 物理形态约束")
    material_form = st.selectbox(
        "成型宏观形态",
        ["纤维/长丝 (复合材料增强相/单向受力)", "各向同性体块/树脂/金属替代品 (多向受力)"]
    )

    st.header("4. 云端算力引擎")
    api_key = st.text_input("DeepSeek API Key", type="password", value=st.secrets.get("DEEPSEEK_API_KEY", ""))

# ================= 主界面：评估逻辑 =================

if st.button("运行工业级计算与对标引擎", type="primary"):
    if not api_key:
        st.warning("⚠️ 需配置 API Key 方可运行。")
        st.stop()

    # 极度严苛的工程指令，强制要求公式推演与结构化 JSON
    system_prompt = f"""
    你是一个工业级的材料力学仿真与计算引擎。
    输入参数：领域={domain}, 形态={material_form}, 密度={density}, 强度={strength}, 模量={modulus}。
    
    【核心计算要求】
    1. 必须客观、冷峻，绝对禁止使用“我建议”、“首席科学家”等拟人化主观词汇，全篇使用数据说话。
    2. 必须包含【单一材料性能】与【成型零部件数据】的严格区分。
    3. 在零部件推演中，必须输出具体的力学代换计算过程（如悬臂梁挠度公式），必须使用 LaTeX 语法（用 $ 包裹行内公式，$$ 包裹独立公式段）。
    
    只输出纯 JSON，不含任何其他标记。格式必须严格遵守：
    {{
      "radar_score": {{"比强度": 100, "比刚度": 60, "轻量化": 95, "加工容错": 45, "动态疲劳": 50}},
      "base_materials_comparison": [
        {{"metric": "绝对强度 (MPa)", "Al7075": 570, "T1000": 3000, "NewMat": {strength}}},
        {{"metric": "绝对模量 (GPa)", "Al7075": 71, "T1000": 160, "NewMat": {modulus}}},
        {{"metric": "比强度 (kN·m/kg)", "Al7075": 203, "T1000": 1875, "NewMat": {strength/density}}},
        {{"metric": "比模量 (GPa·cm³/g)", "Al7075": 25.3, "T1000": 100, "NewMat": {modulus/density}}}
      ],
      "component_simulation": {{
        "part_name": "典型机械臂悬臂梁 (假设长1000mm, 承载100N)",
        "design_goal": "等刚度代换 (维持相同的末端静态挠度)",
        "math_process": "根据悬臂梁挠度公式 $$ \\delta = \\frac{{F L^3}}{{3 E I}} $$ 为保证挠度 $\\delta$ 不变，要求 $E_1 I_1 = E_2 I_2$。已知新材料模量 $E_2={modulus}$ GPa，原铝合金 $E_1=71$ GPa。则所需截面惯性矩比值为 $I_2 / I_1 = 71 / {modulus}$。在管径固定的前提下，可精确计算壁厚削减量及最终减重比。",
        "data_table": [
          {{"parameter": "目标模量 E (GPa)", "traditional": "71 (铝合金)", "proposed": "{modulus} (新材料)"}},
          {{"parameter": "等效截面惯性矩 I", "traditional": "基准值 1.0 I", "proposed": "0.71 I (需削减壁厚)"}},
          {{"parameter": "成型部件总重 (预估)", "traditional": "4.25 kg", "proposed": "1.35 kg (减重约 68%)"}}
        ]
      }},
      "multi_angle_analysis": [
        {{"angle": "静态承载效能", "detail": "数据点1；数据点2"}},
        {{"angle": "动态变形控制", "detail": "数据点1；数据点2"}},
        {{"angle": "成型工艺数据约束", "detail": "针对形态的具体加工参数约束"}}
      ],
      "final_conclusion": "纯数据总结：该材料在某指标上提升X倍，但在某指标上存在Y的硬伤。综合判定其最佳适用部件为Z。"
    }}
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    API_URL = API_URL.encode('ascii', 'ignore').decode('ascii').strip()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.1}

    with st.spinner("算力引擎启动：正在进行本征参数对标与零部件等效计算..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            clean_json_str = response.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json_str)
            
            st.success("✅ 物理建模与代换计算完成。")
            
            # ================= 1. 顶层仪表盘 =================
            st.subheader("I. 材料多维本征参数对标 (Base Material Properties)")
            
            col_radar, col_charts = st.columns([1, 2.5])
            
            with col_radar:
                radar_data = data['radar_score']
                df_radar = pd.DataFrame(dict(r=list(radar_data.values()), theta=list(radar_data.keys())))
                fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True, title="综合能力图谱")
                fig_radar.update_traces(fill='toself', line_color='#1f77b4')
                fig_radar.update_layout(margin=dict(l=30, r=30, t=40, b=20), height=350)
                st.plotly_chart(fig_radar, use_container_width=True)

            with col_charts:
                # 矩阵化图表：将 4 个基础指标分为 2x2 网格
                base_comps = data['base_materials_comparison']
                if len(base_comps) >= 4:
                    row1_col1, row1_col2 = st.columns(2)
                    row2_col1, row2_col2 = st.columns(2)
                    
                    def plot_mini_bar(metric_dict, container):
                        df_m = pd.DataFrame({
                            "Material": ["铝合金7075", "碳纤维T1000", "输入新材料"],
                            "Value": [metric_dict['Al7075'], metric_dict['T1000'], metric_dict['NewMat']]
                        })
                        fig = px.bar(df_m, x="Material", y="Value", text_auto='.2s', color="Material",
                                     color_discrete_map={"铝合金7075": "#a6b8c7", "碳纤维T1000": "#5a6e7f", "输入新材料": "#d62728"})
                        fig.update_layout(title=metric_dict['metric'], showlegend=False, height=200, margin=dict(l=10, r=10, t=30, b=10))
                        container.plotly_chart(fig, use_container_width=True)

                    plot_mini_bar(base_comps[0], row1_col1)
                    plot_mini_bar(base_comps[1], row1_col2)
                    plot_mini_bar(base_comps[2], row2_col1)
                    plot_mini_bar(base_comps[3], row2_col2)

            st.divider()

            # ================= 2. 零部件仿真计算过程 =================
            st.subheader("II. 零部件级代换推演与计算过程 (Component-Level Simulation)")
            sim = data.get("component_simulation", {})
            
            st.markdown(f"**设定工况：** `{sim.get('part_name')}`")
            st.markdown(f"**优化目标：** `{sim.get('design_goal')}`")
            
            # 展示硬核数学推导过程 (LaTeX 支持)
            with st.container(border=True):
                st.markdown("##### 📐 力学代换推导过程")
                st.markdown(sim.get('math_process'))
            
            # 零部件成型后的数据对比表格
            st.markdown("##### 📊 成型零部件物理参数对比")
            df_sim = pd.DataFrame(sim.get("data_table", []))
            df_sim.columns = ["对比参数", "基准材料方案", "新材料代换方案"]
            st.dataframe(df_sim, use_container_width=True, hide_index=True)

            st.divider()

            # ================= 3. 多维角度客观评述 =================
            st.subheader("III. 多维角度客观评价 (Multi-Angle Evaluation)")
            cols_angle = st.columns(len(data.get("multi_angle_analysis", [])))
            for i, angle in enumerate(data.get("multi_angle_analysis", [])):
                with cols_angle[i]:
                    st.info(f"**{angle['angle']}**")
                    # 将分号分隔的文本转为项目符号列表
                    points = angle['detail'].split('；')
                    for p in points:
                        if p.strip(): st.markdown(f"- {p.strip()}")

            st.divider()

            # ================= 4. 最终数据总结论 =================
            st.subheader("IV. 最终工程判定数据看板 (Final Data Verdict)")
            st.success(data.get('final_conclusion'))

        except Exception as e:
            st.error(f"计算中断，请重试。错误追踪: {str(e)}")
