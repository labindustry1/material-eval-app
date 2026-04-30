import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px

# ================= UI 页面基础配置 =================
st.set_page_config(page_title="AI 商业选型系统", layout="wide", initial_sidebar_state="expanded")

# ================= 🔐 第一关：商业邀请码验证系统 =================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.info("🛡️ 该商业评估系统已加密，仅限受邀用户访问。")
        pwd = st.text_input("请输入专属邀请码：", type="password")
        if st.button("解锁系统", type="primary", use_container_width=True):
            if pwd == "VIP2026":  # 邀请码
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("邀请码错误或已过期！")
    st.stop()
# ===================================================================

# ================= 导入本地挂载引擎 (智能容错) =================
try:
    from rag_engine import retrieve_knowledge
    from db_connector import init_db, get_material_data
    init_db()
    LOCAL_TOOLS_READY = True
except ImportError:
    LOCAL_TOOLS_READY = False
    def retrieve_knowledge(query, k=3): return "本地知识库尚未部署。"
    def get_material_data(mat_name): return None

# ================= 实时联网搜索引擎 (Tavily) =================
def search_tavily(query, api_key):
    if not api_key: return "未配置 Tavily API Key"
    url = "https://api.tavily.com/search"
    payload = {"api_key": api_key, "query": query, "search_depth": "advanced", "include_answer": True, "max_results": 3}
    try:
        response = requests.post(url, json=payload, timeout=15)
        data = response.json()
        return f"【全网提炼】: {data.get('answer', '无')}\n【来源】: {str(data.get('results', []))}"
    except Exception as e: return f"检索失败: {str(e)}"

