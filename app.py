import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math

# ================= UI 页面基础配置 =================
st.set_page_config(page_title="材料可行性评估系统", layout="wide", initial_sidebar_state="expanded")

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if not st.session_state["authenticated"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 1, 1])
    with c2:
        st.info("🛡️ 该评估系统已加密，仅限受邀用户访问。")
        pwd = st.text_input("请输入专属邀请码：", type="password")
        if st.button("解锁系统", type="primary", use_container_width=True):
            if pwd == "VIP2026": 
                st.session_state["authenticated"] = True
                st.rerun()
            else: st.error("邀请码错误或已过期！")
    st.stop()

# ================= 导入本地挂载与联网引擎 =================
try:
    from rag_engine import retrieve_knowledge
    from db_connector import init_db, get_material_data
    init_db()
except ImportError:
    def retrieve_knowledge(query, k=3): return "本地知识库尚未部署。"
    def get_material_data(mat_name): return None

def search_tavily(query, api_key):
    if not api_key: return "未配置 Tavily API Key"
    try:
        res = requests.post("https://api.tavily.com/search", json={"api_key": api_key, "query": query, "search_depth": "advanced", "include_answer": True, "max_results": 3}, timeout=15).json()
        return f"【全网提炼】: {res.get('answer', '无')}\n【来源】: {str(res.get('results', []))}"
    except Exception as e: return f"检索失败: {str(e)}"

# ================= 🌟 黑白 CAD 线框图生成引擎 🌟 =================
def draw_cad_blueprint(part_name):
    """纯数学生成的黑白工程线框网格，极具工程师调性，无需外部API"""
    x = [i*0.2 - 5 for i in range(50)]
    y = [i*0.2 - 5 for i in range(50)]
    z = [[math.sin(xi) * math.cos(yi) * 2 for xi in x] for yi in y]
    
    fig = go.Figure(data=[go.Surface(z=z, x=x, y=y, colorscale='Greys', showscale=False, opacity=0.9)])
    fig.update_traces(contours_z=dict(show=True, usecolormap=False, highlightcolor="black", project_z=True))
    fig.update_layout(
        title=dict(text=f"📐 二维/三维工程简图拟合: {part_name}", font=dict(color="black")),
        scene=dict(
            xaxis=dict(showbackground=False, color="black", gridcolor="lightgrey", title="长度 (X)"),
            yaxis=dict(showbackground=False, color="black", gridcolor="lightgrey", title="宽度 (Y)"),
            zaxis=dict(showbackground=False, color="black", gridcolor="lightgrey", title="壁厚/形变 (Z)")
        ),
        paper_bgcolor='white', plot_bgcolor='white', margin=dict(l=0, r=0, t=40, b=0), height=300
    )
    return fig

# ================= 🌟 领域零件与尺寸配置字典 🌟 =================
DOMAIN_CONFIG = {
    "生物医疗与人体植入物 (生化导向)": {
        "part_options": ["骨折内固定承力板", "高强度人工韧带", "可降解骨钉"],
        "ui_inputs": [
            {"label": "零件设计壁厚/直径 (mm)", "type": "slider", "min": 0.5, "max": 10.0, "default": 2.5, "key": "thickness"},
            {"label": "预期体内服役周期 (天)", "type": "slider", "min": 30, "max": 1000, "default": 365, "key": "life_cycle"},
            {"label": "目标承载应力 (MPa)", "type": "number", "default": 150, "key": "target_load"}
        ],
        "search_suffix": "medical implant dynamic fatigue degradation rate ISO 10993"
    },
    "人形机器人核心骨架 (高动载/刚度)": {
        "part_options": ["下肢大扭矩传动连杆", "主承力躯干框架", "末端高频执行器外壳"],
        "ui_inputs": [
            {"label": "零件设计壁厚/直径 (mm)", "type": "slider", "min": 1.0, "max": 20.0, "default": 5.0, "key": "thickness"},
            {"label": "高频振动幅度预估 (mm)", "type": "slider", "min": 0.1, "max": 5.0, "default": 0.5, "key": "vibration"},
            {"label": "最高移动爆发速度 (m/s)", "type": "number", "default": 5.0, "key": "target_speed"}
        ],
        "search_suffix": "humanoid robot structural frame fatigue dynamic response lightweight"
    },
    "军工：单兵装甲与防护装备 (防弹/吸能)": {
        "part_options": ["NIJ III级 防弹插板", "战术外骨骼承力件", "头盔缓冲外壳"],
        "ui_inputs": [
            {"label": "装甲/护板设计厚度 (mm)", "type": "slider", "min": 5.0, "max": 30.0, "default": 12.5, "key": "thickness"},
            {"label": "目标抗击打速度 (m/s)", "type": "number", "default": 850, "key": "strike_velocity"},
            {"label": "允许最大形变深度 (mm)", "type": "slider", "min": 10, "max": 44, "default": 25, "key": "deformation"}
        ],
        "search_suffix": "ballistic armor plate impact resistance blunt trauma MIL-STD"
    }
}

