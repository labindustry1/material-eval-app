import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math

# ================= UI 页面基础配置 =================
st.set_page_config(page_title="材料可行性评估系统", layout="wide", initial_sidebar_state="expanded")

# ================= 🔐 第一关：商业邀请码验证系统 =================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.info("🛡️ 该评估系统已加密，仅限受邀用户访问。")
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

# ================= 🌟 黑白 CAD 线框图生成引擎 🌟 =================
def draw_cad_blueprint(part_name):
    """纯数学生成的黑白工程线框网格"""
    x = [i*0.2 - 5 for i in range(50)]
    y = [i*0.2 - 5 for i in range(50)]
    z = [[math.sin(xi) * math.cos(yi) * 2 for xi in x] for yi in y]
    
    fig = go.Figure(data=[go.Surface(z=z, x=x, y=y, colorscale='Greys', showscale=False, opacity=0.9)])
    fig.update_traces(contours_z=dict(show=True, usecolormap=False, highlightcolor="black", project_z=True))
    fig.update_layout(
        title=dict(text=f"📐 工程结构拟合: {part_name}", font=dict(color="black")),
        scene=dict(
            xaxis=dict(showbackground=False, color="black", gridcolor="lightgrey", title="长度 (X)"),
            yaxis=dict(showbackground=False, color="black", gridcolor="lightgrey", title="宽度 (Y)"),
            zaxis=dict(showbackground=False, color="black", gridcolor="lightgrey", title="壁厚/形变 (Z)")
        ),
        paper_bgcolor='white', plot_bgcolor='white', margin=dict(l=0, r=0, t=40, b=0), height=320
    )
    return fig

