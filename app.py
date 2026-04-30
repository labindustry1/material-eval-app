import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse

# ================= UI 页面配置 =================
st.set_page_config(page_title="材料工业级全景推演引擎", layout="wide", initial_sidebar_state="expanded")

st.title("🧬 材料本征与系统级效应全景推演引擎 (v11.0 终极融合版)")
st.caption("本征对标矩阵 | 数学等效推演 | 缺失参数图表化扫掠 | 多维切片 | 商业实景案例 | 终审看板")

# ================= 侧边栏：全参数输入 =================
with st.sidebar:
    st.header("1. 目标应用工况")
    domain = st.selectbox(
        "下游整机系统",
        ["工业协作机械臂 (关注刚度/挠度)", "长航时工业无人机 (关注极致减重)", "深海探测器结构件 (关注耐压/吸水)", "医疗可穿戴外骨骼 (关注疲劳/寿命)"]
    )

    st.header("2. 核心物性参数")
    density = st.number_input("密度 (g/cm³)", value=1.30, format="%.2f")
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    
    st.header("3. 宏观结构形态")
    material_form = st.selectbox(
        "材料加工形态",
        ["连续长丝/纤维 (单向受力/复材增强相)", "多轴向织物预浸料 (平面受力)", "各向同性体块/树脂/金属代用品 (体块受力)"]
    )

    st.header("4. 高阶参数 (缺失将触发图表扫掠)")
    with st.expander("展开填补高阶盲区"):
        elongation = st.number_input("断裂伸长率 (%)", value=0.0)
        water_abs = st.number_input("饱和吸水率 (%)", value=0.0)

    st.header("5. 算力引擎")
    api_key = st.text_input("DeepSeek API Key", type="password", value=st.secrets.get("DEEPSEEK_API_KEY", ""))

# ================= 主界面：评估逻辑 =================

