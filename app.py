import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# ================= UI 页面基础配置 =================
st.set_page_config(page_title="材料可行性评估系统", layout="wide", initial_sidebar_state="expanded")

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "llm_report" not in st.session_state: st.session_state["llm_report"] = None
if "last_part" not in st.session_state: st.session_state["last_part"] = None

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

# ================= 🌟 黑白 CAD 实时物理引擎 🌟 =================
def calculate_physics(topology, dims, strength_mpa, modulus_gpa):
    """底层物理引擎：根据材料本征和实时尺寸推算"""
    E = modulus_gpa * 1000  # GPa 转 MPa
    S = strength_mpa
    if topology == "BEAM":
        L, D, t = dims['length'], dims['diameter'], dims['thickness']
        I = math.pi * (D**4 - (max(0.1, D-2*t))**4) / 64
        max_force = (S * I / (D/2)) / L if L>0 else 0
        deformation = (max_force * L**3) / (3 * E * I) if I>0 else 0
        return {"load": max_force, "def": deformation, "unit": "N (抗弯极限)"}
    elif topology == "PLATE":
        L, W, t = dims['length'], dims['width'], dims['thickness']
        max_force = (4 * S * (t**2)) / L if L>0 else 0
        I = (W * t**3) / 12
        deformation = (max_force * L**3) / (48 * E * I) if I>0 else 0
        return {"load": max_force, "def": deformation, "unit": "N (中心冲压极限)"}
    elif topology == "STRAP":
        W, t = dims['width'], dims['thickness']
        area = W * t
        max_force = S * area
        deformation = (max_force * 1000) / (E * area) if area>0 else 0 # 每米形变
        return {"load": max_force, "def": deformation, "unit": "N (纯拉伸极限)"}

def render_3d_blueprint(topology, dims, physics):
    """生成黑白线框工程图"""
    fig = go.Figure()
    text_color = "black"
    if topology == "BEAM":
        L, D = dims['length'], dims['diameter']
        theta, z = np.meshgrid(np.linspace(0, 2*np.pi, 20), np.linspace(0, L, 20))
        fig.add_trace(go.Surface(x=(D/2)*np.cos(theta), y=(D/2)*np.sin(theta), z=z, colorscale='Greys', opacity=0.8, showscale=False))
        anno_text = f"外径: {D}mm<br>壁厚: {dims['thickness']}mm<br>抗弯推演: {physics['load']:.0f}N"
    elif topology == "PLATE":
        L, W, t = dims['length'], dims['width'], dims['thickness']
        x, y, z = np.array([0, L, L, 0, 0, L, L, 0]), np.array([0, 0, W, W, 0, 0, W, W]), np.array([0, 0, 0, 0, t, t, t, t])
        fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=[0,0,0,1,1,2,4,4,4,5,5,6], j=[1,2,3,2,5,6,5,6,7,6,7,2], k=[2,3,0,5,6,1,6,7,4,7,2,7], color='lightgrey', opacity=0.8))
        anno_text = f"厚度: {t}mm<br>抗冲压推演: {physics['load']:.0f}N"
    elif topology == "STRAP":
        W, t = dims['width'], dims['thickness']
        x, y, z = np.array([0, 100, 100, 0, 0, 100, 100, 0]), np.array([-W/2, -W/2, W/2, W/2, -W/2, -W/2, W/2, W/2]), np.array([0, 0, 0, 0, t, t, t, t])
        fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=[0,0,0,1,1,2,4,4,4,5,5,6], j=[1,2,3,2,5,6,5,6,7,6,7,2], k=[2,3,0,5,6,1,6,7,4,7,2,7], color='darkgrey', opacity=0.9))
        anno_text = f"织带宽/厚: {W}/{t}mm<br>极限拉断力: {physics['load']:.0f}N"

    fig.update_layout(
        scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False), annotations=[dict(showarrow=False, x=0, y=0, z=0, text=anno_text, font=dict(color=text_color, size=14), bgcolor="rgba(255,255,255,0.9)", bordercolor="black")]),
        paper_bgcolor='white', plot_bgcolor='white', margin=dict(l=0, r=0, t=20, b=0), height=300, title=dict(text="📐 实时工程蓝图", font=dict(color="black", size=16))
    )
    return fig

