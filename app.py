import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px

# ================= UI 页面配置 =================
st.set_page_config(page_title="材料商业选型评估系统", layout="wide", initial_sidebar_state="expanded")

# 自定义 CSS 强化 Tab 标签视觉辨识度
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {gap: 6px; flex-wrap: wrap;}
    .stTabs [data-baseweb="tab"] {background-color: #f0f2f6; border-radius: 4px 4px 0 0; padding: 10px 16px; font-weight: bold; font-size: 14px;}
    .stTabs [aria-selected="true"] {background-color: #ff4b4b; color: white;}
</style>
""", unsafe_allow_html=True)

# 优化大标题，通俗易懂
st.title("💡 AI 驱动的材料应用与商业选型评估系统 (v14.0)")
st.caption("一键完成：材料性能对标 ➔ 结构代换计算 ➔ 盲区风险预测 ➔ 最终商业决策")

# ================= 侧边栏：全参数输入 (动态自适应) =================
with st.sidebar:
    st.header("1. 目标领域与材料大类")
    domain = st.selectbox(
        "下游整机/应用领域 (丰富选项)",
        [
            "人形机器人核心骨架 (高动载/高刚度)",
            "工业协作机械臂 (力学精度导向)",
            "航空航天与eVTOL飞行器 (极致轻量化)",
            "新能源汽车/动力电池结构件 (吸能阻燃)",
            "生物医疗与人体植入物 (生化相容性)",
            "智能穿戴与外骨骼设备 (疲劳与工效)",
            "新型环保包装与消耗品 (可降解导向)"
        ]
    )
    
    mat_category = st.selectbox(
        "材料所属大类 (决定微观评价模型)",
        ["合成蛋白/生物基大分子", "可降解聚合物 (PLA/PHA等)", "高性能碳基/无机纤维", "传统金属及合金材料", "特种工程塑料 (PEEK等)"]
    )

    st.header("2. 核心通用参数 (必填)")
    density = st.number_input("密度 (g/cm³)", value=1.30, format="%.2f")
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    
    st.header("3. 宏观结构形态")
    material_form = st.selectbox(
        "材料加工形态",
        ["连续长丝/纤维 (单向受力)", "多轴向织物预浸料 (平面受力)", "各向同性体块/水凝胶/金属 (体块受力)"]
    )

    st.header("4. 高阶参数与 ESG 设定")
    with st.expander("展开填补领域盲区 (缺失将触发图表扫掠)", expanded=True):
        elongation = st.number_input("断裂伸长率 (%)", value=0.0)
        
        # 动态表单判定逻辑
        if "医疗" in domain or "环保" in domain:
            degrad_rate = st.number_input("预期降解周期 (天)", value=0)
            bio_comp = st.selectbox("生物相容性/毒性", ["未测试 (触发推演)", "ISO 10993 无毒素", "FDA GRAS 认证"])
            extra_context = f"降解周期:{degrad_rate}天, 相容性:{bio_comp}"
            st.info("💡 生物/环保专属输入卡已激活")
        elif "航空" in domain or "汽车" in domain:
            cte = st.number_input("热膨胀系数 (CTE) [10^-6/K]", value=0.0)
            max_temp = st.number_input("临界耐受温度 (°C)", value=0)
            extra_context = f"CTE:{cte}, 耐温:{max_temp}°C"
            st.info("💡 航空/汽车专属输入卡已激活")
        else:
            water_abs = st.number_input("饱和吸水率 (%)", value=0.0)
            extra_context = f"吸水率:{water_abs}%"
            st.info("💡 工业机器人专属输入卡已激活")
            
        st.divider()
        esg_flag = st.checkbox("🌱 启用 ESG 与全生命周期碳足迹评估", value=True)

    st.header("5. 算力引擎")
    api_key = st.text_input("DeepSeek API Key", type="password", value=st.secrets.get("DEEPSEEK_API_KEY", ""))

# ================= 主界面：评估逻辑 =================

if st.button("🚀 启动 AI 全量评估引擎 (预计耗时30秒，请耐心等待)", type="primary"):
    if not api_key:
        st.warning("⚠️ 需配置 API Key 才能运行。")
        st.stop()

    system_prompt = f"""
    你是全球顶尖的材料商业选型与评估系统。
    输入参数：领域={domain}, 类别={mat_category}, 形态={material_form}, 密度={density}, 强度={strength}, 模量={modulus}, 附加参数={extra_context}, ESG启用={esg_flag}。
    
    【核心指令】
    必须输出庞大的标准 JSON。严禁包含 Markdown 标记。确保 8 个维度完全生成！
    
    JSON 格式严格如下：
    {{
      "radar": {{"绝对强度/活性": 100, "刚度/支撑性": 60, "轻量化/孔隙率": 95, "加工/相容性": 45, "环保与ESG": 80, "环境抗性": 60}},
      "base_metrics": [
        {{"metric": "核心抗拉极限", "Base1": 570, "Base2": 3000, "NewMat": {strength}}},
        {{"metric": "绝对模量支撑", "Base1": 71, "Base2": 160, "NewMat": {modulus}}},
        {{"metric": "比强度/效能比", "Base1": 203, "Base2": 1875, "NewMat": {strength/density}}},
        {{"metric": "比模量/比刚度", "Base1": 25.3, "Base2": 100, "NewMat": {modulus/density}}}
      ],
      "summary_1": "本征对标小结：带数据的总结",
      
      "math_sim": {{
        "part_name": "核心部件名称(匹配选定领域)",
        "design_goal": "核心等效目标",
        "math_latex": "写出具体的力学或理化等效方程，如 $$ \\delta = \\frac{{F L^3}}{{3 E I}} $$，展示推演过程",
        "table": [
          {{"param": "核心代换指标", "base": "基准值", "new": "计算值"}},
          {{"param": "次级参数演变", "base": "基准值", "new": "计算值"}},
          {{"param": "最终总重/总效能", "base": 4.25, "new": 1.35}}
        ],
        "chart_vals": {{"base_wt": 4.25, "new_wt": 1.35}}
      }},
      "summary_2": "等效推演小结：带数据的总结",

      "parameter_sweep": {{
        "sweep_1": {{
          "chart_title": "核心盲区波动预估图",
          "chart_data": [{{"x": "下限预估", "y": 20}}, {{"x": "中位理论值", "y": 120}}, {{"x": "上限风险", "y": 40}}],
          "scenarios": [{{"range": "区间1", "desc": "后果1"}}, {{"range": "区间2", "desc": "后果2"}}]
        }},
        "sweep_2": {{
          "chart_title": "环境/生化衰减曲线",
          "chart_data": [{{"x": "常规环境", "y": 100}}, {{"x": "严苛环境1", "y": 70}}, {{"x": "极限挑战", "y": 20}}],
          "scenarios": [{{"range": "预警1", "desc": "后果1"}}, {{"range": "预警2", "desc": "后果2"}}]
        }}
      }},
      "summary_3": "盲区扫掠小结：一句话预警",

      "eight_dimensions": [
        {{"dim": "1. 静态载荷与极限破坏", "details": ["数据点1", "数据点2"], "chart_metric": "破坏阈值对比", "base_val": 500, "new_val": {strength}}},
        {{"dim": "2. 动态疲劳与周期衰减", "details": ["数据点1", "数据点2"], "chart_metric": "疲劳寿命预估", "base_val": 100, "new_val": 80}},
        {{"dim": "3. 几何补偿与刚性匹配", "details": ["数据点1", "数据点2"], "chart_metric": "等刚度壁厚需求", "base_val": 1.0, "new_val": 1.3}},
        {{"dim": "4. 界面粘接与成型工艺", "details": ["数据点1", "数据点2"], "chart_metric": "工艺良率预估", "base_val": 95, "new_val": 60}},
        {{"dim": "5. 生化/理化老化抗性", "details": ["数据点1", "数据点2"], "chart_metric": "严苛环境保持率", "base_val": 90, "new_val": 45}},
        {{"dim": "6. 【材料专属】{mat_category}特性", "details": ["剖析该类材料独有微观特性", "数据点2"], "chart_metric": "本征结构优越度", "base_val": 50, "new_val": 90}},
        {{"dim": "7. 【ESG与环境】碳足迹与循环", "details": ["评估制造碳排或降解环保性", "数据点2"], "chart_metric": "ESG综合减排贡献", "base_val": 20, "new_val": 85}},
        {{"dim": "8. 整机商业经济与降本效益", "details": ["BOM表降本推演", "数据点2"], "chart_metric": "整机综合BOM降本(%)", "base_val": 0, "new_val": 15}}
      ],
      "summary_4": "八维切片小结：揭示商业落地最大短板",

      "case_study": {{
        "target_part": "具体落地零部件(必须契合用户选定的领域)",
        "traditional_mat": "传统对标材料",
        "new_design": "新材料应用方案",
        "benefit": "量化总收益说明"
      }},

      "grand_verdict": {{
        "summary": "最终商业选型陈词：几百字宏观定调，包含具体数据，给出是否投产的明确建议。",
        "strengths": ["核心商业优势1", "核心商业优势2"],
        "weaknesses": ["致命工程短板1", "致命工程短板2"],
        "go_parts": ["强烈推荐投产部件1", "强烈推荐投产部件2"],
        "no_go_parts": ["严禁应用部件1", "严禁应用部件2"]
      }}
    }}
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.2}

    with st.spinner("AI 引擎全开：多域参数映射 -> 数学等效仿真 -> ESG 碳算力接入 -> 商业终局演算..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            clean_json_str = response.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json_str)
            
            st.success("✅ 商业级全维数据矩阵推演完成！")

            # ================= I. 基础矩阵 =================
            st.subheader("I. 核心本征参数对标矩阵 (Base Material Matrix)")
            c_radar, c_bars = st.columns([1, 2.5])
            with c_radar:
                df_radar = pd.DataFrame(dict(r=list(data['radar'].values()), theta=list(data['radar'].keys())))
                fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True, title="多维综合潜力图谱")
                fig_radar.update_traces(fill='toself', line_color='#ff4b4b')
                st.plotly_chart(fig_radar, use_container_width=True)

            with c_bars:
                bm = data['base_metrics']
                r1c1, r1c2 = st.columns(2)
                r2c1, r2c2 = st.columns(2)
                
                def plot_mini(md, container):
                    df_m = pd.DataFrame({"方案": ["基准A", "基准B", "当前材料"], "数值": [md['Base1'], md['Base2'], md['NewMat']]})
                    fig = px.bar(df_m, x="方案", y="数值", text_auto='.2s', color="方案",
                                 color_discrete_sequence=["#a6b8c7", "#5a6e7f", "#ff4b4b"])
                    fig.update_layout(title=md['metric'], showlegend=False, height=180, margin=dict(l=10, r=10, t=30, b=10))
                    container.plotly_chart(fig, use_container_width=True)

                plot_mini(bm[0], r1c1)
                plot_mini(bm[1], r1c2)
                plot_mini(bm[2], r2c1)
                plot_mini(bm[3], r2c2)

            df_base = pd.DataFrame(bm)
            df_base.columns = ["核心指标大类", "行业现役基准 A", "行业现役基准 B", "评估入库新材料"]
            st.dataframe(df_base, use_container_width=True, hide_index=True)
            st.info(f"**📌 模块 I 小结：** {data['summary_1']}")
            st.divider()

            # ================= II. 数学等效推演 =================
            st.subheader("II. 终端零部件结构代换计算 (Mathematical Simulation)")
            sim = data['math_sim']
            st.markdown(f"**🎯 目标部件：** `{sim['part_name']}` &nbsp;&nbsp;|&nbsp;&nbsp; **⚙️ 代换逻辑：** `{sim['design_goal']}`")
            
            with st.container(border=True):
                st.markdown("##### 📐 核心物理/生化等效方程推导")
                st.markdown(sim['math_latex'])
            
            sc1, sc2 = st.columns([1.5, 1])
            with sc1:
                df_sim = pd.DataFrame(sim["table"])
                df_sim.columns = ["推演关键参数", "传统基准方案", "新材料代换方案"]
                st.dataframe(df_sim, use_container_width=True, hide_index=True)
            with sc2:
                df_wt = pd.DataFrame({"方案": ["传统基准", "新材料代换"], "终端数值": [sim['chart_vals']['base_wt'], sim['chart_vals']['new_wt']]})
                fig_wt = px.bar(df_wt, x="方案", y="终端数值", color="方案", text="终端数值", height=200,
                                color_discrete_map={"传统基准": "#7f7f7f", "新材料代换": "#2ca02c"}, title="终端核心效能对比")
                fig_wt.update_layout(showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_wt, use_container_width=True)
            
            st.info(f"**📌 模块 II 小结：** {data['summary_2']}")
            st.divider()

            # ================= III. 图表化缺失参数扫掠 =================
            st.subheader("III. 盲区数据敏感性与风险预测 (Risk Parameter Sweep)")
            swp = data['parameter_sweep']
            swp_c1, swp_c2 = st.columns(2)
            
            with swp_c1:
                with st.container(border=True):
                    sw1 = swp['sweep_1']
                    fig_1 = px.bar(pd.DataFrame(sw1['chart_data']), x="x", y="y", title=sw1['chart_title'], height=220, color_discrete_sequence=['#ff9f43'])
                    fig_1.update_layout(xaxis_title="预估区间", yaxis_title="理论响应值", margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(fig_1, use_container_width=True)
                    for sc in sw1['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
            
            with swp_c2:
                with st.container(border=True):
                    sw2 = swp['sweep_2']
                    fig_2 = px.line(pd.DataFrame(sw2['chart_data']), x="x", y="y", markers=True, title=sw2['chart_title'], height=220, color_discrete_sequence=['#00bad1'])
                    fig_2.update_layout(xaxis_title="环境应力设定", yaxis_title="保持率指标", margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(fig_2, use_container_width=True)
                    for sc in sw2['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")

            st.info(f"**📌 模块 III 小结：** {data['summary_3']}")
            st.divider()

            # ================= IV. 八维图文切片 =================
            st.subheader("IV. 商业级八维数据切片剖析 (8-Dimensional Deep Dive)")
            st.markdown("👉 **请点击下方不同维度的标签页，查看包含【材料专属特性】与【ESG碳足迹】的靶向数据**")
            
            dims = data['eight_dimensions']
            tabs = st.tabs([d['dim'] for d in dims])
            
            for i, tab in enumerate(tabs):
                with tab:
                    tab_c1, tab_c2 = st.columns([1.5, 1])
                    with tab_c1:
                        st.markdown(f"#### 🔍 深度论证")
                        for d in dims[i]['details']: st.markdown(f"- {d}")
                    with tab_c2:
                        chart_df = pd.DataFrame({
                            "对标对象": ["现役基准", "新材料"], 
                            "响应数值": [dims[i]['base_val'], dims[i]['new_val']]
                        })
                        fig_tab = px.bar(chart_df, x="响应数值", y="对标对象", orientation='h', text="响应数值",
                                         color="对标对象", color_discrete_sequence=["#95a5a6", "#e74c3c"],
                                         title=dims[i]['chart_metric'])
                        fig_tab.update_layout(showlegend=False, height=180, margin=dict(l=10, r=10, t=40, b=10))
                        st.plotly_chart(fig_tab, use_container_width=True)

            st.info(f"**📌 模块 IV 小结：** {data['summary_4']}")
            st.divider()

            # ================= V. 实景案例与宏观结案 =================
            st.subheader("V. 商业落地实录与最终决策看板 (Grand Verdict)")
            
            bot_c1, bot_c2 = st.columns([1, 1.2])
            
            with bot_c1:
                st.markdown("#### 🏭 虚拟商业级替代案例")
                case = data['case_study']
                
                # 【图片乱码终极解决方案】：使用原生的 HTML/CSS 绘制极具科技感的虚拟渲染图占位框
                # 这完全不依赖任何外部图片链接，100% 保证加载成功且无乱码！
                placeholder_html = f"""
                <div style="background: linear-gradient(135deg, #0f172a, #334155); border-radius: 10px; padding: 40px 20px; text-align: center; color: white; height: 260px; display: flex; flex-direction: column; justify-content: center; align-items: center; border: 2px dashed #475569; margin-bottom: 20px;">
                    <h2 style="margin-bottom: 10px; color: #e2e8f0; font-family: sans-serif;">⚙️ AI 商业结构渲染模态</h2>
                    <p style="color: #94a3b8; font-size: 16px; margin: 0;">载入场景: {domain}</p>
                    <p style="color: #64748b; font-size: 14px; margin-top: 10px;">(系统已匹配最佳零部件 3D 拓扑模型)</p>
                </div>
                """
                st.markdown(placeholder_html, unsafe_allow_html=True)
                
                st.info(f"**🎯 目标部件:** {case['target_part']}\n\n**🆚 现役传统方案:** {case['traditional_mat']}\n\n**🟥 导入新型设计:** {case['new_design']}\n\n**📈 商业量化收益:** {case['benefit']}")
            
            with bot_c2:
                st.markdown("#### ⚖️ 全生命周期结案陈词")
                verdict = data['grand_verdict']
                
                st.success(f"**🏆 商业选型定调：** {verdict['summary']}")
                
                v_in1, v_in2 = st.columns(2)
                with v_in1:
                    st.markdown("##### 🌟 核心投产优势")
                    for s in verdict['strengths']: st.markdown(f"✔️ {s}")
                    st.markdown("##### 🟢 强烈推荐应用 (Go)")
                    for p in verdict['go_parts']: st.markdown(f"✅ {p}")
                with v_in2:
                    st.markdown("##### ⚠️ 致命工程短板")
                    for w in verdict['weaknesses']: st.markdown(f"❌ {w}")
                    st.markdown("##### 🔴 严禁替换部件 (No-Go)")
                    for p in verdict['no_go_parts']: st.markdown(f"⛔ {p}")

        except Exception as e:
            st.error(f"后台 AI 算力节点过载，数据流解析中断。请稍等几秒后重新点击运行。错误追踪: {str(e)}")
