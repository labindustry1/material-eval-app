import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ================= UI 页面配置 =================
st.set_page_config(page_title="工业材料全景数据推演系统", layout="wide", initial_sidebar_state="expanded")

st.title("⚙️ 材料本征与零部件代换全景推演系统 (v9.0 终极矩阵版)")
st.caption("基准对标 | 图表双轨解析 | 等效数学建模 | 虚拟案例库 | 全维结案看板")

# ================= 侧边栏：全参数输入 =================
with st.sidebar:
    st.header("1. 目标应用与基准")
    domain = st.selectbox(
        "下游目标工况",
        ["工业机器人 (关注刚度与挠度)", "航空航天与无人机 (关注极致比强度)", "医疗器械结构件 (关注疲劳与相容性)"]
    )

    st.header("2. 核心物性参数")
    density = st.number_input("密度 (g/cm³)", value=1.30, format="%.2f")
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    
    st.header("3. 物理形态约束")
    material_form = st.selectbox(
        "成型宏观形态",
        ["纤维/长丝 (单向受力/复材增强相)", "各向同性体块/树脂/金属替代品 (多向受力)"]
    )

    st.header("4. 高阶参数 (Sparse Data)")
    with st.expander("展开填补高阶盲区"):
        elongation = st.number_input("断裂伸长率 (%)", value=0.0)
        water_abs = st.number_input("饱和吸水率 (%)", value=0.0)

    st.header("5. 算力引擎")
    api_key = st.text_input("DeepSeek API Key", type="password", value=st.secrets.get("DEEPSEEK_API_KEY", ""))

# ================= 主界面：评估逻辑 =================