# ================= 🌟 知识图谱：6大领域及精细零件字典 🌟 =================
DOMAIN_CONFIG = {
    "生物医疗植入物": {
        "parts": {
            "骨折内固定承力板": {
                "topology": "PLATE", "search_suffix": "bone plate ISO 10993 medical implant", "constraint": "对标钛合金骨板，聚焦应力遮挡与降解。",
                "ui_inputs": [{"label": "骨板长度 (mm)", "key": "length", "min": 30.0, "max": 150.0, "default": 80.0}, {"label": "骨板宽度 (mm)", "key": "width", "min": 5.0, "max": 20.0, "default": 12.0}, {"label": "骨板厚度 (mm)", "key": "thickness", "min": 1.0, "max": 6.0, "default": 3.5}]
            }
        }
    },
    "人形机器人": {
        "parts": {
            "下肢大扭矩连杆": {
                "topology": "BEAM", "search_suffix": "humanoid robot link dynamic stiffness", "constraint": "对标7075航空铝，聚焦高频电机启停的疲劳与形变。",
                "ui_inputs": [{"label": "外管径 (mm)", "key": "diameter", "min": 10.0, "max": 50.0, "default": 30.0}, {"label": "连杆长度 (mm)", "key": "length", "min": 100.0, "max": 600.0, "default": 350.0}, {"label": "管壁厚度 (mm)", "key": "thickness", "min": 1.0, "max": 10.0, "default": 3.0}]
            }
        }
    },
    "军工：单兵装甲": {
        "parts": {
            "NIJ III级 防弹插板": {
                "topology": "PLATE", "search_suffix": "ballistic armor plate MIL-STD impact", "constraint": "对标芳纶复合板，聚焦防弹极限与背部形变。",
                "ui_inputs": [{"label": "插板长度 (mm)", "key": "length", "min": 200.0, "max": 400.0, "default": 300.0}, {"label": "插板宽度 (mm)", "key": "width", "min": 150.0, "max": 300.0, "default": 250.0}, {"label": "核心厚度 (mm)", "key": "thickness", "min": 5.0, "max": 30.0, "default": 12.0}]
            }
        }
    },
    "航空航天": {
        "parts": {
            "机翼主承力翼梁": {
                "topology": "BEAM", "search_suffix": "aerospace wing spar lightweight composite", "constraint": "对标碳纤维预浸料，聚焦飞行气动载荷与轻量化。",
                "ui_inputs": [{"label": "翼梁高度/直径 (mm)", "key": "diameter", "min": 20.0, "max": 100.0, "default": 50.0}, {"label": "翼梁长度 (mm)", "key": "length", "min": 1000.0, "max": 5000.0, "default": 2000.0}, {"label": "壁厚 (mm)", "key": "thickness", "min": 2.0, "max": 15.0, "default": 5.0}]
            }
        }
    },
    "高性能纺织与户外": {
        "parts": {
            "特种降落伞承力带": {
                "topology": "STRAP", "search_suffix": "parachute strap UHMWPE high strength", "constraint": "对标UHMWPE或锦纶，分析开伞瞬间拉伸冲击。",
                "ui_inputs": [{"label": "织带宽度 (mm)", "key": "width", "min": 10.0, "max": 50.0, "default": 25.0}, {"label": "织带厚度 (mm)", "key": "thickness", "min": 0.5, "max": 5.0, "default": 2.0}]
            },
            "极限高山帐篷支撑杆": {
                "topology": "BEAM", "search_suffix": "tent pole high altitude wind resistance", "constraint": "对标高标号航空铝，分析狂风下的抗弯折力。",
                "ui_inputs": [{"label": "外径 (mm)", "key": "diameter", "min": 5.0, "max": 20.0, "default": 8.5}, {"label": "管壁厚度 (mm)", "key": "thickness", "min": 0.5, "max": 3.0, "default": 1.0}, {"label": "跨度长度 (mm)", "key": "length", "min": 500.0, "max": 2000.0, "default": 1000.0}]
            }
        }
    },
    "新能源汽车": {
        "parts": {
            "电池包防撞底护板": {
                "topology": "PLATE", "search_suffix": "EV battery enclosure crashworthiness", "constraint": "对标铝合金压铸件，聚焦底盘防刮击穿及阻燃。",
                "ui_inputs": [{"label": "护板长度 (mm)", "key": "length", "min": 500.0, "max": 2000.0, "default": 1200.0}, {"label": "护板宽度 (mm)", "key": "width", "min": 300.0, "max": 1000.0, "default": 800.0}, {"label": "护板厚度 (mm)", "key": "thickness", "min": 2.0, "max": 15.0, "default": 4.0}]
            }
        }
    }
}