# ================= 🌟 核心：全域知识图谱与零部件配置字典 🌟 =================
DOMAIN_CONFIG = {
    "生物医疗与人体植入物 (生化导向)": {
        "part_options": ["骨折内固定承力板", "高强度人工韧带", "可降解骨钉"],
        "ui_inputs": [
            {"label": "零件设计厚度/直径 (mm)", "type": "slider", "min": 0.5, "max": 10.0, "default": 2.5, "key": "thickness"},
            {"label": "预期体内服役周期 (天)", "type": "slider", "min": 30, "max": 730, "default": 180, "key": "degradation_time"},
            {"label": "生物相容性认证", "type": "selectbox", "options": ["ISO 10993 (植入级)", "体外接触级"], "key": "biocompatibility"}
        ],
        "search_suffix": "medical implant dynamic fatigue degradation rate ISO 10993 scholarly research",
        "strict_constraint": "严禁提及军工、航空等词汇！聚焦于组织工程、降解毒性、FDA准入。对标天然骨骼或PEEK。"
    },
    "人形机器人核心骨架 (高动载/刚度)": {
        "part_options": ["下肢大扭矩传动连杆", "主承力躯干框架", "末端高频执行器外壳"],
        "ui_inputs": [
            {"label": "零件设计壁厚 (mm)", "type": "slider", "min": 1.0, "max": 20.0, "default": 5.0, "key": "thickness"},
            {"label": "结构阻尼比 (ζ)", "type": "slider", "min": 0.01, "max": 0.50, "default": 0.05, "key": "damping_ratio"},
            {"label": "最高移动爆发速度 (m/s)", "type": "number", "default": 5.0, "key": "target_speed"}
        ],
        "search_suffix": "humanoid robot structural frame fatigue dynamic response lightweight scholarly research",
        "strict_constraint": "严禁提及医疗、防弹标准！聚焦于高频伺服电机启停带来的动态疲劳与惯量拖累。对标7075航空铝。"
    },
    "军工：单兵装甲与防护装备 (防弹/吸能)": {
        "part_options": ["NIJ III级 防弹插板", "战术外骨骼承力件", "头盔缓冲外壳"],
        "ui_inputs": [
            {"label": "装甲/护板设计厚度 (mm)", "type": "slider", "min": 5.0, "max": 30.0, "default": 12.5, "key": "thickness"},
            {"label": "目标抗击打速度 (m/s)", "type": "number", "default": 850, "key": "strike_velocity"},
            {"label": "抗冲击吸能率 (%)", "type": "slider", "min": 10, "max": 99, "default": 75, "key": "energy_absorption"}
        ],
        "search_suffix": "ballistic armor plate impact resistance blunt trauma MIL-STD scholarly research",
        "strict_constraint": "严禁提及医疗植入、降解等词汇！聚焦于应力波传导、防弹极限。对标Kevlar或UHMWPE。"
    },
    "航空航天与eVTOL飞行器 (极致轻量化)": {
        "part_options": ["机翼主承力翼梁", "机舱轻量化骨架", "发动机耐温整流罩"],
        "ui_inputs": [
            {"label": "结构件壁厚 (mm)", "type": "slider", "min": 0.5, "max": 15.0, "default": 3.0, "key": "thickness"},
            {"label": "最高服役温度 (℃)", "type": "number", "default": 150, "key": "max_temp"},
            {"label": "阻燃等级", "type": "selectbox", "options": ["UL94-V0 (最高)", "UL94-V1", "不要求"], "key": "flame_retardant"}
        ],
        "search_suffix": "aerospace structural materials thermal stability FAA regulations scholarly research",
        "strict_constraint": "严禁提及医疗或民用标准！重点分析高低温循环交变应力及适航认证(FAA/EASA)。"
    },
    "新能源汽车与动力电池包 (吸能/阻燃)": {
        "part_options": ["电池包防撞底护板", "白车身轻量化纵梁", "电机碳纤维转子套"],
        "ui_inputs": [
            {"label": "防护件壁厚 (mm)", "type": "slider", "min": 1.0, "max": 10.0, "default": 4.0, "key": "thickness"},
            {"label": "阻燃与热失控防护", "type": "selectbox", "options": ["UL94-V0 (电池包级)", "内饰级阻燃", "无要求"], "key": "ev_flame"},
            {"label": "碰撞吸能比 (%)", "type": "slider", "min": 10, "max": 100, "default": 60, "key": "crash_absorption"}
        ],
        "search_suffix": "EV battery enclosure crashworthiness flame retardant lightweight vehicle structure scholarly research",
        "strict_constraint": "严禁提及医疗！聚焦汽车轻量化、电池包防刺穿、热失控隔热阻燃。对标高强钢或铝合金压铸件。"
    },
    "工业协作机械臂 (精度与疲劳导向)": {
        "part_options": ["高速协作机械臂主段", "重载机床主轴外壳", "精密末端治具"],
        "ui_inputs": [
            {"label": "管材壁厚 (mm)", "type": "slider", "min": 2.0, "max": 15.0, "default": 6.0, "key": "thickness"},
            {"label": "设计疲劳寿命 (10^7次)", "type": "number", "default": 100, "key": "fatigue_cycles"},
            {"label": "刚度形变容忍度 (mm)", "type": "slider", "min": 0.01, "max": 2.00, "default": 0.10, "key": "deformation_tolerance"}
        ],
        "search_suffix": "industrial collaborative robot arm lightweight stiffness fatigue resistance scholarly research",
        "strict_constraint": "严禁偏向防弹或医疗！重点在于绝对的高刚度和高周疲劳极限。对标铸铁或挤压铝材。"
    },
    "智能穿戴与柔性外骨骼 (工效与贴合)": {
        "part_options": ["柔性外骨骼助力带", "智能手表承力表壳", "高频弯曲义肢插座"],
        "ui_inputs": [
            {"label": "材料厚度 (mm)", "type": "slider", "min": 0.1, "max": 5.0, "default": 1.5, "key": "thickness"},
            {"label": "柔性弯曲疲劳 (万次)", "type": "number", "default": 50, "key": "flex_fatigue"},
            {"label": "表面亲肤透气性", "type": "selectbox", "options": ["高透气排汗", "防风防水", "致密不透气"], "key": "breathability"}
        ],
        "search_suffix": "wearable flexible exoskeleton ergonomic material durability scholarly research",
        "strict_constraint": "不能用刚性骨架的思维评估！必须聚焦于人机交互的舒适度、柔性储能、耐磨性和生理工效学。"
    },
    "高性能纺织与极限户外装备 (耐候/舒适)": {
        "part_options": ["极限高山帐篷支撑杆", "特种降落伞承力带", "高耐磨速降绳索"],
        "ui_inputs": [
            {"label": "特征尺寸/直径 (mm)", "type": "slider", "min": 0.1, "max": 20.0, "default": 8.0, "key": "thickness"},
            {"label": "公定回潮率 (%)", "type": "number", "default": 4.5, "key": "moisture_regain"},
            {"label": "抗紫外线衰减等级", "type": "selectbox", "options": ["极高 (高海拔户外)", "中等", "无需防护"], "key": "uv_resistance"}
        ],
        "search_suffix": "high performance textile fiber moisture wicking abrasion resistance outdoor gear scholarly research",
        "strict_constraint": "必须围绕极限户外标准，分析其在户外日晒、拉扯下的性能表现。对标锦纶或超高分子量聚乙烯纤维。"
    }
}