# ================= 🌟 核心：全域知识图谱配置字典 🌟 =================
DOMAIN_CONFIG = {
    "生物医疗与人体植入物 (生化导向)": {
        "ui_inputs": [
            {"label": "预期降解周期 (天)", "type": "slider", "min": 0, "max": 730, "default": 180, "key": "degradation_time"},
            {"label": "生物相容性认证", "type": "selectbox", "options": ["ISO 10993 (植入级)", "体外接触级", "未测试"], "key": "biocompatibility"},
            {"label": "吸水溶胀率 (%)", "type": "number", "default": 2.0, "key": "swelling_rate"}
        ],
        "search_suffix": "biocompatibility ISO 10993 in vivo degradation rate medical implants scholarly research",
        "strict_constraint": "【绝对禁令】：严禁在报告中提及军工、航空、装甲、防弹等无关工业词汇！必须严格聚焦于组织工程、骨传导、降解代谢产物毒性、FDA准入标准。对标材料必须是天然骨骼、PEEK或医用钛合金。"
    },
    "人形机器人核心骨架 (高动载/刚度)": {
        "ui_inputs": [
            {"label": "结构阻尼比 (ζ)", "type": "slider", "min": 0.01, "max": 0.50, "default": 0.05, "key": "damping_ratio"},
            {"label": "抗冲击韧性 (J/cm²)", "type": "number", "default": 50, "key": "impact_toughness"}
        ],
        "search_suffix": "dynamic mechanics vibration damping lightweight humanoid robot frame scholarly research",
        "strict_constraint": "【绝对禁令】：严禁提及医疗、防弹标准！必须聚焦于高频伺服电机启停带来的动态疲劳、惯量拖累与末端抖动抑制。对标材料必须是 7075 航空铝或碳纤维复材。"
    },
    "军工：单兵装甲与防护装备 (防弹/吸能)": {
        "ui_inputs": [
            {"label": "V50 防弹极限估值 (m/s)", "type": "number", "default": 650, "key": "v50_limit"},
            {"label": "抗冲击吸能率 (%)", "type": "slider", "min": 10, "max": 99, "default": 75, "key": "energy_absorption"}
        ],
        "search_suffix": "ballistic impact resistance body armor energy absorption MIL-STD scholarly research",
        "strict_constraint": "【绝对禁令】：严禁提及医疗植入、降解、环保等词汇！必须严格聚焦于应力波传导、防弹极限、抗弹击破片性能。参考 MIL-STD 等军用标准，对标材料必须是 Kevlar (芳纶) 或 UHMWPE。"
    },
    "航空航天与eVTOL飞行器 (极致轻量化)": {
        "ui_inputs": [
            {"label": "最高服役温度 (℃)", "type": "number", "default": 150, "key": "max_temp"},
            {"label": "阻燃等级", "type": "selectbox", "options": ["UL94-V0 (最高)", "UL94-V1", "不要求"], "key": "flame_retardant"},
            {"label": "热膨胀系数 (10^-6/K)", "type": "number", "default": 5.0, "key": "cte"}
        ],
        "search_suffix": "aerospace structural materials thermal stability FAA regulations scholarly research",
        "strict_constraint": "【绝对禁令】：严禁提及医疗或普通民用标准！重点分析高低温循环交变应力、抗微陨石冲击及适航认证(FAA/EASA)。"
    },
    "新能源汽车与动力电池包 (吸能/阻燃)": {
        "ui_inputs": [
            {"label": "阻燃与热失控防护", "type": "selectbox", "options": ["UL94-V0 (电池包级)", "内饰级阻燃", "无要求"], "key": "ev_flame"},
            {"label": "碰撞吸能比 (%)", "type": "slider", "min": 10, "max": 100, "default": 60, "key": "crash_absorption"}
        ],
        "search_suffix": "EV battery enclosure crashworthiness flame retardant lightweight vehicle structure scholarly research",
        "strict_constraint": "【绝对禁令】：严禁提及医疗或航天！必须聚焦汽车轻量化、电池包防刺穿、热失控隔热阻燃以及 NCAP 碰撞标准。对标高强钢或铝合金压铸件。"
    },
    "工业协作机械臂 (精度与疲劳导向)": {
        "ui_inputs": [
            {"label": "设计疲劳寿命 (10^7次)", "type": "number", "default": 100, "key": "fatigue_cycles"},
            {"label": "刚度形变容忍度 (mm)", "type": "slider", "min": 0.01, "max": 2.00, "default": 0.10, "key": "deformation_tolerance"}
        ],
        "search_suffix": "industrial collaborative robot arm lightweight stiffness fatigue resistance scholarly research",
        "strict_constraint": "【绝对禁令】：严禁偏向防弹或医疗！重点在于绝对的高刚度（防止机械臂末端下垂误差）和24小时连续运作的高周疲劳极限。对标铸铁或挤压铝材。"
    },
    "智能穿戴与柔性外骨骼 (工效与贴合)": {
        "ui_inputs": [
            {"label": "柔性弯曲疲劳 (万次)", "type": "number", "default": 50, "key": "flex_fatigue"},
            {"label": "表面亲肤透气性", "type": "selectbox", "options": ["高透气排汗", "防风防水", "致密不透气"], "key": "breathability"}
        ],
        "search_suffix": "wearable flexible exoskeleton ergonomic material durability scholarly research",
        "strict_constraint": "【绝对禁令】：不能用刚性骨架的思维评估！必须聚焦于人机交互的舒适度、柔性储能、耐磨性和生理工效学。评估舒适性和长期服役形变。"
    },
    "高性能纺织与极限户外装备 (耐候/舒适)": {
        "ui_inputs": [
            {"label": "公定回潮率 (%)", "type": "number", "default": 4.5, "key": "moisture_regain"},
            {"label": "抗紫外线衰减等级", "type": "selectbox", "options": ["极高 (高海拔户外)", "中等", "无需防护"], "key": "uv_resistance"},
            {"label": "耐水洗与磨损次数", "type": "number", "default": 200, "key": "wash_cycles"}
        ],
        "search_suffix": "high performance textile fiber moisture wicking abrasion resistance outdoor gear scholarly research",
        "strict_constraint": "【绝对禁令】：不要用硬质工业材料的思维！必须围绕服装纺织标准（如AATCC），分析其在户外日晒、雨淋、拉扯下的性能表现。对标锦纶或超高分子量聚乙烯纤维。"
    }
}

