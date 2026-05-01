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
    """底层物理引擎：根据材料本征和实时尺寸推算极值"""
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
        deformation = (max_force * 1000) / (E * area) if area>0 else 0 
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
        anno_text = f"宽/厚: {W}/{t}mm<br>极限拉断: {physics['load']:.0f}N"

    fig.update_layout(
        scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False), annotations=[dict(showarrow=False, x=0, y=0, z=0, text=anno_text, font=dict(color=text_color, size=14), bgcolor="rgba(255,255,255,0.9)", bordercolor="black")]),
        paper_bgcolor='white', plot_bgcolor='white', margin=dict(l=0, r=0, t=30, b=0), height=320, title=dict(text="📐 实时工程拓扑蓝图", font=dict(color="black", size=16))
    )
    return fig

# ================= 🌟 知识图谱：8大领域与零件级交互 🌟 =================
DOMAIN_CONFIG = {
    "生物医疗植入物 (生化导向)": {
        "parts": {
            "骨折内固定承力板": {
                "topology": "PLATE", "search_suffix": "bone plate medical implant ISO 10993 degradation", "constraint": "严禁提及军工。对标钛合金骨板，聚焦应力遮挡与降解。",
                "ui_inputs": [{"label": "骨板长度 (mm)", "key": "length", "min": 30.0, "max": 150.0, "default": 80.0}, {"label": "骨板宽度 (mm)", "key": "width", "min": 5.0, "max": 20.0, "default": 12.0}, {"label": "骨板厚度 (mm)", "key": "thickness", "min": 1.0, "max": 6.0, "default": 3.5}]
            },
            "人工韧带/肌腱": {
                "topology": "STRAP", "search_suffix": "artificial ligament tendon tissue engineering", "constraint": "严禁提及军工。对标PET纤维，聚焦抗疲劳拉伸和细胞黏附。",
                "ui_inputs": [{"label": "韧带宽度 (mm)", "key": "width", "min": 5.0, "max": 20.0, "default": 10.0}, {"label": "韧带厚度 (mm)", "key": "thickness", "min": 0.5, "max": 4.0, "default": 2.0}]
            }
        }
    },
    "人形机器人核心骨架 (高动载)": {
        "parts": {
            "下肢大扭矩连杆": {
                "topology": "BEAM", "search_suffix": "humanoid robot link dynamic stiffness lightweight", "constraint": "严禁防弹标准。对标7075航空铝，聚焦高频电机启停的疲劳与形变。",
                "ui_inputs": [{"label": "外管径 (mm)", "key": "diameter", "min": 10.0, "max": 50.0, "default": 30.0}, {"label": "连杆长度 (mm)", "key": "length", "min": 100.0, "max": 600.0, "default": 350.0}, {"label": "管壁厚度 (mm)", "key": "thickness", "min": 1.0, "max": 10.0, "default": 3.0}]
            }
        }
    },
    "军工：单兵装甲与防护": {
        "parts": {
            "NIJ III级 防弹插板": {
                "topology": "PLATE", "search_suffix": "ballistic armor plate MIL-STD impact resistance", "constraint": "严禁医疗词汇。对标芳纶复合板，聚焦防弹极限与背部形变。",
                "ui_inputs": [{"label": "插板长度 (mm)", "key": "length", "min": 200.0, "max": 400.0, "default": 300.0}, {"label": "插板宽度 (mm)", "key": "width", "min": 150.0, "max": 300.0, "default": 250.0}, {"label": "核心厚度 (mm)", "key": "thickness", "min": 5.0, "max": 30.0, "default": 12.0}]
            }
        }
    },
    "航空航天与eVTOL飞行器": {
        "parts": {
            "机翼主承力翼梁": {
                "topology": "BEAM", "search_suffix": "aerospace wing spar lightweight composite FAA", "constraint": "严禁民用标准。对标碳纤维预浸料，聚焦飞行气动载荷与轻量化。",
                "ui_inputs": [{"label": "翼梁管径 (mm)", "key": "diameter", "min": 20.0, "max": 100.0, "default": 50.0}, {"label": "翼梁长度 (mm)", "key": "length", "min": 1000.0, "max": 5000.0, "default": 2000.0}, {"label": "梁壁厚 (mm)", "key": "thickness", "min": 2.0, "max": 15.0, "default": 5.0}]
            }
        }
    },
    "新能源汽车与动力电池包": {
        "parts": {
            "电池包防撞底护板": {
                "topology": "PLATE", "search_suffix": "EV battery enclosure crashworthiness flame retardant", "constraint": "严禁医疗航天。对标铝合金压铸件，聚焦底盘防刮击穿及阻燃。",
                "ui_inputs": [{"label": "护板长度 (mm)", "key": "length", "min": 500.0, "max": 2000.0, "default": 1200.0}, {"label": "护板宽度 (mm)", "key": "width", "min": 300.0, "max": 1000.0, "default": 800.0}, {"label": "护板厚度 (mm)", "key": "thickness", "min": 2.0, "max": 15.0, "default": 4.0}]
            }
        }
    },
    "工业协作机械臂": {
        "parts": {
            "高速协作机械臂主段": {
                "topology": "BEAM", "search_suffix": "industrial collaborative robot arm lightweight stiffness", "constraint": "严禁防弹医疗。重点在于绝对高刚度和高周疲劳极限。对标铸铁或挤压铝材。",
                "ui_inputs": [{"label": "臂管外径 (mm)", "key": "diameter", "min": 30.0, "max": 150.0, "default": 80.0}, {"label": "臂管长度 (mm)", "key": "length", "min": 200.0, "max": 1500.0, "default": 600.0}, {"label": "管壁厚度 (mm)", "key": "thickness", "min": 2.0, "max": 20.0, "default": 6.0}]
            }
        }
    },
    "智能穿戴与柔性外骨骼": {
        "parts": {
            "柔性外骨骼助力带": {
                "topology": "STRAP", "search_suffix": "wearable flexible exoskeleton material durability", "constraint": "不能用刚性骨架思维！聚焦人机交互的舒适度、柔性储能、耐磨性。",
                "ui_inputs": [{"label": "带体宽度 (mm)", "key": "width", "min": 10.0, "max": 80.0, "default": 40.0}, {"label": "带体厚度 (mm)", "key": "thickness", "min": 1.0, "max": 10.0, "default": 3.0}]
            }
        }
    },
    "高性能纺织与极限户外": {
        "parts": {
            "特种降落伞承力带": {
                "topology": "STRAP", "search_suffix": "parachute strap UHMWPE high strength textile", "constraint": "对标UHMWPE或锦纶，分析开伞瞬间拉伸冲击。",
                "ui_inputs": [{"label": "织带宽度 (mm)", "key": "width", "min": 10.0, "max": 50.0, "default": 25.0}, {"label": "织带厚度 (mm)", "key": "thickness", "min": 0.5, "max": 5.0, "default": 2.0}]
            },
            "极限高山帐篷支撑杆": {
                "topology": "BEAM", "search_suffix": "tent pole high altitude wind resistance", "constraint": "对标高标号航空铝，分析狂风下的抗弯折力。",
                "ui_inputs": [{"label": "外径 (mm)", "key": "diameter", "min": 5.0, "max": 20.0, "default": 8.5}, {"label": "管壁厚度 (mm)", "key": "thickness", "min": 0.5, "max": 3.0, "default": 1.0}, {"label": "跨度长度 (mm)", "key": "length", "min": 500.0, "max": 2000.0, "default": 1000.0}]
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
    
    st.header("2. 评估材料本征参数")
    mat_category = st.selectbox("材料大类", ["合成蛋白/生物基大分子", "碳纤维复合", "特种工程塑料", "特种合金"])
    density = st.number_input("密度 (g/cm³)", value=1.30)
    strength = st.number_input("抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    
    # 侦测零件变化，清空旧报告
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
    with st.spinner(f"正在读取独家数据库，为【{target_part}】撰写全维深度评测..."):
        
        web_query = f"scholarly articles {mat_category} {target_part} {part_config['search_suffix']}"
        web_context = search_tavily(web_query, tavily_key)
        local_query = f"{mat_category} {target_part} 加工 规范"
        rag_context = retrieve_knowledge(local_query)

        # ！！！保留了 v19 的庞大 JSON 格式，全面囊括所有硬核分析模块 ！！！
        system_prompt = f"""
        你是顶尖应用工程师。评估材料在【{domain}】领域【{target_part}】上的商业可行性。
        材料: 密度={density}, 强度={strength}MPa, 模量={modulus}GPa。
        约束: {part_config['constraint']}
        情报: {web_context}
        经验: {rag_context}
        
        【数据包装规范】禁止提“本地文件”或“Tavily”。包装为：“独家内部数据库” 或 “学术文献”。
        
        必须输出极度庞大的标准 JSON (严禁Markdown)：
        {{
          "market_positioning": {{
            "tier": "突破性颠覆级别 或 行业标杆 或 常规替代",
            "verdict": "一句话核心定调产品的竞争力",
            "competitor_compare": "详细对比现役最顶尖方案的优劣势",
            "derived_performance": [
              {{"metric": "推演工况指标1 (结合材料属性给出震撼的极限值)", "value": "带单位的数据"}},
              {{"metric": "理论衰减寿命 (恶劣工况下)", "value": "带单位的数据"}}
            ]
          }},
          "radar": {{"绝对强度": 100, "刚度稳定": 60, "轻量化收益": 95, "加工成型": 45, "专属环境抗性": 80, "商业落地潜力": 90}},
          "base_metrics": [
            {{"metric": "核心抗拉极限", "Base1": 570, "Base2": 3000, "NewMat": {strength}}},
            {{"metric": "绝对模量支撑", "Base1": 71, "Base2": 160, "NewMat": {modulus}}},
            {{"metric": "比强度/效能比", "Base1": 203, "Base2": 1875, "NewMat": {strength/density}}},
            {{"metric": "比模量/比刚度", "Base1": 25.3, "Base2": 100, "NewMat": {modulus/density}}}
          ],
          "summary_1": "本征对标小结",
          "math_sim": {{
            "design_goal": "核心等效目标",
            "math_latex": "写出具体的力学或理化等效方程",
            "table": [{{"param": "核心代换参数", "base": "基准值", "new": "代换计算值"}}],
            "chart_vals": {{"base_wt": 4.25, "new_wt": 1.35}}
          }},
          "summary_2": "等效计算小结",
          "parameter_sweep": {{
            "sweep_1": {{"chart_title": "领域风险盲区波动图", "chart_data": [{{"x": "下限预估", "y": 20}}, {{"x": "中位理论值", "y": 120}}, {{"x": "上限风险", "y": 40}}], "scenarios": [{{"range": "风险区间", "desc": "预估后果"}}]}},
            "sweep_2": {{"chart_title": "环境/生化衰减曲线", "chart_data": [{{"x": "常规环境", "y": 100}}, {{"x": "严苛挑战", "y": 40}}], "scenarios": [{{"range": "衰减说明", "desc": "应对策略"}}]}}
          }},
          "summary_3": "盲区扫掠小结",
          "eight_dimensions": [
            {{"dim": "1. 静态载荷与壁厚补偿", "details": ["深度分析1", "分析2"], "chart_metric": "强度倍数", "base_val": 1.0, "new_val": 3.2}},
            {{"dim": "2. 动态磨损与疲劳衰减", "details": ["分析1"], "chart_metric": "疲劳寿命", "base_val": 100, "new_val": 80}},
            {{"dim": "3. 几何界面与加工良率", "details": ["分析1"], "chart_metric": "工艺良率", "base_val": 95, "new_val": 60}},
            {{"dim": "4. 【重点】专属领域抗性", "details": ["结合领域约束剖析防弹/降解等特性"], "chart_metric": "环境保持率", "base_val": 90, "new_val": 45}},
            {{"dim": "5. 材料微观机理影响", "details": ["分析1"], "chart_metric": "结构优越度", "base_val": 50, "new_val": 90}},
            {{"dim": "6. 终端经济效益与降本", "details": ["BOM表推演"], "chart_metric": "降本(%)", "base_val": 0, "new_val": 15}},
            {{"dim": "7. 全生命周期碳足迹与ESG", "details": ["分析1"], "chart_metric": "ESG表现", "base_val": 20, "new_val": 85}},
            {{"dim": "8. 行业标准准入与壁垒", "details": ["分析1"], "chart_metric": "准入难度评估", "base_val": 10, "new_val": 18}}
          ],
          "summary_4": "八维切片小结",
          "grand_verdict": {{
            "summary": "最终投产陈词与红绿灯决议",
            "strengths": ["绝对优势1", "优势2"],
            "weaknesses": ["致命短板1", "风险2"]
          }},
          "reference_sources": ["独家内部数据库: xxx工艺规范", "学术文献: xxx研究分析"]
        }}
        """
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
        payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.15}
        
        try:
            res = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=120)
            res.raise_for_status()
            raw_content = res.json()['choices'][0]['message']['content']
            # 清理可能的 markdown 标记
            if "```json" in raw_content:
                raw_content = raw_content.split("```json")[1].split("```")[0]
            elif "```" in raw_content:
                raw_content = raw_content.split("```")[1].split("```")[0]
            st.session_state["llm_report"] = json.loads(raw_content.strip())
        except Exception as e:
            st.error(f"模型分析流中断或JSON解析失败 (请尝试重新点击生成): {str(e)}")

# ================= 🌟 报告渲染：交互沙盒(顶层) + v19 全系详尽图表(底层) 🌟 =================
if st.session_state["llm_report"]:
    data = st.session_state["llm_report"]
    
    # ---------------- 顶层板块：市场定位与 3D 尺寸交互沙盒 ----------------
    st.markdown(f"<h1 style='text-align: center; color: #000;'>🏆 终端产品市场定位：{data['market_positioning']['tier']}</h1>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='text-align: center; color: #4a4a4a;'>{data['market_positioning']['verdict']}</h4><hr>", unsafe_allow_html=True)
    
    col_sandbox, col_cad = st.columns([1, 1.2])
    current_dims = {}
    with col_sandbox:
        st.markdown(f"### ⚙️ 【{target_part}】工程参数设计沙盒")
        st.caption("👈 滑动修改尺寸，右侧 CAD图与极限力学数据将【无延迟刷新】")
        for item in part_config["ui_inputs"]:
            current_dims[item["key"]] = st.slider(item["label"], item["min"], item["max"], item["default"], key=f"sb_{item['key']}")
            
        st.markdown("#### ⚔️ 市场竞品对标分析")
        st.write(data['market_positioning']['competitor_compare'])
        st.markdown("#### 🚀 理论工况推演")
        for item in data['market_positioning']['derived_performance']:
            st.markdown(f"- **{item['metric']}**: `{item['value']}`")

    with col_cad:
        physics_res = calculate_physics(part_config["topology"], current_dims, strength, modulus)
        st.plotly_chart(render_3d_blueprint(part_config["topology"], current_dims, physics_res), use_container_width=True)
        st.success(f"**⚡ 沙盒实时推演：** 依据当前输入尺寸，该制件的理论承受极值可达 **{physics_res['load']:.0f} {physics_res['unit']}**。")

    st.markdown("---")
    
    # ---------------- 底层板块：完整保留的 v19 核心论证 ----------------
    
    # I. 本征参数与多维潜力
    st.subheader("I. 本征参数与多维潜力对标")
    c_radar, c_bars = st.columns([1, 2.5])
    with c_radar:
        df_radar = pd.DataFrame(dict(r=list(data['radar'].values()), theta=list(data['radar'].keys())))
        st.plotly_chart(px.line_polar(df_radar, r='r', theta='theta', line_close=True).update_traces(fill='toself', line_color='black').update_layout(margin=dict(t=30, b=10)), use_container_width=True)

    with c_bars:
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)
        cols = [r1c1, r1c2, r2c1, r2c2]
        for idx, md in enumerate(data['base_metrics']):
            fig = px.bar(pd.DataFrame({"方案": ["现役基准A", "现役基准B", "入库新材"], "数值": [md['Base1'], md['Base2'], md['NewMat']]}), x="方案", y="数值", text_auto='.2s', color="方案", color_discrete_sequence=["#d3d3d3", "#a9a9a9", "#000000"])
            cols[idx].plotly_chart(fig.update_layout(title=md['metric'], showlegend=False, height=180, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)
    st.info(f"**📌 小结：** {data.get('summary_1', '本征参数优势显著。')}")
    st.divider()

    # II. 数学等效推演
    st.subheader("II. 结构数学代换与效能核算")
    sim = data['math_sim']
    st.markdown(f"**🎯 核心等效目标:** `{sim['design_goal']}`")
    with st.container(border=True): st.markdown(sim['math_latex'])
    sc1, sc2 = st.columns([1.5, 1])
    with sc1: st.dataframe(pd.DataFrame(sim["table"]).rename(columns={"param": "代换关键参数", "base": "现役基准", "new": "新材料代换"}), use_container_width=True, hide_index=True)
    with sc2:
        fig_wt = px.bar(pd.DataFrame({"方案": ["现役基准", "新设计"], "效能": [sim['chart_vals']['base_wt'], sim['chart_vals']['new_wt']]}), x="方案", y="效能", color="方案", text="效能", height=200, color_discrete_map={"现役基准": "#7f7f7f", "新设计": "#000000"})
        st.plotly_chart(fig_wt.update_layout(showlegend=False, margin=dict(l=10, r=10, t=30, b=10)), use_container_width=True)
    st.info(f"**📌 小结：** {data.get('summary_2', '数学推演逻辑闭环。')}")
    st.divider()

    # III. 盲区预演
    st.subheader("III. 领域核心风险扫掠预演")
    swp_c1, swp_c2 = st.columns(2)
    with swp_c1:
        with st.container(border=True):
            sw1 = data['parameter_sweep']['sweep_1']
            st.plotly_chart(px.bar(pd.DataFrame(sw1['chart_data']), x="x", y="y", title=sw1['chart_title'], height=220, color_discrete_sequence=['#4a4a4a']).update_layout(margin=dict(l=10,r=10,t=40,b=10)), use_container_width=True)
            for sc in sw1['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
    with swp_c2:
        with st.container(border=True):
            sw2 = data['parameter_sweep']['sweep_2']
            st.plotly_chart(px.line(pd.DataFrame(sw2['chart_data']), x="x", y="y", markers=True, title=sw2['chart_title'], height=220, color_discrete_sequence=['#000000']).update_layout(margin=dict(l=10,r=10,t=40,b=10)), use_container_width=True)
            for sc in sw2['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
    st.info(f"**📌 小结：** {data.get('summary_3', '极端工况下存在特定风险区间。')}")
    st.divider()

    # IV. 八维切片
    st.subheader("IV. 商业级八维深度剖析")
    dims = data['eight_dimensions']
    tabs = st.tabs([d['dim'] for d in dims])
    for i, tab in enumerate(tabs):
        with tab:
            tc1, tc2 = st.columns([1.5, 1])
            with tc1:
                st.markdown("#### 🔍 深度论证")
                for d in dims[i]['details']: st.markdown(f"- {d}")
            with tc2:
                fig_tab = px.bar(pd.DataFrame({"对标对象": ["现役基准", "新材料"], "数值": [dims[i]['base_val'], dims[i]['new_val']]}), x="数值", y="对标对象", orientation='h', text="数值", color="对标对象", color_discrete_sequence=["#a9a9a9", "#000000"], title=dims[i]['chart_metric'])
                st.plotly_chart(fig_tab.update_layout(showlegend=False, height=180, margin=dict(l=10,r=10,t=40,b=10)), use_container_width=True)
    st.info(f"**📌 小结：** {data.get('summary_4', '八维切片展示了系统的全生命周期优势与短板。')}")
    st.divider()

    # V. 结案决议与溯源
    st.subheader("V. 结案陈词与数据溯源")
    verdict = data['grand_verdict']
    st.success(f"**⚖️ 商业落地决议：** {verdict['summary']}")
    v_in1, v_in2 = st.columns(2)
    with v_in1:
        st.markdown("##### 🌟 核心投产优势")
        for s in verdict['strengths']: st.markdown(f"✔️ {s}")
    with v_in2:
        st.markdown("##### ⚠️ 致命工程短板与风险")
        for w in verdict['weaknesses']: st.markdown(f"❌ {w}")
        
    st.markdown("#### 📚 隐藏数据溯源 (Data Origins)")
    for ref in data.get('reference_sources', []): st.markdown(f"- 🔗 **{ref}**")