if st.button("🚀 启动大满贯全景数据引擎 (耗时约15-30秒)", type="primary"):
    if not api_key:
        st.warning("⚠️ 需配置 API Key。")
        st.stop()

    # 榨干大模型输出极限的终极 JSON 指令
    system_prompt = f"""
    你是一个终极工业材料计算与数据推演引擎。
    输入：领域={domain}, 形态={material_form}, 密度={density}, 强度={strength}, 模量={modulus}, 伸长率={elongation}%, 吸水率={water_abs}%。
    
    【核心要求】必须严格输出以下极其庞大的 JSON 结构，绝不包含任何 Markdown 标记。确保所有 JSON 闭合合法！
    
    {{
      "radar": {{"绝对强度": 100, "比刚度": 60, "轻量化": 95, "韧性容错": 45, "抗疲劳": 50, "加工良率": 60}},
      "base_metrics": [
        {{"metric": "绝对强度 (MPa)", "Al7075": 570, "T1000": 3000, "NewMat": {strength}}},
        {{"metric": "绝对模量 (GPa)", "Al7075": 71, "T1000": 160, "NewMat": {modulus}}},
        {{"metric": "比强度 (kN·m/kg)", "Al7075": 203, "T1000": 1875, "NewMat": {strength/density}}},
        {{"metric": "比模量 (GPa·cm³/g)", "Al7075": 25.3, "T1000": 100, "NewMat": {modulus/density}}}
      ],
      "math_sim": {{
        "part_name": "典型主承力部件 (机臂/梁)",
        "design_goal": "等刚度代换 (控制挠度不变)",
        "math_latex": "根据公式 $$ \\delta = \\frac{{F L^3}}{{3 E I}} $$，令新旧挠度 $\\delta$ 相等，则 $E_1 I_1 = E_2 I_2$。因新模量 $E_2={modulus}$GPa，原铝合金 $E_1=71$GPa，则截面惯性矩需调整为 $I_2 = (71/{modulus}) I_1$。以此推导管壁厚度和最终减重比。",
        "table": [
          {{"param": "设计模量 E (GPa)", "base": 71, "new": {modulus}}},
          {{"param": "等效截面惯性矩 I", "base": "1.0 基准", "new": "0.71 (可削减壁厚)"}},
          {{"param": "预估结构总重 (kg)", "base": 4.25, "new": 1.35}}
        ],
        "chart_vals": {{"base_wt": 4.25, "new_wt": 1.35}}
      }},
      "parameter_sweep": {{
        "elongation": {{
          "chart_title": "理论断裂韧性随伸长率波动预估",
          "chart_data": [{{"x": "脆性 <2%", "y": 20}}, {{"x": "高韧 5-8%", "y": 120}}, {{"x": "塑化 >15%", "y": 40}}],
          "scenarios": [
            {{"range": "< 2%", "desc": "极脆，冲击载荷下易碎裂，需表面包覆吸能层。"}},
            {{"range": "5% - 8%", "desc": "结合高强度，断裂功（韧性）逆天，可作防爆骨架。"}}]
        }},
        "environment": {{
          "chart_title": "模量随湿热环境衰减曲线预估 (Tg盲区)",
          "chart_data": [{{"x": "常温干燥", "y": 100}}, {{"x": "80°C / 湿度50%", "y": 70}}, {{"x": "120°C / 湿度90%", "y": 20}}],
          "scenarios": [
            {{"range": "高湿热区 (Tg < 80°C)", "desc": "若非晶区玻璃化温度偏低，模量将断崖下跌，需隔热/隔水封装。"}},
            {{"range": "溶剂溶胀风险", "desc": "高分子结构若遇极性溶剂膨胀率超5%，必须禁用裸露态。"}}]
        }}
      }},
      "six_dimensions": [
        {{"dim": "1. 静态拉压与剪切极限", "details": ["数据论证1", "数据论证2"]}},
        {{"dim": "2. 动态疲劳与蠕变推演", "details": ["数据论证1", "数据论证2"]}},
        {{"dim": "3. 刚度形变与几何补偿", "details": ["数据论证1", "数据论证2"]}},
        {{"dim": "4. 界面粘接与加工成型", "details": ["数据论证1", "数据论证2"]}},
        {{"dim": "5. 环境老化与理化耐受", "details": ["数据论证1", "数据论证2"]}},
        {{"dim": "6. 全生命周期经济与良率", "details": ["数据论证1", "数据论证2"]}}
      ],
      "system_impact": [
        {{"indicator": "有效载荷提升 (Payload)", "val": "+18%", "justification": "因大臂自重减少，电机无效扭矩输出降低。"}},
        {{"indicator": "能耗/续航优化 (Power)", "val": "-22%", "justification": "动态加减速惯量大幅下降，峰值电流衰减。"}},
        {{"indicator": "高速抑震响应 (Settling)", "val": "-12%", "justification": "高强低惯量结合一定阻尼，到位后残余震荡缩短。"}}
      ],
      "case_study": {{
        "target_part": "轻载高速运动连杆",
        "traditional_mat": "7075铝合金 / 碳纤T300",
        "new_design": "新材料复合纤维铺层",
        "benefit": "壁厚削减40%，单件减重55%，惯量极大降低，允许电机提速20%而不过载。"
      }},
      "verdict": {{
        "strengths": ["核心优势1(带数据)", "核心优势2"],
        "weaknesses": ["致命短板1(带数据)", "致命短板2"],
        "go_parts": ["推荐部件A", "推荐部件B", "推荐部件C"],
        "no_go_parts": ["禁用部件A", "禁用部件B"]
      }}
    }}
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    API_URL = API_URL.encode('ascii', 'ignore').decode('ascii').strip()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.15}

    with st.spinner("算力引擎启动：加载基础矩阵 -> 数学仿真 -> 区间扫掠 -> 系统折算..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            clean_json_str = response.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json_str)
            
            st.success("✅ 大满贯数据矩阵计算完成！")

            # ================= 1. 基础矩阵 (恢复了图表与数据表并存) =================
            st.subheader("I. 材料本征参数对标矩阵 (Base Material Mapping)")
            
            c_radar, c_bars = st.columns([1, 2.5])
            with c_radar:
                df_radar = pd.DataFrame(dict(r=list(data['radar'].values()), theta=list(data['radar'].keys())))
                fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True, title="多维潜力图谱")
                fig_radar.update_traces(fill='toself', line_color='#ff4b4b')
                fig_radar.update_layout(margin=dict(l=30, r=30, t=40, b=20), height=320)
                st.plotly_chart(fig_radar, use_container_width=True)

            with c_bars:
                bm = data['base_metrics']
                r1c1, r1c2 = st.columns(2)
                r2c1, r2c2 = st.columns(2)
                
                def plot_mini(md, container):
                    df_m = pd.DataFrame({"Material": ["Al7075", "T1000", "NewMat"], "Value": [md['Al7075'], md['T1000'], md['NewMat']]})
                    fig = px.bar(df_m, x="Material", y="Value", text_auto='.2s', color="Material",
                                 color_discrete_map={"Al7075": "#a6b8c7", "T1000": "#5a6e7f", "NewMat": "#ff4b4b"})
                    fig.update_layout(title=md['metric'], showlegend=False, height=160, margin=dict(l=10, r=10, t=30, b=10))
                    container.plotly_chart(fig, use_container_width=True)

                plot_mini(bm[0], r1c1)
                plot_mini(bm[1], r1c2)
                plot_mini(bm[2], r2c1)
                plot_mini(bm[3], r2c2)

            st.markdown("###### 📝 核心本征参数量化表")
            df_base = pd.DataFrame(bm)
            df_base.columns = ["指标大类", "航空铝合金 7075", "顶尖碳纤维 T1000", "当前输入新材料"]
            st.dataframe(df_base, use_container_width=True, hide_index=True)

            st.divider()

            # ================= 2. 数学仿真推演 =================
            st.subheader("II. 零部件级代换数学等效推演 (Component-Level Math Simulation)")
            sim = data['math_sim']
            st.markdown(f"**设定工况：** `{sim['part_name']}` | **优化目标：** `{sim['design_goal']}`")
            
            with st.container(border=True):
                st.markdown("##### 📐 力学等效代换公式推演")
                st.markdown(sim['math_latex'])
            
            sc1, sc2 = st.columns([1.5, 1])
            with sc1:
                st.markdown("##### 📊 成型件关键参数演变表")
                df_sim = pd.DataFrame(sim["table"])
                df_sim.columns = ["推演关键参数", "传统基准方案", "新材料代换方案"]
                st.dataframe(df_sim, use_container_width=True, hide_index=True)
            with sc2:
                df_wt = pd.DataFrame({"方案": ["传统方案", "新材料代换"], "总重(kg)": [sim['chart_vals']['base_wt'], sim['chart_vals']['new_wt']]})
                fig_wt = px.bar(df_wt, x="方案", y="总重(kg)", color="方案", text="总重(kg)", height=220,
                                color_discrete_map={"传统方案": "#7f7f7f", "新材料代换": "#2ca02c"}, title="等效结构最终减重对比")
                fig_wt.update_layout(showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_wt, use_container_width=True)

            st.divider()

            # ================= 3. 图表化缺失参数扫掠 =================
            st.subheader("III. 缺失参数敏感性图表扫掠 (Parameter Sweep Analysis)")
            st.caption("针对关键断裂韧性与湿热老化盲区，系统自动展开多区间图表化预测。")
            
            swp = data['parameter_sweep']
            swp_c1, swp_c2 = st.columns(2)
            
            with swp_c1:
                with st.container(border=True):
                    elo = swp['elongation']
                    fig_e = px.bar(pd.DataFrame(elo['chart_data']), x="x", y="y", title=elo['chart_title'], height=200, color_discrete_sequence=['#ff9f43'])
                    fig_e.update_layout(xaxis_title="伸长率区间预估", yaxis_title="理论相对韧性", margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(fig_e, use_container_width=True)
                    for sc in elo['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
            
            with swp_c2:
                with st.container(border=True):
                    env = swp['environment']
                    fig_en = px.line(pd.DataFrame(env['chart_data']), x="x", y="y", markers=True, title=env['chart_title'], height=200, color_discrete_sequence=['#00bad1'])
                    fig_en.update_layout(xaxis_title="湿热环境负荷", yaxis_title="模量保持率 (%)", margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(fig_en, use_container_width=True)
                    for sc in env['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")

            st.divider()

            # ================= 4. 六大维度切片与整机效能 =================
            st.subheader("IV. 全景维度切片与整机系统级效应 (System-Level Impacts)")
            
            # 整机效能卡片并排
            sys = data['system_impact']
            sys_cols = st.columns(len(sys))
            for i, s in enumerate(sys):
                with sys_cols[i]:
                    st.metric(label=s['indicator'], value=s['val'])
                    st.caption(s['justification'])
            
            st.markdown("##### 🔬 6大硬核工程维度剖析")
            dims = data['six_dimensions']
            tabs = st.tabs([d['dim'] for d in dims])
            for i, tab in enumerate(tabs):
                with tab:
                    for d in dims[i]['details']: st.markdown(f"- {d}")

            st.divider()

            # ================= 5. 实景案例与终审看板 =================
            st.subheader("V. 工程落地案例与首席终审看板 (Final Verdict)")
            
            bot_c1, bot_c2 = st.columns([1, 1])
            
            with bot_c1:
                st.markdown("#### 🏭 虚拟商业案例对标")
                case = data['case_study']
                # 工业实景占位图
                img_url = f"https://placehold.co/600x300/1e293b/e2e8f0?text={urllib.parse.quote('Engineering Case Study')}"
                st.image(img_url, use_container_width=True)
                st.info(f"**🎯 目标部件:** {case['target_part']}\n\n**🆚 传统基准:** {case['traditional_mat']}\n\n**🟥 新代换设计:** {case['new_design']}\n\n**📈 量化总收益:** {case['benefit']}")
            
            with bot_c2:
                st.markdown("#### ⚖️ 工程红绿灯判定决议")
                verdict = data['verdict']
                with st.container(border=True):
                    st.success("##### 🌟 核心绝对优势")
                    for s in verdict['strengths']: st.markdown(f"- {s}")
                    st.error("##### ⚠️ 致命物理短板")
                    for w in verdict['weaknesses']: st.markdown(f"- {w}")
                
                v_in1, v_in2 = st.columns(2)
                with v_in1:
                    st.info("##### 🟢 极度推荐部件 (Go)")
                    for p in verdict['go_parts']: st.markdown(f"- {p}")
                with v_in2:
                    st.warning("##### 🔴 严禁使用部件 (No-Go)")
                    for p in verdict['no_go_parts']: st.markdown(f"- {p}")

        except Exception as e:
            st.error(f"引擎负荷过大，JSON 解析中断。请重试。错误追踪: {str(e)}")