st.title("🚀 零部件级材料应用可行性评估系统")
st.markdown("<style>.stTabs [data-baseweb='tab-list'] {gap: 6px;} .stTabs [data-baseweb='tab'] {background-color: #f0f2f6; font-weight: bold;} .stTabs [aria-selected='true'] {background-color: #000; color: white;}</style>", unsafe_allow_html=True)

# ================= 侧边栏：动态零部件 UI 渲染 =================
with st.sidebar:
    st.header("1. 目标领域与终端零件")
    domain = st.selectbox("选择下游应用领域", list(DOMAIN_CONFIG.keys()))
    current_config = DOMAIN_CONFIG[domain]
    target_part = st.selectbox("拟制备的核心零部件", current_config["part_options"])
    
    st.header("2. 材料基础本征")
    mat_category = st.selectbox("材料所属大类", ["合成蛋白/生物基大分子", "碳基复合纤维", "特种工程塑料"])
    density = st.number_input("密度 (g/cm³)", value=1.30)
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)

    st.header("3. 零件工程设计参数")
    domain_specific_data = {}
    for item in current_config["ui_inputs"]:
        if item["type"] == "slider": domain_specific_data[item["key"]] = st.slider(item["label"], item["min"], item["max"], item["default"])
        elif item["type"] == "number": domain_specific_data[item["key"]] = st.number_input(item["label"], value=item["default"])
            
    st.divider()
    if st.button("退出登录", type="secondary"):
        st.session_state["authenticated"] = False
        st.rerun()

api_key = st.secrets.get("DEEPSEEK_API_KEY", "") 
tavily_key = st.secrets.get("TAVILY_API_KEY", "") 