if st.button("运行全景数据推演与案例生成引擎", type="primary"):
    if not api_key:
        st.warning("⚠️ 需配置 API Key 方可运行。")
        st.stop()

    # 压榨大模型输出极限的超长 JSON 结构指令
    system_prompt = f"""
    你是一个全景材料数据推演引擎。
    参数：领域={domain}, 形态={material_form}, 密度={density}, 强度={strength}, 模量={modulus}, 伸长率={elongation}%, 吸水率={water_abs}%。
    
    【强制要求】
    1. 客观冷峻，纯数据支撑。
    2. 严格按以下 JSON 结构输出，不可省略任何字段，绝不包含 Markdown。
    
    {{
      "radar_score": {{"比强度": 100, "比刚度": 60, "轻量化效能": 95, "加工成型率": 45, "疲劳极限": 50}},
      "base_metrics": [
        {{"metric": "绝对强度 (MPa)", "Al7075": 570, "T1000": 3000, "NewMat": {strength}}},
        {{"metric": "绝对模量 (GPa)", "Al7075": 71, "T1000": 160, "NewMat": {modulus}}},
        {{"metric": "比强度 (kN·m/kg)", "Al7075": 203, "T1000": 1875, "NewMat": {strength/density}}},
        {{"metric": "比模量 (GPa·cm³/g)", "Al7075": 25.3, "T1000": 100, "NewMat": {modulus/density}}}
      ],
      "component_simulation": {{
        "part_name": "典型主承力部件 (悬臂梁/机臂)",
        "design_goal": "等刚度代换 (控制末端挠度不变)",
        "math_process": "根据公式 $$ \\delta = \\frac{{F L^3}}{{3 E I}} $$，令新旧挠度相等，则 $E_1 I_1 = E_2 I_2$。因新模量 $E_2={modulus}$GPa，铝 $E_1=71$GPa，则截面惯性矩需求 $I_2 = 0.71 I_1$。代入管材质量公式推导最终减重。",
        "table_data": [
          {{"param": "模量 E (GPa)", "base": 71, "new": {modulus}}},
          {{"param": "等效截面惯性矩 I", "base": 1.0, "new": 0.71}},
          {{"param": "预估总重 (kg)", "base": 4.25, "new": 1.35}}
        ],
        "chart_title": "等刚度代换下零部件重量对比 (kg)",
        "chart_base_val": 4.25,
        "chart_new_val": 1.35
      }},
      "five_dimensions_analysis": [
        {{"dim": "静态拉压极限", "details": ["数据点1", "数据点2"]}},
        {{"dim": "动态疲劳与形变", "details": ["基于伸长率和模量的疲劳推演", "数据点2"]}},
        {{"dim": "界面与加工约束", "details": ["形态导致的工艺难点", "数据点2"]}},
        {{"dim": "环境与理化耐受", "details": ["基于吸水率或常规预估的耐受分析", "数据点2"]}},
        {{"dim": "综合轻量化收益", "details": ["减重百分比在系统层面的二次收益", "数据点2"]}}
      ],
      "case_studies": [
        {{
          "target_part": "轻载高速连杆",
          "traditional_mat": "碳纤维T300管",
          "new_mat_design": "新材料单向拉挤管",
          "quantified_benefit": "因绝对强度极高，壁厚可削减50%，整件减重30%，惯量大幅降低提升电机响应。"
        }},
        {{
          "target_part": "重载高精法兰",
          "traditional_mat": "7075铝合金",
          "new_mat_design": "新材料复合铺层",
          "quantified_benefit": "因模量不足(100 vs 71优势不大)，为达到极小公差，需增加截面积，减重收益收窄至15%，性价比低。"
        }}
      ],
      "final_verdict": {{
        "core_strengths": ["列出2条带数据的核心优势"],
        "hard_limits": ["列出2条带数据的致命缺陷"],
        "go_parts": ["明确列出3个绝对推荐使用的零部件名称"],
        "no_go_parts": ["明确列出2个严禁使用的零部件名称(容易失效)"]
      }}
    }}
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    API_URL = API_URL.encode('ascii', 'ignore').decode('ascii').strip()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.15}

    with st.spinner("算力引擎超频运行：解析海量矩阵与推演案例..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=100)
            response.raise_for_status()
            clean_json_str = response.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json_str)
            
            st.success("✅ 全景数据矩阵生成完毕。")
            
            # ================= I. 材料本征参数 (图 + 表) =================
            st.subheader("I. 材料本征参数对标矩阵 (Base Material Matrix)")
            
            # 顶部图表
            col_radar, col_charts = st.columns([1, 2.5])
            with col_radar:
                df_radar = pd.DataFrame(dict(r=list(data['radar_score'].values()), theta=list(data['radar_score'].keys())))
                fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True, title="多维潜力评估")
                fig_radar.update_traces(fill='toself', line_color='#1f77b4')
                fig_radar.update_layout(margin=dict(l=30, r=30, t=40, b=20), height=350)
                st.plotly_chart(fig_radar, use_container_width=True)

            with col_charts:
                base_metrics = data['base_metrics']
                r1c1, r1c2 = st.columns(2)
                r2c1, r2c2 = st.columns(2)
                
                def plot_mini(md, container):
                    df_m = pd.DataFrame({"Material": ["Al7075", "T1000", "NewMat"], "Value": [md['Al7075'], md['T1000'], md['NewMat']]})
                    fig = px.bar(df_m, x="Material", y="Value", text_auto='.2s', color="Material",
                                 color_discrete_map={"Al7075": "#a6b8c7", "T1000": "#5a6e7f", "NewMat": "#d62728"})
                    fig.update_layout(title=md['metric'], showlegend=False, height=180, margin=dict(l=10, r=10, t=30, b=10))
                    container.plotly_chart(fig, use_container_width=True)

                plot_mini(base_metrics[0], r1c1)
                plot_mini(base_metrics[1], r1c2)
                plot_mini(base_metrics[2], r2c1)
                plot_mini(base_metrics[3], r2c2)

            # 底部补充数据表格 (图表双轨)
            st.markdown("##### 📝 本征参数量化表")
            df_base = pd.DataFrame(base_metrics)
            df_base.columns = ["指标", "航空铝合金 7075", "碳纤维 T1000", "输入新材料"]
            st.dataframe(df_base, use_container_width=True, hide_index=True)

            st.divider()

            # ================= II. 零部件仿真计算 (图 + 表 + 公式) =================
            st.subheader("II. 零部件级代换推演 (Component-Level Simulation)")
            sim = data.get("component_simulation", {})
            st.markdown(f"**设定工况：** `{sim.get('part_name')}` | **优化目标：** `{sim.get('design_goal')}`")
            
            with st.container(border=True):
                st.markdown("##### 📐 力学等效数学推演")
                st.markdown(sim.get('math_process'))
            
            # 图表并排
            sim_col_tbl, sim_col_chart = st.columns([1.5, 1])
            with sim_col_tbl:
                st.markdown("##### 📊 成型件参数演变表")
                df_sim = pd.DataFrame(sim.get("table_data", []))
                df_sim.columns = ["推演参数", "传统基准方案", "新材料代换方案"]
                st.dataframe(df_sim, use_container_width=True, hide_index=True)
            with sim_col_chart:
                # 针对零部件数据的对比柱状图
                df_sim_chart = pd.DataFrame({
                    "方案": ["传统基准", "新材料代换"],
                    "重量 (kg)": [sim.get("chart_base_val"), sim.get("chart_new_val")]
                })
                fig_sim = px.bar(df_sim_chart, x="方案", y="重量 (kg)", text="重量 (kg)", color="方案", 
                                 color_discrete_map={"传统基准": "#7f7f7f", "新材料代换": "#2ca02c"},
                                 title=sim.get("chart_title"))
                fig_sim.update_layout(height=250, showlegend=False, margin=dict(l=10, r=10, t=40, b=10))
                st.plotly_chart(fig_sim, use_container_width=True)

            st.divider()

            # ================= III. 5大维度深度剖析 =================
            st.subheader("III. 核心工程维度深度剖析 (Five-Dimensional Deep Dive)")
            dims = data.get("five_dimensions_analysis", [])
            tabs = st.tabs([d['dim'] for d in dims])
            for i, tab in enumerate(tabs):
                with tab:
                    for detail in dims[i]['details']:
                        st.markdown(f"- {detail}")

            st.divider()

            # ================= IV. 落地案例库 =================
            st.subheader("IV. 典型部件代换对标案例 (Virtual Case Studies)")
            cases = data.get("case_studies", [])
            cols_case = st.columns(len(cases))
            for i, case in enumerate(cases):
                with cols_case[i]:
                    with st.container(border=True):
                        st.markdown(f"#### ⚙️ {case.get('target_part')}")
                        st.info(f"**🆚 替代对象:** {case.get('traditional_mat')}\n\n**🛠️ 新方案:** {case.get('new_mat_design')}")
                        st.success(f"**📈 收益量化:** {case.get('quantified_benefit')}")

            st.divider()

            # ================= V. 全维结案看板 =================
            st.subheader("V. 首席工程决策看板 (Final Engineering Verdict)")
            verdict = data.get("final_verdict", {})
            
            v_col1, v_col2 = st.columns(2)
            with v_col1:
                st.success("##### 🌟 核心工程优势 (Core Strengths)")
                for s in verdict.get('core_strengths', []): st.markdown(f"- {s}")
                
                st.info("##### ✅ 强烈推荐应用部件 (Go-Parts)")
                for g in verdict.get('go_parts', []): st.markdown(f"- 🟢 {g}")
                
            with v_col2:
                st.error("##### ⚠️ 致命物理短板 (Hard Limits)")
                for w in verdict.get('hard_limits', []): st.markdown(f"- {w}")
                
                st.warning("##### 🚫 严禁越线应用部件 (No-Go-Parts)")
                for ng in verdict.get('no_go_parts', []): st.markdown(f"- 🔴 {ng}")

        except Exception as e:
            st.error(f"引擎过载或网络错误，请重试。追踪: {str(e)}")