st.title("🚀 材料特性在具体应用领域中的使用可行性评估系统")
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {gap: 6px; flex-wrap: wrap;}
    .stTabs [data-baseweb="tab"] {background-color: #f0f2f6; border-radius: 4px 4px 0 0; padding: 10px 16px; font-weight: bold;}
    .stTabs [aria-selected="true"] {background-color: #000000; color: white;}
</style>
""", unsafe_allow_html=True)

# ================= 侧边栏：先交互零件，再交互材料 =================
with st.sidebar:
    st.header("1. 目标领域与终端零件")
    domain = st.selectbox("选择下游应用领域", list(DOMAIN_CONFIG.keys()))
    current_config = DOMAIN_CONFIG[domain]
    
    target_part = st.selectbox("拟制备的核心零部件", current_config["part_options"])

    st.header("2. 零件工程设计参数")
    domain_specific_data = {}
    for item in current_config["ui_inputs"]:
        if item["type"] == "slider":
            domain_specific_data[item["key"]] = st.slider(item["label"], item["min"], item["max"], item["default"])
        elif item["type"] == "number":
            domain_specific_data[item["key"]] = st.number_input(item["label"], value=item["default"])
        elif item["type"] == "selectbox":
            domain_specific_data[item["key"]] = st.selectbox(item["label"], item["options"])
            
    st.header("3. 评估材料本征参数")
    mat_category = st.selectbox("材料所属大类", ["合成蛋白/生物基大分子", "碳基复合纤维", "可降解聚合物", "特种工程塑料"])
    density = st.number_input("密度 (g/cm³)", value=1.30)
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    material_form = st.selectbox("加工形态", ["连续长丝/纤维", "体块/水凝胶", "薄膜/涂层"])

    st.divider()
    if st.button("退出登录", type="secondary"):
        st.session_state["authenticated"] = False
        st.rerun()

# ================= 后台静默读取 API Keys =================
api_key = st.secrets.get("DEEPSEEK_API_KEY", "") 
tavily_key = st.secrets.get("TAVILY_API_KEY", "") 

# ================= 主界面评估逻辑 =================
if st.button("🚀 启动零部件级市场可行性推演", type="primary"):
    if not api_key: st.warning("系统后台未配置 DeepSeek API Key，请联系管理员。"); st.stop()

    with st.spinner(f"正在对【{target_part}】进行产品级工况仿真与深度论证..."):
        
        web_query = f"scholarly articles {mat_category} application in {target_part} {current_config['search_suffix']}"
        web_context = search_tavily(web_query, tavily_key)
        local_query = f"{mat_category} {target_part} {material_form} 加工工艺 缺陷"
        rag_context = retrieve_knowledge(local_query)

    # ---------------- 合体版！大模型指令 ----------------
    system_prompt = f"""
    你是全球顶尖的应用工程师与材料科学家。当前评估语境：【{domain}】领域下的具体零件【{target_part}】。
    
    【评估材料本征】: 密度={density}, 强度={strength}, 模量={modulus}。
    【零件工程参数】: {json.dumps(domain_specific_data, ensure_ascii=False)}。
    
    💥【领域安全隔离防线 (CRITICAL)】💥
    {current_config['strict_constraint']}
    若违反禁令跨界分析，视为严重错误！
    
    【核心任务】
    你必须结合强大的高分子材料性能和用户输入的“零件厚度/设计尺寸”，推演出该零件做出来后在市场上的竞争力。
    
    【全网实时情报】: {web_context}
    【内部私有经验】: {rag_context}
    
    【数据包装规范】
    1. 严禁提及“本地文件”、“Tavily”。
    2. 本地数据包装为：“独家内部数据库：相关测试规范”。
    3. 联网数据包装为：“学术文献：[标题]”。
    
    必须输出庞大的标准 JSON。严禁 Markdown。
    JSON 格式严格如下：
    {{
      "market_positioning": {{
        "tier": "突破性颠覆级别 或 行业第一梯队标杆 或 常规经济型替代",
        "verdict": "一句话核心定调该产品在市场上的竞争力",
        "competitor_compare": "对比现役顶尖竞品方案的优劣势",
        "derived_performance": [
          {{"metric": "推演工况指标1 (结合输入的厚度算出的极值，如极限承伤/最高速度)", "value": "带单位的震撼数据"}},
          {{"metric": "推演工况指标2 (如理论衰减/磨损寿命)", "value": "带单位的数据"}}
        ]
      }},
      "radar": {{"绝对强度容限": 100, "刚度与几何稳定性": 60, "轻量化收益": 95, "成型良率": 45, "专属环境抗性": 80, "商业落地性": 90}},
      "base_metrics": [
        {{"metric": "核心抗拉极限", "Base1": 570, "Base2": 3000, "NewMat": {strength}}},
        {{"metric": "绝对模量支撑", "Base1": 71, "Base2": 160, "NewMat": {modulus}}},
        {{"metric": "比强度/效能比", "Base1": 203, "Base2": 1875, "NewMat": {strength/density}}},
        {{"metric": "比模量/比刚度", "Base1": 25.3, "Base2": 100, "NewMat": {modulus/density}}}
      ],
      "summary_1": "本征对标小结",
      
      "math_sim": {{
        "part_name": "{target_part}",
        "design_goal": "核心等效目标",
        "math_latex": "写出具体的力学或理化等效方程",
        "table": [
          {{"param": "核心代换指标", "base": "基准值", "new": "计算值"}},
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
          "chart_data": [{{"x": "常规环境", "y": 100}}, {{"x": "极限挑战", "y": 20}}],
          "scenarios": [{{"range": "预警1", "desc": "后果1"}}]
        }}
      }},
      "summary_3": "盲区扫掠小结",

      "eight_dimensions": [
        {{"dim": "1. 静态载荷与壁厚补偿", "details": ["分析1", "分析2"], "chart_metric": "等效强度倍数", "base_val": 1.0, "new_val": 3.2}},
        {{"dim": "2. 动态磨损与疲劳衰减", "details": ["分析1", "分析2"], "chart_metric": "疲劳寿命预估", "base_val": 100, "new_val": 80}},
        {{"dim": "3. 几何适配与界面成型", "details": ["分析1", "分析2"], "chart_metric": "工艺良率", "base_val": 95, "new_val": 60}},
        {{"dim": "4. 【重点】领域专属生化/理化抗性", "details": ["必须结合输入的专属参数深度剖析", "论证2"], "chart_metric": "环境保持率", "base_val": 90, "new_val": 45}},
        {{"dim": "5. 材料微观机理影响", "details": ["剖析", "数据"], "chart_metric": "结构优越度", "base_val": 50, "new_val": 90}},
        {{"dim": "6. 终端经济效益与降本", "details": ["BOM表推演", "论证"], "chart_metric": "降本幅度(%)", "base_val": 0, "new_val": 15}},
        {{"dim": "7. 全生命周期碳足迹", "details": ["分析1", "分析2"], "chart_metric": "ESG表现", "base_val": 20, "new_val": 85}},
        {{"dim": "8. 行业标准准入难度", "details": ["分析1", "分析2"], "chart_metric": "准入周期", "base_val": 10, "new_val": 18}}
      ],
      "summary_4": "八维切片小结",

      "grand_verdict": {{
        "summary": "最终选型陈词：明确投产建议。",
        "strengths": ["商业优势1", "商业优势2"],
        "weaknesses": ["致命短板1", "致命短板2"]
      }},
      
      "reference_sources": ["独家内部数据库: xxx规范", "学术文献: xxx研究报告"]
    }}
    """

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.2}

    with st.spinner("架构隔离防线已启动，正在生成最终图纸与评测报告..."):
        try:
            response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = json.loads(response.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip())
            
            st.success(f"✅ 【{target_part}】市场定位与深度论证完成！")

            # ================= 🏆 顶层亮点：市场定位看板与黑白工程图 =================
            st.markdown(f"## 🏆 终端产品市场定位：{data['market_positioning']['tier']}")
            st.info(f"**核心定调**：{data['market_positioning']['verdict']}")
            
            top_col1, top_col2 = st.columns([1.2, 1])
            with top_col1:
                st.markdown("#### ⚔️ 市场竞品对标分析")
                st.write(data['market_positioning']['competitor_compare'])
                st.markdown("#### ⚙️ 终端工况数据推演 (基于输入尺寸)")
                for item in data['market_positioning']['derived_performance']:
                    st.markdown(f"- **{item['metric']}**: `{item['value']}`")
            
            with top_col2:
                # 渲染黑白 CAD 线框图
                st.plotly_chart(draw_cad_blueprint(target_part), use_container_width=True)
            
            st.divider()

            # ================= I. 雷达与基础矩阵 =================
            st.subheader("I. 本征参数与多维潜力对标")
            c_radar, c_bars = st.columns([1, 2.5])
            with c_radar:
                df_radar = pd.DataFrame(dict(r=list(data['radar'].values()), theta=list(data['radar'].keys())))
                fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True)
                fig_radar.update_traces(fill='toself', line_color='#000000')
                st.plotly_chart(fig_radar, use_container_width=True)

            with c_bars:
                bm = data['base_metrics']
                r1c1, r1c2 = st.columns(2)
                r2c1, r2c2 = st.columns(2)
                def plot_mini(md, container):
                    fig = px.bar(pd.DataFrame({"方案": ["基准A", "基准B", "入库新材"], "数值": [md['Base1'], md['Base2'], md['NewMat']]}), x="方案", y="数值", text_auto='.2s', color="方案", color_discrete_sequence=["#d3d3d3", "#a9a9a9", "#000000"])
                    fig.update_layout(title=md['metric'], showlegend=False, height=180, margin=dict(l=10, r=10, t=30, b=10))
                    container.plotly_chart(fig, use_container_width=True)
                plot_mini(bm[0], r1c1); plot_mini(bm[1], r1c2)
                plot_mini(bm[2], r2c1); plot_mini(bm[3], r2c2)

            st.info(f"**📌 模块小结：** {data['summary_1']}")
            st.divider()

            # ================= II. 结构等效计算 =================
            st.subheader("II. 结构代换与重量效能核算")
            sim = data['math_sim']
            with st.container(border=True):
                st.markdown(f"**🎯 核心等效推导方程**")
                st.markdown(sim['math_latex'])
            
            sc1, sc2 = st.columns([1.5, 1])
            with sc1:
                st.dataframe(pd.DataFrame(sim["table"]).rename(columns={"param": "关键参数", "base": "传统方案", "new": "新材代换"}), use_container_width=True, hide_index=True)
            with sc2:
                fig_wt = px.bar(pd.DataFrame({"方案": ["传统基准", "新设计"], "效能": [sim['chart_vals']['base_wt'], sim['chart_vals']['new_wt']]}), x="方案", y="效能", color="方案", text="效能", height=200, color_discrete_map={"传统基准": "#7f7f7f", "新设计": "#000000"})
                fig_wt.update_layout(showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_wt, use_container_width=True)
            st.info(f"**📌 模块小结：** {data['summary_2']}")
            st.divider()

            # ================= III. 盲区预演 =================
            st.subheader("III. 领域核心风险扫掠预演")
            swp = data['parameter_sweep']
            swp_c1, swp_c2 = st.columns(2)
            with swp_c1:
                with st.container(border=True):
                    sw1 = swp['sweep_1']
                    fig_1 = px.bar(pd.DataFrame(sw1['chart_data']), x="x", y="y", title=sw1['chart_title'], height=220, color_discrete_sequence=['#4a4a4a'])
                    fig_1.update_layout(xaxis_title="预估区间", yaxis_title="理论响应", margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(fig_1, use_container_width=True)
                    for sc in sw1['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
            with swp_c2:
                with st.container(border=True):
                    sw2 = swp['sweep_2']
                    fig_2 = px.line(pd.DataFrame(sw2['chart_data']), x="x", y="y", markers=True, title=sw2['chart_title'], height=220, color_discrete_sequence=['#000000'])
                    fig_2.update_layout(xaxis_title="环境应力", yaxis_title="保持率", margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(fig_2, use_container_width=True)
                    for sc in sw2['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
            st.info(f"**📌 模块小结：** {data['summary_3']}")
            st.divider()

            # ================= IV. 八维切片 =================
            st.subheader("IV. 八维深度切片剖析")
            dims = data['eight_dimensions']
            tabs = st.tabs([d['dim'] for d in dims])
            for i, tab in enumerate(tabs):
                with tab:
                    tab_c1, tab_c2 = st.columns([1.5, 1])
                    with tab_c1:
                        for d in dims[i]['details']: st.markdown(f"- {d}")
                    with tab_c2:
                        fig_tab = px.bar(pd.DataFrame({"对象": ["现役", "新材"], "数值": [dims[i]['base_val'], dims[i]['new_val']]}), x="数值", y="对象", orientation='h', text="数值", color="对象", color_discrete_sequence=["#a9a9a9", "#000000"], title=dims[i]['chart_metric'])
                        fig_tab.update_layout(showlegend=False, height=180, margin=dict(l=10, r=10, t=40, b=10))
                        st.plotly_chart(fig_tab, use_container_width=True)
            st.info(f"**📌 模块小结：** {data['summary_4']}")
            st.divider()

            # ================= V. 结案决议与数据溯源 =================
            st.subheader("V. 商业落地决议与溯源")
            verdict = data['grand_verdict']
            st.success(f"**🏆 终局定调：** {verdict['summary']}")
            v_in1, v_in2 = st.columns(2)
            with v_in1:
                st.markdown("##### 🌟 核心投产优势")
                for s in verdict['strengths']: st.markdown(f"✔️ {s}")
            with v_in2:
                st.markdown("##### ⚠️ 致命工程短板")
                for w in verdict['weaknesses']: st.markdown(f"❌ {w}")
                
            st.markdown("#### 📚 数据溯源 (Data Origins)")
            for ref in data.get('reference_sources', []): st.markdown(f"- 🔗 **{ref}**")

        except Exception as e:
            st.error(f"后台节点过载或数据流中断。错误追踪: {str(e)}")