# ================= 主界面评估逻辑 =================
if st.button("🚀 启动零部件级市场可行性推演", type="primary"):
    if not api_key: st.warning("未配置 DeepSeek API Key。"); st.stop()

    with st.spinner(f"正在对【{target_part}】进行产品级工况仿真与市场定位评测..."):
        
        web_query = f"scholarly articles {mat_category} application in {target_part} {current_config['search_suffix']}"
        web_context = search_tavily(web_query, tavily_key)
        local_query = f"{mat_category} {target_part} 加工尺寸 厚度 规范"
        rag_context = retrieve_knowledge(local_query)

    system_prompt = f"""
    你是全球顶尖的应用工程师。正在评估【{target_part}】(属于{domain}领域) 的市场可行性。
    材料参数: 密度={density}, 强度={strength}, 模量={modulus}。
    零件设计参数: {json.dumps(domain_specific_data, ensure_ascii=False)}。
    
    【核心任务】：
    1. 必须推导出该零件做出来后在市场上的【定位级别】（分为：突破性颠覆级别 / 行业第一梯队标杆 / 常规经济型替代）。结合高强度的蛋白材料特性做出大胆且严谨的预判。
    2. 根据输入的零件厚度等参数，推算出终端工况表现（如抗击打、移动速度、磨损寿命等具体数值）。
    
    【全网情报】: {web_context}
    【本地经验】: {rag_context}
    
    必须输出标准 JSON。严禁 Markdown。
    JSON 格式严格如下：
    {{
      "market_positioning": {{
        "tier": "突破性颠覆级别 或 行业第一梯队标杆 或 常规替代",
        "verdict": "一句话核心定调该产品在市场上的竞争力",
        "competitor_compare": "对比现役最顶尖方案的具体优势和劣势",
        "derived_performance": [
          {{"metric": "推演工况指标1 (如最高移动速度/极限承伤)", "value": "结合输入参数算出的牛逼数据"}},
          {{"metric": "推演工况指标2 (如理论磨损寿命/衰减周期)", "value": "带单位的具体数据"}}
        ]
      }},
      "radar": {{"绝对强度容限": 100, "刚度与几何稳定性": 60, "轻量化收益": 95, "加工成型率": 45, "专属环境抗性": 80, "商业落地性": 90}},
      "base_metrics": [
        {{"metric": "核心抗拉极限", "Base1": 570, "Base2": 3000, "NewMat": {strength}}},
        {{"metric": "绝对模量支撑", "Base1": 71, "Base2": 160, "NewMat": {modulus}}}
      ],
      "eight_dimensions": [
        {{"dim": "1. 静态载荷与壁厚补偿", "details": ["分析1", "分析2"], "chart_metric": "等效强度倍数", "base_val": 1.0, "new_val": 3.2}},
        {{"dim": "2. 动态磨损与疲劳衰减", "details": ["分析1", "分析2"], "chart_metric": "疲劳寿命预估", "base_val": 100, "new_val": 80}},
        {{"dim": "3. 终端经济效益与良率", "details": ["分析1", "分析2"], "chart_metric": "降本幅度(%)", "base_val": 0, "new_val": 15}},
        {{"dim": "4. 领域专属抗性(防弹/降解等)", "details": ["分析1", "分析2"], "chart_metric": "环境保持率", "base_val": 90, "new_val": 45}}
      ],
      "reference_sources": ["独家内部数据库: xxx工艺数据", "学术文献: xxx研究"]
    }}
    """

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.2}

    with st.spinner("正在绘制工程线框图并生成最终商业定位..."):
        try:
            response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = json.loads(response.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip())
            
            st.success("✅ 零部件级评估与市场定位推演完成！")

            # ================= 核心亮点 1：市场定位看板与图纸 (置于最顶层) =================
            st.markdown(f"## 🏆 终端产品市场定位：{data['market_positioning']['tier']}")
            st.info(f"**核心定调**：{data['market_positioning']['verdict']}")
            
            top_col1, top_col2 = st.columns([1.2, 1])
            with top_col1:
                st.markdown("#### ⚔️ 市场竞品对标分析")
                st.write(data['market_positioning']['competitor_compare'])
                st.markdown("#### ⚙️ 理论推演工况数据 (基于输入的尺寸与载荷)")
                for item in data['market_positioning']['derived_performance']:
                    st.markdown(f"- **{item['metric']}**: `{item['value']}`")
            
            with top_col2:
                # 渲染黑白 CAD 线框图
                st.plotly_chart(draw_cad_blueprint(target_part), use_container_width=True)
            
            st.divider()

            # ================= 原有的图表分析模块保留 =================
            st.subheader("I. 本征参数与多维潜力")
            c_radar, c_bars = st.columns([1, 1.5])
            with c_radar:
                df_radar = pd.DataFrame(dict(r=list(data['radar'].values()), theta=list(data['radar'].keys())))
                fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True)
                fig_radar.update_traces(fill='toself', line_color='#000000')
                st.plotly_chart(fig_radar, use_container_width=True)

            with c_bars:
                bm = data['base_metrics']
                r1c1, r1c2 = st.columns(2)
                def plot_mini(md, container):
                    fig = px.bar(pd.DataFrame({"方案": ["基准A", "基准B", "入库新材"], "数值": [md['Base1'], md['Base2'], md['NewMat']]}), x="方案", y="数值", text_auto='.2s', color="方案", color_discrete_sequence=["#d3d3d3", "#a9a9a9", "#000000"])
                    fig.update_layout(title=md['metric'], showlegend=False, height=220, margin=dict(l=10, r=10, t=30, b=10))
                    container.plotly_chart(fig, use_container_width=True)
                plot_mini(bm[0], r1c1); plot_mini(bm[1], r1c2)
            
            st.divider()
            st.subheader("II. 四维深度剖析")
            dims = data['eight_dimensions']
            tabs = st.tabs([d['dim'] for d in dims])
            for i, tab in enumerate(tabs):
                with tab:
                    tab_c1, tab_c2 = st.columns([1.5, 1])
                    with tab_c1:
                        for d in dims[i]['details']: st.markdown(f"- {d}")
                    with tab_c2:
                        fig_tab = px.bar(pd.DataFrame({"对标对象": ["现役基准", "新材料"], "响应数值": [dims[i]['base_val'], dims[i]['new_val']]}), x="响应数值", y="对标对象", orientation='h', text="响应数值", color="对标对象", color_discrete_sequence=["#a9a9a9", "#000000"], title=dims[i]['chart_metric'])
                        fig_tab.update_layout(showlegend=False, height=180, margin=dict(l=10, r=10, t=40, b=10))
                        st.plotly_chart(fig_tab, use_container_width=True)

            st.divider()
            st.subheader("📚 数据溯源 (Data Origins)")
            for ref in data.get('reference_sources', []): st.markdown(f"- 🔗 **{ref}**")

        except Exception as e:
            st.error(f"后台节点过载或数据流中断。错误追踪: {str(e)}")