st.title("🚀 材料特性在具体应用领域中的使用可行性评估系统")
st.markdown("<style>.stTabs [data-baseweb='tab-list'] {gap: 6px;} .stTabs [data-baseweb='tab'] {background-color: #f0f2f6; font-weight: bold;} .stTabs [aria-selected='true'] {background-color: #000; color: white;}</style>", unsafe_allow_html=True)

# ================= 侧边栏：参数输入 =================
with st.sidebar:
    st.header("1. 目标终端零部件")
    domain = st.selectbox("选择应用领域", list(DOMAIN_CONFIG.keys()))
    parts_dict = DOMAIN_CONFIG[domain]["parts"]
    target_part = st.selectbox("核心零部件", list(parts_dict.keys()))
    part_config = parts_dict[target_part]
    
    st.header("2. 材料本征参数")
    mat_category = st.selectbox("材料大类", ["合成蛋白/生物基", "碳纤维复合", "工程塑料", "特种合金"])
    density = st.number_input("密度 (g/cm³)", value=1.30)
    strength = st.number_input("抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    
    # 侦测领域变化，清空旧报告
    if target_part != st.session_state["last_part"]:
        st.session_state["llm_report"] = None
        st.session_state["last_part"] = target_part

    st.divider()
    generate_btn = st.button("🚀 启动深度评测与图纸生成", type="primary", use_container_width=True)

api_key = st.secrets.get("DEEPSEEK_API_KEY", "")
tavily_key = st.secrets.get("TAVILY_API_KEY", "")

# ================= 大模型核心数据获取逻辑 =================
if generate_btn:
    if not api_key: st.warning("未配置 DeepSeek API Key。"); st.stop()
    with st.spinner(f"正在读取独家数据库，为【{target_part}】撰写专业评测..."):
        
        web_query = f"scholarly articles {mat_category} {target_part} {part_config['search_suffix']}"
        web_context = search_tavily(web_query, tavily_key)
        local_query = f"{mat_category} {target_part} 加工 规范"
        rag_context = retrieve_knowledge(local_query)

        # ！！保留了 v19 的庞大 JSON 格式，全面囊括所有分析模块 ！！
        system_prompt = f"""
        你是顶尖应用工程师。评估材料在【{domain}】领域【{target_part}】上的商业可行性。
        材料: 密度={density}, 强度={strength}MPa, 模量={modulus}GPa。
        约束: {part_config['constraint']}
        情报: {web_context}
        经验: {rag_context}
        
        【数据包装规范】
        禁止提“本地文件”或“Tavily”。包装为：“独家内部数据库：xxx” 或 “学术文献：xxx”。
        
        必须输出极度庞大的标准 JSON：
        {{
          "market_positioning": {{
            "tier": "突破性颠覆级别 或 行业第一梯队标杆 或 常规经济型替代",
            "verdict": "一句话核心定调产品的竞争力",
            "competitor_compare": "详细对比现役最顶尖方案的优劣势"
          }},
          "radar": {{"绝对强度": 100, "刚度稳定": 60, "轻量化收益": 95, "加工成型": 45, "专属抗性": 80, "商业落地": 90}},
          "base_metrics": [
            {{"metric": "核心抗拉极限", "Base1": 570, "Base2": 3000, "NewMat": {strength}}},
            {{"metric": "绝对模量支撑", "Base1": 71, "Base2": 160, "NewMat": {modulus}}},
            {{"metric": "比强度/效能比", "Base1": 203, "Base2": 1875, "NewMat": {strength/density}}}
          ],
          "math_sim": {{
            "part_name": "{target_part}",
            "design_goal": "核心等效目标",
            "math_latex": "写出具体的力学方程",
            "table": [{{"param": "核心代换指标", "base": "基准值", "new": "计算值"}}],
            "chart_vals": {{"base_wt": 4.25, "new_wt": 1.35}}
          }},
          "parameter_sweep": {{
            "sweep_1": {{"chart_title": "盲区波动图", "chart_data": [{{"x": "下限", "y": 20}}, {{"x": "中位", "y": 120}}, {{"x": "上限", "y": 40}}], "scenarios": [{{"range": "说明", "desc": "后果"}}]}},
            "sweep_2": {{"chart_title": "环境衰减图", "chart_data": [{{"x": "常温", "y": 100}}, {{"x": "严苛", "y": 40}}], "scenarios": [{{"range": "说明", "desc": "后果"}}]}}
          }},
          "eight_dimensions": [
            {{"dim": "1. 静态载荷补偿", "details": ["分析1", "分析2"], "chart_metric": "强度倍数", "base_val": 1.0, "new_val": 3.2}},
            {{"dim": "2. 动态疲劳衰减", "details": ["分析1"], "chart_metric": "疲劳寿命", "base_val": 100, "new_val": 80}},
            {{"dim": "3. 几何界面工艺", "details": ["分析1"], "chart_metric": "工艺良率", "base_val": 95, "new_val": 60}},
            {{"dim": "4. 【专属】领域抗性", "details": ["结合领域深度剖析"], "chart_metric": "环境保持率", "base_val": 90, "new_val": 45}},
            {{"dim": "5. 微观机理影响", "details": ["分析1"], "chart_metric": "结构优越度", "base_val": 50, "new_val": 90}},
            {{"dim": "6. 终端经济降本", "details": ["分析1"], "chart_metric": "降本(%)", "base_val": 0, "new_val": 15}},
            {{"dim": "7. ESG碳足迹", "details": ["分析1"], "chart_metric": "ESG表现", "base_val": 20, "new_val": 85}},
            {{"dim": "8. 行业准入壁垒", "details": ["分析1"], "chart_metric": "准入周期", "base_val": 10, "new_val": 18}}
          ],
          "grand_verdict": {{
            "summary": "最终投产陈词",
            "strengths": ["优势1"],
            "weaknesses": ["致命短板1"]
          }},
          "reference_sources": ["独家内部数据库: xxx规范", "学术文献: xxx研究"]
        }}
        """
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
        payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.15}
        
        try:
            res = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=90)
            res.raise_for_status()
            st.session_state["llm_report"] = json.loads(res.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip())
        except Exception as e:
            st.error(f"模型调用失败或生成格式错误: {str(e)}")