st.title("🚀 AI 材料商业评估与选型系统 (v19.5 全域旗舰版)")
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {gap: 6px; flex-wrap: wrap;}
    .stTabs [data-baseweb="tab"] {background-color: #f0f2f6; border-radius: 4px 4px 0 0; padding: 10px 16px; font-weight: bold;}
    .stTabs [aria-selected="true"] {background-color: #000000; color: white;}
</style>
""", unsafe_allow_html=True)

# ================= 侧边栏：动态 UI 渲染 =================
with st.sidebar:
    st.header("1. 目标领域")
    domain = st.selectbox("选择下游应用领域", list(DOMAIN_CONFIG.keys()))
    current_config = DOMAIN_CONFIG[domain]
    
    st.header("2. 通用基础参数")
    mat_category = st.selectbox("材料所属大类", ["合成蛋白/生物基大分子", "可降解聚合物", "高性能碳基纤维", "特种合金", "特种工程塑料"])
    density = st.number_input("密度 (g/cm³)", value=1.30)
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    material_form = st.selectbox("加工形态", ["连续长丝/纤维", "体块/水凝胶", "薄膜/涂层"])

    st.header("3. 领域专属关键参数")
    domain_specific_data = {}
    for item in current_config["ui_inputs"]:
        if item["type"] == "slider":
            domain_specific_data[item["key"]] = st.slider(item["label"], item["min"], item["max"], item["default"])
        elif item["type"] == "number":
            domain_specific_data[item["key"]] = st.number_input(item["label"], value=item["default"])
        elif item["type"] == "selectbox":
            domain_specific_data[item["key"]] = st.selectbox(item["label"], item["options"])
            
    st.divider()
    if st.button("退出登录", type="secondary"):
        st.session_state["authenticated"] = False
        st.rerun()

# ================= 后台静默读取 API Keys =================
api_key = st.secrets.get("DEEPSEEK_API_KEY", "") 
tavily_key = st.secrets.get("TAVILY_API_KEY", "") 

# ================= 主界面评估逻辑 =================
if st.button("🚀 启动专属领域全量评估", type="primary"):
    if not api_key: st.warning("系统后台未配置 DeepSeek API Key，请联系管理员。"); st.stop()

    with st.spinner(f"正在以【{domain.split(' ')[0]}】专家模式读取独家数据库与学术文献..."):
        
        # 1. 靶向搜索
        web_query = f"scholarly articles {mat_category} {strength}MPa {current_config['search_suffix']}"
        web_context = search_tavily(web_query, tavily_key)
        
        # 2. 本地检索
        local_query = f"{mat_category} {material_form} 加工工艺 {domain}"
        rag_context = retrieve_knowledge(local_query)

    # ---------------- 严谨的大模型指令 ----------------
    system_prompt = f"""
    你是全球顶尖的材料商业评估系统。当前评估语境：【{domain}】。
    
    【基础参数】: 密度={density}, 强度={strength}, 模量={modulus}。
    【领域专属参数】: {json.dumps(domain_specific_data, ensure_ascii=False)}。
    
    💥【领域安全隔离防线 (CRITICAL)】💥
    {current_config['strict_constraint']}
    若违反禁令跨界分析，视为严重错误！必须深度结合“领域专属参数”进行推演。
    
    【全网实时对标情报】: {web_context}
    【本地私有工艺经验】: {rag_context}
    
    【数据来源包装规范】(极度重要)
    1. 严禁在输出中提及“本地文件”、“txt”、“Tavily”或“API”。
    2. 本地提取的数据统一包装为：“独家内部数据库：相关测试规范或工艺手册”。
    3. 联网检索的内容统一包装为：“学术文献：[文章/新闻标题]” 或 “行业专著：相关理论”。
    4. reference_sources 数组中的内容必须严格遵守上述格式。
    
    必须输出庞大的标准 JSON。严禁 Markdown。
    JSON 格式严格如下：
    {{
      "radar": {{"核心强度": 100, "刚度支撑": 60, "轻量化收益": 95, "加工成型率": 45, "专属环境抗性": 80, "商业落地性": 90}},
      "base_metrics": [
        {{"metric": "核心抗拉极限", "Base1": 570, "Base2": 3000, "NewMat": {strength}}},
        {{"metric": "绝对模量支撑", "Base1": 71, "Base2": 160, "NewMat": {modulus}}},
        {{"metric": "比强度/效能比", "Base1": 203, "Base2": 1875, "NewMat": {strength/density}}},
        {{"metric": "比模量/比刚度", "Base1": 25.3, "Base2": 100, "NewMat": {modulus/density}}}
      ],
      "summary_1": "本征对标小结",
      
      "math_sim": {{
        "part_name": "核心部件名称(必须契合当前领域)",
        "design_goal": "核心等效目标",
        "math_latex": "写出具体的力学或理化等效方程",
        "table": [
          {{"param": "核心代换指标", "base": "基准值", "new": "计算值"}},
          {{"param": "次级参数演变", "base": "基准值", "new": "计算值"}},
          {{"param": "终端核心效能", "base": 4.25, "new": 1.35}}
        ],
        "chart_vals": {{"base_wt": 4.25, "new_wt": 1.35}}
      }},
      "summary_2": "等效推演小结",

      "parameter_sweep": {{
        "sweep_1": {{
          "chart_title": "领域专属盲区波动图",
          "chart_data": [{{"x": "下限预估", "y": 20}}, {{"x": "中位理论值", "y": 120}}, {{"x": "上限风险", "y": 40}}],
          "scenarios": [{{"range": "区间1", "desc": "后果1"}}, {{"range": "区间2", "desc": "后果2"}}]
        }},
        "sweep_2": {{
          "chart_title": "环境衰减曲线",
          "chart_data": [{{"x": "常规环境", "y": 100}}, {{"x": "严苛环境1", "y": 70}}, {{"x": "极限挑战", "y": 20}}],
          "scenarios": [{{"range": "预警1", "desc": "后果1"}}, {{"range": "预警2", "desc": "后果2"}}]
        }}
      }},
      "summary_3": "盲区扫掠小结",

      "eight_dimensions": [
        {{"dim": "1. 静态载荷与极限破坏", "details": ["分析1", "分析2"], "chart_metric": "破坏阈值对比", "base_val": 500, "new_val": {strength}}},
        {{"dim": "2. 动态疲劳与周期衰减", "details": ["分析1", "分析2"], "chart_metric": "疲劳寿命预估", "base_val": 100, "new_val": 80}},
        {{"dim": "3. 几何补偿与刚性匹配", "details": ["分析1", "分析2"], "chart_metric": "等刚度壁厚需求", "base_val": 1.0, "new_val": 1.3}},
        {{"dim": "4. 界面粘接与成型工艺", "details": ["分析1", "分析2"], "chart_metric": "工艺良率预估", "base_val": 95, "new_val": 60}},
        {{"dim": "5. 【重点】专属领域生化/理化抗性", "details": ["必须结合输入的专属参数深度剖析", "数据论证2"], "chart_metric": "专属环境保持率", "base_val": 90, "new_val": 45}},
        {{"dim": "6. 【专属】材料微观机理影响", "details": ["剖析微观特性", "数据点2"], "chart_metric": "结构优越度", "base_val": 50, "new_val": 90}},
        {{"dim": "7. 全生命周期碳足迹与ESG", "details": ["评估制造碳排或降解环保性", "数据点2"], "chart_metric": "ESG综合减排", "base_val": 20, "new_val": 85}},
        {{"dim": "8. 整机商业经济与降本效益", "details": ["BOM表降本推演", "数据点2"], "chart_metric": "综合降本(%)", "base_val": 0, "new_val": 15}}
      ],
      "summary_4": "八维切片小结",

      "case_study": {{
        "target_part": "具体落地零部件(严格匹配当前领域)",
        "traditional_mat": "传统现役方案",
        "new_design": "新材料应用方案",
        "benefit": "商业量化总收益说明"
      }},

      "grand_verdict": {{
        "summary": "最终选型陈词：给出明确投产建议。",
        "strengths": ["商业优势1", "商业优势2"],
        "weaknesses": ["致命短板1", "致命短板2"],
        "go_parts": ["推荐部件1", "推荐部件2"],
        "no_go_parts": ["严禁应用部件1", "严禁应用部件2"]
      }},
      
      "reference_sources": [
        "独家内部数据库: xxx规范",
        "学术文献: xxx研究报告"
      ]
    }}
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.15}

    with st.spinner("架构隔离防线已启动，正在生成专家级商业评测报告..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            clean_json_str = response.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json_str)
            
            st.success("✅ 专属领域深度推演完成！")

            # =============== UI 渲染层 ===============
            st.subheader(f"I. {domain.split(' ')[0]} - 核心本征参数对标")
            c_radar, c_bars = st.columns([1, 2.5])
            with c_radar:
                df_radar = pd.DataFrame(dict(r=list(data['radar'].values()), theta=list(data['radar'].keys())))
                fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True, title="多维潜力图谱")
                fig_radar.update_traces(fill='toself', line_color='#1f77b4')
                st.plotly_chart(fig_radar, use_container_width=True)

            with c_bars:
                bm = data['base_metrics']
                r1c1, r1c2 = st.columns(2)
                r2c1, r2c2 = st.columns(2)
                def plot_mini(md, container):
                    df_m = pd.DataFrame({"方案": ["基准A", "基准B", "入库新材"], "数值": [md['Base1'], md['Base2'], md['NewMat']]})
                    fig = px.bar(df_m, x="方案", y="数值", text_auto='.2s', color="方案", color_discrete_sequence=["#d3d3d3", "#a9a9a9", "#1f77b4"])
                    fig.update_layout(title=md['metric'], showlegend=False, height=180, margin=dict(l=10, r=10, t=30, b=10))
                    container.plotly_chart(fig, use_container_width=True)

                plot_mini(bm[0], r1c1); plot_mini(bm[1], r1c2)
                plot_mini(bm[2], r2c1); plot_mini(bm[3], r2c2)

            df_base = pd.DataFrame(bm)
            df_base.columns = ["核心指标大类", "现役基准 A", "现役基准 B", "入库新材料"]
            st.dataframe(df_base, use_container_width=True, hide_index=True)
            st.info(f"**📌 模块小结：** {data['summary_1']}")
            st.divider()

            st.subheader("II. 终端零部件结构代换计算")
            sim = data['math_sim']
            st.markdown(f"**🎯 目标部件：** `{sim['part_name']}` &nbsp;&nbsp;|&nbsp;&nbsp; **⚙️ 代换逻辑：** `{sim['design_goal']}`")
            with st.container(border=True):
                st.markdown("##### 📐 核心等效推导")
                st.markdown(sim['math_latex'])
            
            sc1, sc2 = st.columns([1.5, 1])
            with sc1:
                df_sim = pd.DataFrame(sim["table"])
                df_sim.columns = ["推演关键参数", "传统方案", "新材料代换"]
                st.dataframe(df_sim, use_container_width=True, hide_index=True)
            with sc2:
                df_wt = pd.DataFrame({"方案": ["传统基准", "新设计"], "效能": [sim['chart_vals']['base_wt'], sim['chart_vals']['new_wt']]})
                fig_wt = px.bar(df_wt, x="方案", y="效能", color="方案", text="效能", height=200, color_discrete_map={"传统基准": "#7f7f7f", "新设计": "#2ca02c"})
                fig_wt.update_layout(showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_wt, use_container_width=True)
            st.info(f"**📌 模块小结：** {data['summary_2']}")
            st.divider()

            st.subheader("III. 领域核心风险扫掠预演")
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
                    fig_2.update_layout(xaxis_title="环境应力", yaxis_title="保持率", margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(fig_2, use_container_width=True)
                    for sc in sw2['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
            st.info(f"**📌 模块小结：** {data['summary_3']}")
            st.divider()

            st.subheader("IV. 八维深度切片剖析")
            dims = data['eight_dimensions']
            tabs = st.tabs([d['dim'] for d in dims])
            for i, tab in enumerate(tabs):
                with tab:
                    tab_c1, tab_c2 = st.columns([1.5, 1])
                    with tab_c1:
                        st.markdown(f"#### 🔍 核心论证")
                        for d in dims[i]['details']: st.markdown(f"- {d}")
                    with tab_c2:
                        chart_df = pd.DataFrame({"对标对象": ["现役基准", "新材料"], "响应数值": [dims[i]['base_val'], dims[i]['new_val']]})
                        fig_tab = px.bar(chart_df, x="响应数值", y="对标对象", orientation='h', text="响应数值", color="对标对象", color_discrete_sequence=["#95a5a6", "#e74c3c"], title=dims[i]['chart_metric'])
                        fig_tab.update_layout(showlegend=False, height=180, margin=dict(l=10, r=10, t=40, b=10))
                        st.plotly_chart(fig_tab, use_container_width=True)
            st.info(f"**📌 模块小结：** {data['summary_4']}")
            st.divider()

            st.subheader("V. 领域专属结案与红绿灯决议")
            bot_c1, bot_c2 = st.columns([1, 1.2])
            with bot_c1:
                case = data['case_study']
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #0f172a, #334155); border-radius: 10px; padding: 40px 20px; text-align: center; color: white; height: 260px; display: flex; flex-direction: column; justify-content: center; align-items: center; border: 2px dashed #475569; margin-bottom: 20px;">
                    <h2 style="margin-bottom: 10px; color: #e2e8f0; font-family: sans-serif;">⚙️ AI 结构级仿真模态</h2>
                    <p style="color: #94a3b8; font-size: 16px; margin: 0;">应用场景载入: {domain.split(' ')[0]}</p>
                </div>
                """, unsafe_allow_html=True)
                st.info(f"**🎯 目标部件:** {case['target_part']}\n\n**🆚 现役方案:** {case['traditional_mat']}\n\n**🟥 新设计:** {case['new_design']}\n\n**📈 量化收益:** {case['benefit']}")
            with bot_c2:
                verdict = data['grand_verdict']
                st.success(f"**🏆 终局定调：** {verdict['summary']}")
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
                    
            st.divider()
            st.subheader("📚 数据溯源 (Data Origins)")
            for ref in data.get('reference_sources', []): st.markdown(f"- 🔗 **{ref}**")

        except Exception as e:
            st.error(f"后台节点过载或数据流中断。错误追踪: {str(e)}")