# ================= 🌟 报告渲染：交互沙盒(第1板块) + v19 全系图表 🌟 =================
if st.session_state["llm_report"]:
    data = st.session_state["llm_report"]
    
    # ---------------- 第一板块：置顶市场定位与交互沙盒 ----------------
    st.markdown(f"<h1 style='text-align: center; color: #1f77b4;'>🏆 终端产品市场定位：{data['market_positioning']['tier']}</h1>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='text-align: center;'>{data['market_positioning']['verdict']}</h4><hr>", unsafe_allow_html=True)
    
    col_sandbox, col_cad = st.columns([1, 1.2])
    current_dims = {}
    with col_sandbox:
        st.markdown(f"### ⚙️ 【{target_part}】工程参数设计沙盒")
        st.caption("👈 滑动修改尺寸，右侧 CAD图与极限力学数据将【无延迟刷新】")
        for item in part_config["ui_inputs"]:
            # 在主屏幕渲染滑动条！
            current_dims[item["key"]] = st.slider(item["label"], item["min"], item["max"], item["default"], key=f"sb_{item['key']}")
            
        st.markdown("#### ⚔️ 市场竞品对标分析")
        st.write(data['market_positioning']['competitor_compare'])

    with col_cad:
        # 秒级推算物理表现
        physics_res = calculate_physics(part_config["topology"], current_dims, strength, modulus)
        # 实时渲染带数据的 CAD 图
        st.plotly_chart(render_3d_blueprint(part_config["topology"], current_dims, physics_res), use_container_width=True)
        st.success(f"**⚡ 沙盒实时推演：** 依据当前尺寸，该结构理论极值可达 **{physics_res['load']:.0f} {physics_res['unit']}**。")

    st.markdown("---")
    
    # ---------------- 后面全系保留 v19 的硬核模块 ----------------
    
    # I. 本征参数与多维潜力
    st.subheader("I. 本征参数与多维潜力对标")
    c_radar, c_bars = st.columns([1, 2.5])
    with c_radar:
        df_radar = pd.DataFrame(dict(r=list(data['radar'].values()), theta=list(data['radar'].keys())))
        st.plotly_chart(px.line_polar(df_radar, r='r', theta='theta', line_close=True).update_traces(fill='toself', line_color='black'), use_container_width=True)

    with c_bars:
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)
        cols = [r1c1, r1c2, r2c1]
        for idx, md in enumerate(data['base_metrics']):
            fig = px.bar(pd.DataFrame({"方案": ["基准A", "基准B", "入库新材"], "数值": [md['Base1'], md['Base2'], md['NewMat']]}), x="方案", y="数值", text_auto='.2s', color="方案", color_discrete_sequence=["#d3d3d3", "#a9a9a9", "#000000"])
            fig.update_layout(title=md['metric'], showlegend=False, height=180, margin=dict(l=10, r=10, t=30, b=10))
            cols[idx].plotly_chart(fig, use_container_width=True)
    st.divider()

    # II. 数学等效推演
    st.subheader("II. 数学结构代换核算")
    sim = data['math_sim']
    st.markdown(f"**🎯 核心等效目标:** {sim['design_goal']}")
    with st.container(border=True): st.markdown(sim['math_latex'])
    sc1, sc2 = st.columns([1.5, 1])
    with sc1: st.dataframe(pd.DataFrame(sim["table"]), use_container_width=True, hide_index=True)
    with sc2:
        fig_wt = px.bar(pd.DataFrame({"方案": ["基准", "新设计"], "效能": [sim['chart_vals']['base_wt'], sim['chart_vals']['new_wt']]}), x="方案", y="效能", color="方案", text="效能", height=200, color_discrete_map={"基准": "grey", "新设计": "black"})
        fig_wt.update_layout(showlegend=False, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_wt, use_container_width=True)
    st.divider()

    # III. 盲区预演
    st.subheader("III. 领域核心风险扫掠预演")
    swp_c1, swp_c2 = st.columns(2)
    with swp_c1:
        sw1 = data['parameter_sweep']['sweep_1']
        st.plotly_chart(px.bar(pd.DataFrame(sw1['chart_data']), x="x", y="y", title=sw1['chart_title'], height=220, color_discrete_sequence=['#4a4a4a']).update_layout(margin=dict(l=0,r=0,t=30,b=0)), use_container_width=True)
        for sc in sw1['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
    with swp_c2:
        sw2 = data['parameter_sweep']['sweep_2']
        st.plotly_chart(px.line(pd.DataFrame(sw2['chart_data']), x="x", y="y", markers=True, title=sw2['chart_title'], height=220, color_discrete_sequence=['black']).update_layout(margin=dict(l=0,r=0,t=30,b=0)), use_container_width=True)
        for sc in sw2['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
    st.divider()

    # IV. 八维切片
    st.subheader("IV. 商业级八维深度剖析")
    dims = data['eight_dimensions']
    tabs = st.tabs([d['dim'] for d in dims])
    for i, tab in enumerate(tabs):
        with tab:
            tc1, tc2 = st.columns([1.5, 1])
            with tc1:
                for d in dims[i]['details']: st.markdown(f"- {d}")
            with tc2:
                fig_tab = px.bar(pd.DataFrame({"对象": ["基准", "新材"], "数值": [dims[i]['base_val'], dims[i]['new_val']]}), x="数值", y="对象", orientation='h', text="数值", color="对象", color_discrete_sequence=["#a9a9a9", "#000000"], title=dims[i]['chart_metric'])
                st.plotly_chart(fig_tab.update_layout(showlegend=False, height=150, margin=dict(l=0,r=0,t=30,b=0)), use_container_width=True)
    st.divider()

    # V. 结案决议与溯源
    st.subheader("V. 结案陈词与数据溯源")
    verdict = data['grand_verdict']
    v_in1, v_in2 = st.columns(2)
    with v_in1:
        st.markdown("##### 🌟 核心投产优势")
        for s in verdict['strengths']: st.markdown(f"✔️ {s}")
    with v_in2:
        st.markdown("##### ⚠️ 致命工程短板")
        for w in verdict['weaknesses']: st.markdown(f"❌ {w}")
        
    st.markdown("#### 📚 数据来源")
    for ref in data.get('reference_sources', []): st.markdown(f"- 🔗 **{ref}**")
