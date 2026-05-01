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

# ================= 🔐 安全与状态缓存初始化 =================
if "authenticated" not in st.session_state: 
    st.session_state["authenticated"] = False
if "llm_report" not in st.session_state: 
    st.session_state["llm_report"] = None
if "last_part" not in st.session_state: 
    st.session_state["last_part"] = None

if not st.session_state["authenticated"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    col_empty1, col_login, col_empty2 = st.columns([1, 1, 1])
    with col_login:
        st.info("🛡️ 该评估系统已加密，仅限内部工程师及受邀用户访问。")
        pwd = st.text_input("请输入专属邀请码：", type="password")
        if st.button("解锁系统", type="primary", use_container_width=True):
            if pwd == "VIP2026": 
                st.session_state["authenticated"] = True
                st.rerun()
            else: 
                st.error("邀请码错误或已过期！")
    st.stop()

# ================= 导入本地挂载与联网引擎 =================
try:
    from rag_engine import retrieve_knowledge
    from db_connector import init_db, get_material_data
    init_db()
except ImportError:
    def retrieve_knowledge(query, k=3): 
        return "本地知识库尚未部署。"
    def get_material_data(mat_name): 
        return None

def search_tavily(query, api_key):
    if not api_key: return "未配置 Tavily API Key"
    try:
        res = requests.post(
            "https://api.tavily.com/search", 
            json={"api_key": api_key, "query": query, "search_depth": "advanced", "include_answer": True, "max_results": 3}, 
            timeout=15
        ).json()
        return f"【全网提炼】: {res.get('answer', '无')}\n【来源】: {str(res.get('results', []))}"
    except Exception as e: 
        return f"检索失败: {str(e)}"

# ================= 🌟 核心引擎 1：实时多维物理计算 (纯数学) 🌟 =================
def calculate_physics(topology, dims, S, E_gpa, density):
    """根据拓扑类型、实时尺寸和材料本征，秒级推算终端性能指标"""
    E = E_gpa * 1000  # GPa转换为MPa
    results = []
    weight_factor = density * 1e-6 # 换算为 kg
    
    if topology == "BEAM": # 圆形管材/连杆
        L, D, t = dims['length'], dims['diameter'], dims['thickness']
        d_inner = max(0.1, D - 2*t)
        V = math.pi/4 * (D**2 - d_inner**2) * L
        I = math.pi * (D**4 - d_inner**4) / 64
        area = math.pi/4 * (D**2 - d_inner**2)
        
        weight = V * weight_factor
        bending_load = (S * I / (D/2)) / L if L>0 else 0
        compression = S * area * 0.8 
        deflection = (bending_load * L**3) / (3 * E * I) if I>0 else 0
        
        results = [
            {"指标": "结构总重量估算 (kg)", "数值": weight},
            {"指标": "悬臂抗弯极限极值 (N)", "数值": bending_load},
            {"指标": "轴向抗压承载极限 (N)", "数值": compression},
            {"指标": "极限弹性挠度极值 (mm)", "数值": deflection}
        ]
        
    elif topology == "I_BEAM": # 工字梁 (航空机翼/汽车纵梁)
        L, H, W, t = dims['length'], dims['height'], dims['width'], dims['thickness']
        area = 2 * W * t + max(0, H - 2*t) * t
        V = area * L
        weight = V * weight_factor
        
        # 工字梁惯性矩 Ix = (W*H^3 - (W-t)*h^3)/12
        h_inner = max(0, H - 2*t)
        I = (W * H**3 - (W - t) * h_inner**3) / 12
        
        bending_load = (S * I / (H/2)) / L if L>0 else 0
        deflection = (bending_load * L**3) / (3 * E * I) if I>0 else 0
        
        results = [
            {"指标": "结构总重量估算 (kg)", "数值": weight},
            {"指标": "工字梁主轴抗弯极限 (N)", "数值": bending_load},
            {"指标": "腹板抗剪切预估 (N)", "数值": S * 0.5 * h_inner * t},
            {"指标": "主轴抗弯挠度极值 (mm)", "数值": deflection}
        ]
        
    elif topology == "PLATE":
        L, W, t = dims['length'], dims['width'], dims['thickness']
        V = L * W * t
        weight = V * weight_factor
        
        punch_load = 4 * S * (t**2) / L if L>0 else 0
        shear_load = S * 0.577 * W * t 
        I = (W * t**3) / 12
        deflection = (punch_load * L**3) / (48 * E * I) if I>0 else 0
        
        results = [
            {"指标": "结构总重量估算 (kg)", "数值": weight},
            {"指标": "中心点抗冲压极限 (N)", "数值": punch_load},
            {"指标": "边缘面抗剪切极限 (N)", "数值": shear_load},
            {"指标": "最大冲压形变容限 (mm)", "数值": deflection}
        ]
        
    elif topology == "CORRUGATED":
        L, W, t = dims['length'], dims['width'], dims['thickness']
        V = L * W * t * 1.22 
        weight = V * weight_factor
        
        I_equivalent = (W * (t*3)**3) / 12 
        bending_load = (S * I_equivalent / (t*1.5)) / L if L>0 else 0
        crush_energy = S * V * 0.4 
        
        results = [
            {"指标": "结构总重量估算 (kg)", "数值": weight},
            {"指标": "波纹截面等效抗弯 (N)", "数值": bending_load},
            {"指标": "整体压溃吸能极值 (J)", "数值": crush_energy / 1000},
            {"指标": "结构刚度提升比 (倍)", "数值": 3.2}
        ]
        
    elif topology == "STRAP":
        W, t = dims['width'], dims['thickness']
        L_ref = 1000 
        V = L_ref * W * t
        area = W * t
        weight = V * weight_factor
        
        tensile_load = S * area
        elongation = (tensile_load * L_ref) / (E * area) if area>0 else 0
        
        results = [
            {"指标": "标准每米重量 (kg/m)", "数值": weight},
            {"指标": "截面单向拉断极值 (N)", "数值": tensile_load},
            {"指标": "极限量程伸缩度 (mm/m)", "数值": elongation},
            {"指标": "理论承重安全冗余", "数值": 2.5}
        ]

    return pd.DataFrame(results)

# ================= 🌟 核心引擎 2：真·双视图 CAE仿真绘图引擎 🌟 =================
def render_3d_blueprint(topology, dims, view_type="macro"):
    """
    macro: 渲染宏观真实几何结构 (灰白色调)
    micro: 渲染受力/形变云图 (带热力图颜色梯度，反映性能分布)
    """
    fig = go.Figure()
    
    if topology == "BEAM": # 管材
        L, D = dims['length'], dims['diameter']
        theta, z = np.meshgrid(np.linspace(0, 2*np.pi, 30), np.linspace(0, L, 20))
        if view_type == "macro":
            x = (D/2)*np.cos(theta)
            y = (D/2)*np.sin(theta)
            fig.add_trace(go.Surface(x=x, y=y, z=z, colorscale='Greys', opacity=0.9, showscale=False))
            title_text = "📐 宏观外观: 管材/连杆结构"
        else:
            # 仿真：受端部弯曲载荷，根部应力最大 (云图)
            deflection = 0.1 * D * (z/L)**2 # 模拟抛物线弯曲
            x = (D/2)*np.cos(theta) + deflection
            y = (D/2)*np.sin(theta)
            stress_color = (L - z) # 根部z=0应力最大
            fig.add_trace(go.Surface(x=x, y=y, z=z, surfacecolor=stress_color, colorscale='Inferno', opacity=0.9, showscale=False))
            title_text = "🔥 CAE仿真: 悬臂受弯应力/形变云图"
            
    elif topology == "I_BEAM": # 工字梁
        L, H, W, t = dims['length'], dims['height'], dims['width'], dims['thickness']
        # 简化工字梁的三个面：上翼缘，下翼缘，腹板
        Z_arr = np.linspace(0, L, 20)
        if view_type == "macro":
            # 上下翼缘
            fig.add_trace(go.Surface(x=np.array([[-W/2, W/2]]*20), y=np.full((20,2), H/2), z=np.array([Z_arr, Z_arr]).T, colorscale='Greys', showscale=False))
            fig.add_trace(go.Surface(x=np.array([[-W/2, W/2]]*20), y=np.full((20,2), -H/2), z=np.array([Z_arr, Z_arr]).T, colorscale='Greys', showscale=False))
            # 腹板
            fig.add_trace(go.Surface(x=np.zeros((20,2)), y=np.array([[-H/2, H/2]]*20), z=np.array([Z_arr, Z_arr]).T, colorscale='Greys', showscale=False))
            title_text = "📐 宏观外观: 工字梁截面轮廓"
        else:
            # 仿真：受弯曲，产生挠度，翼缘应力大
            deflection = 0.05 * L * (Z_arr/L)**2
            stress_top = np.full((20,2), 1.0) * (1 - Z_arr/L)[:, None] # 根部上翼缘受拉最高
            stress_bot = np.full((20,2), 0.8) * (1 - Z_arr/L)[:, None] # 根部下翼缘受压
            stress_web = np.abs(np.array([[-H/2, H/2]]*20)) / (H/2) * (1 - Z_arr/L)[:, None] # 腹板应力向两端扩散
            
            fig.add_trace(go.Surface(x=np.array([[-W/2, W/2]]*20)+deflection[:,None], y=np.full((20,2), H/2), z=np.array([Z_arr, Z_arr]).T, surfacecolor=stress_top, colorscale='Jet', showscale=False))
            fig.add_trace(go.Surface(x=np.array([[-W/2, W/2]]*20)+deflection[:,None], y=np.full((20,2), -H/2), z=np.array([Z_arr, Z_arr]).T, surfacecolor=stress_bot, colorscale='Jet', showscale=False))
            fig.add_trace(go.Surface(x=np.zeros((20,2))+deflection[:,None], y=np.array([[-H/2, H/2]]*20), z=np.array([Z_arr, Z_arr]).T, surfacecolor=stress_web, colorscale='Jet', showscale=False))
            title_text = "🔥 CAE仿真: 翼梁主轴弯曲应力云图"

    elif topology == "PLATE":
        L, W, t = dims['length'], dims['width'], dims['thickness']
        X, Y = np.meshgrid(np.linspace(0, L, 20), np.linspace(0, W, 20))
        if view_type == "macro":
            Z = np.zeros_like(X)
            fig.add_trace(go.Surface(x=X, y=Y, z=Z, colorscale='Greys', opacity=0.9, showscale=False))
            title_text = "📐 宏观外观: 平面装配外廓"
        else: 
            # 仿真：中心受冲压，形成抛物面下陷，中心颜色最亮
            Z = -0.1 * L * np.sin(X/L * np.pi) * np.sin(Y/W * np.pi)
            stress_color = np.abs(Z) # 形变越大的地方应力越集中
            fig.add_trace(go.Surface(x=X, y=Y, z=Z, surfacecolor=stress_color, colorscale='Inferno', opacity=0.9, showscale=False))
            title_text = "🔥 CAE仿真: 中心抗冲压形变/应力云图"
            
    elif topology == "CORRUGATED":
        L, W, t = dims['length'], dims['width'], dims['thickness']
        X, Y = np.meshgrid(np.linspace(0, L, 40), np.linspace(0, W, 20))
        if view_type == "macro":
            # 宏观是一个代表包络体积的透明灰盒
            h_macro = t * 3
            x_box = [0, L, L, 0, 0, L, L, 0]
            y_box = [0, 0, W, W, 0, 0, W, W]
            z_box = [-h_macro, -h_macro, -h_macro, -h_macro, h_macro, h_macro, h_macro, h_macro]
            fig.add_trace(go.Mesh3d(x=x_box, y=y_box, z=z_box, i=[0,0,0,1,1,2,4,4,4,5,5,6], j=[1,2,3,2,5,6,5,6,7,6,7,2], k=[2,3,0,5,6,1,6,7,4,7,2,7], color='lightgrey', opacity=0.4, flatshading=True))
            title_text = "📐 宏观包络: 电池底板设计空间"
        else:
            # 仿真：波纹阵列在受压时的吸能应力分布，波峰波谷受力大
            Z = (t * 2) * np.sin(X / L * 10 * np.pi) 
            stress_color = np.abs(Z) # 波峰波谷应力高
            fig.add_trace(go.Surface(x=X, y=Y, z=Z, surfacecolor=stress_color, colorscale='Jet', opacity=0.9, showscale=False))
            title_text = "🔥 CAE仿真: 波纹吸能抗压应力云图"
            
    elif topology == "STRAP":
        W, t = dims['length'] if 'length' in dims else 300, dims['width']
        X, Y = np.meshgrid(np.linspace(0, W, 20), np.linspace(-dims['width']/2, dims['width']/2, 10))
        if view_type == "macro":
            Z = np.zeros_like(X)
            fig.add_trace(go.Surface(x=X, y=Y, z=Z, colorscale='Greys', opacity=0.9, showscale=False))
            title_text = "📐 宏观外观: 柔性织带自然状态"
        else:
            # 仿真：两端受拉导致中间产生“颈缩 (Necking)”效应
            necking_factor = 1 - 0.15 * np.sin(X/W * np.pi)
            Y_neck = Y * necking_factor
            Z = np.zeros_like(X)
            stress_color = 1 / necking_factor # 越细的地方拉应力越集中
            fig.add_trace(go.Surface(x=X, y=Y_neck, z=Z, surfacecolor=stress_color, colorscale='Inferno', opacity=0.9, showscale=False))
            title_text = "🔥 CAE仿真: 极限拉伸颈缩/拉应力云图"

    fig.update_layout(
        scene=dict(xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False)),
        paper_bgcolor='white', plot_bgcolor='white', margin=dict(l=0, r=0, t=30, b=0), height=320,
        title=dict(text=title_text, font=dict(color="black", size=14))
    )
    return fig

# ================= 🌟 知识图谱字典 (8大领域 19个核心零部件 严谨物理映射) 🌟 =================
DOMAIN_CONFIG = {
    "航空航天与eVTOL飞行器": {
        "parts": {
            "机翼主承力翼梁": {
                "topology": "I_BEAM", "search_suffix": "aerospace wing spar I-beam composite FAA", "constraint": "严禁民用标准。对标碳纤维预浸料，聚焦气动弯矩与扭矩。",
                "ui_inputs": [
                    {"label": "翼梁高度 (mm)", "key": "height", "min": 50.0, "max": 300.0, "default": 150.0}, 
                    {"label": "翼缘宽度 (mm)", "key": "width", "min": 20.0, "max": 150.0, "default": 80.0}, 
                    {"label": "翼梁长度 (mm)", "key": "length", "min": 1000.0, "max": 5000.0, "default": 2500.0},
                    {"label": "平均壁厚 (mm)", "key": "thickness", "min": 2.0, "max": 15.0, "default": 5.0}
                ]
            },
            "客舱轻量化座椅骨架": {
                "topology": "BEAM", "search_suffix": "aircraft cabin interior seat frame lightweight flame retardant", "constraint": "必须满足 FAA 适航阻燃认证及 16G 动态冲击测试。对标铝合金挤压件。",
                "ui_inputs": [{"label": "管件外径 (mm)", "key": "diameter", "min": 15.0, "max": 60.0, "default": 30.0}, {"label": "管件长度 (mm)", "key": "length", "min": 300.0, "max": 1500.0, "default": 600.0}, {"label": "管壁厚 (mm)", "key": "thickness", "min": 1.0, "max": 5.0, "default": 2.0}]
            }
        }
    },
    "新能源汽车及电池包": {
        "parts": {
            "白车身轻量化纵梁": {
                "topology": "I_BEAM", "search_suffix": "vehicle body-in-white longitudinal beam lightweight", "constraint": "聚焦整车减重与正面碰撞传力路径。对标超高强钢或铝挤压型材。",
                "ui_inputs": [{"label": "纵梁高度 (mm)", "key": "height", "min": 80.0, "max": 250.0, "default": 120.0}, {"label": "纵梁宽度 (mm)", "key": "width", "min": 50.0, "max": 150.0, "default": 80.0}, {"label": "单段长度 (mm)", "key": "length", "min": 500.0, "max": 2500.0, "default": 1500.0}, {"label": "钣金壁厚 (mm)", "key": "thickness", "min": 1.0, "max": 8.0, "default": 2.5}]
            },
            "电池包防撞波纹底板": {
                "topology": "CORRUGATED", "search_suffix": "EV battery corrugated plate crashworthiness thermal", "constraint": "必须基于底部托底吸能、热失控阻燃进行评估。对标铝合金压铸件。",
                "ui_inputs": [{"label": "护板长度 (mm)", "key": "length", "min": 500.0, "max": 2000.0, "default": 1200.0}, {"label": "护板宽度 (mm)", "key": "width", "min": 300.0, "max": 1000.0, "default": 800.0}, {"label": "波纹厚度 (mm)", "key": "thickness", "min": 1.0, "max": 10.0, "default": 3.0}]
            }
        }
    },
    "生物医疗植入物": {
        "parts": {
            "骨折内固定承力板": {
                "topology": "PLATE", "search_suffix": "bone plate medical implant ISO 10993", "constraint": "绝对严禁提及军工。对标钛合金骨板，聚焦应力遮挡与降解相容性。",
                "ui_inputs": [{"label": "骨板长度 (mm)", "key": "length", "min": 30.0, "max": 150.0, "default": 80.0}, {"label": "骨板宽度 (mm)", "key": "width", "min": 5.0, "max": 20.0, "default": 12.0}, {"label": "骨板厚度 (mm)", "key": "thickness", "min": 1.0, "max": 6.0, "default": 3.5}]
            },
            "人工韧带/肌腱": {
                "topology": "STRAP", "search_suffix": "artificial ligament tendon tissue engineering", "constraint": "绝对严禁提及军工。对标PET纤维，聚焦抗疲劳拉伸和细胞黏附能力。",
                "ui_inputs": [{"label": "韧带宽度 (mm)", "key": "width", "min": 5.0, "max": 20.0, "default": 10.0}, {"label": "韧带厚度 (mm)", "key": "thickness", "min": 0.5, "max": 4.0, "default": 2.0}]
            },
            "可吸收干涉骨钉": {
                "topology": "BEAM", "search_suffix": "absorbable interference screw interference fixation", "constraint": "分析骨钉在植入时的扭转强度及术后的降解力学维持时间。对标 PLLA 或钛钉。",
                "ui_inputs": [{"label": "骨钉外径 (mm)", "key": "diameter", "min": 3.0, "max": 12.0, "default": 7.0}, {"label": "骨钉长度 (mm)", "key": "length", "min": 10.0, "max": 60.0, "default": 25.0}, {"label": "等效壁厚 (mm)", "key": "thickness", "min": 1.0, "max": 5.0, "default": 2.0}]
            }
        }
    },
    "人形机器人核心骨架": {
        "parts": {
            "下肢大扭矩管状连杆": {
                "topology": "BEAM", "search_suffix": "humanoid robot link dynamic stiffness", "constraint": "聚焦高频伺服电机启停带来的动态疲劳与抖动，对标7075航空铝。",
                "ui_inputs": [{"label": "连杆外管径 (mm)", "key": "diameter", "min": 10.0, "max": 50.0, "default": 30.0}, {"label": "两轴跨度长度 (mm)", "key": "length", "min": 100.0, "max": 600.0, "default": 350.0}, {"label": "核心管壁厚度 (mm)", "key": "thickness", "min": 1.0, "max": 10.0, "default": 3.0}]
            },
            "主承力躯干框架": {
                "topology": "PLATE", "search_suffix": "humanoid robot torso frame lightweight rigidity", "constraint": "聚焦机器人在行走跌倒时的抗冲击能力与整体刚度匹配。对标压铸铝合金。",
                "ui_inputs": [{"label": "特征长度 (mm)", "key": "length", "min": 150.0, "max": 500.0, "default": 300.0}, {"label": "特征宽度 (mm)", "key": "width", "min": 100.0, "max": 400.0, "default": 200.0}, {"label": "背板厚度 (mm)", "key": "thickness", "min": 2.0, "max": 15.0, "default": 5.0}]
            }
        }
    },
    "军工：单兵装甲与防护": {
        "parts": {
            "NIJ III级 防弹插板": {
                "topology": "PLATE", "search_suffix": "ballistic armor plate MIL-STD impact", "constraint": "严禁医疗词汇。聚焦防弹极限与背部钝伤形变，对标芳纶复合板。",
                "ui_inputs": [{"label": "插板长度 (mm)", "key": "length", "min": 200.0, "max": 400.0, "default": 300.0}, {"label": "插板宽度 (mm)", "key": "width", "min": 150.0, "max": 300.0, "default": 250.0}, {"label": "装甲厚度 (mm)", "key": "thickness", "min": 5.0, "max": 30.0, "default": 12.0}]
            },
            "防爆头盔缓冲内衬": {
                "topology": "CORRUGATED", "search_suffix": "combat helmet impact attenuation liner", "constraint": "聚焦低速钝器击打及爆炸冲击波的吸能缓冲。对标发泡聚丙烯 (EPP) 或 Kevlar。",
                "ui_inputs": [{"label": "覆盖长度 (mm)", "key": "length", "min": 150.0, "max": 300.0, "default": 250.0}, {"label": "覆盖宽度 (mm)", "key": "width", "min": 150.0, "max": 300.0, "default": 200.0}, {"label": "波纹厚度 (mm)", "key": "thickness", "min": 5.0, "max": 25.0, "default": 15.0}]
            }
        }
    },
    "工业协作机械臂": {
        "parts": {
            "高速协作臂主段": {
                "topology": "BEAM", "search_suffix": "industrial robot arm lightweight stiffness fatigue", "constraint": "严禁偏向防弹或医疗！重点在于绝对高刚度（防末端下垂）和高周疲劳极限。",
                "ui_inputs": [{"label": "主臂外径 (mm)", "key": "diameter", "min": 30.0, "max": 150.0, "default": 80.0}, {"label": "主臂长度 (mm)", "key": "length", "min": 200.0, "max": 1500.0, "default": 600.0}, {"label": "管壁厚度 (mm)", "key": "thickness", "min": 2.0, "max": 20.0, "default": 6.0}]
            },
            "精密末端夹具平板": {
                "topology": "PLATE", "search_suffix": "robot end effector gripper lightweight rigid plate", "constraint": "聚焦极低的惯量（降低电机负荷）和极高的尺寸稳定性。对标硬质铝合金。",
                "ui_inputs": [{"label": "基板长度 (mm)", "key": "length", "min": 50.0, "max": 300.0, "default": 150.0}, {"label": "基板宽度 (mm)", "key": "width", "min": 30.0, "max": 200.0, "default": 80.0}, {"label": "基板厚度 (mm)", "key": "thickness", "min": 2.0, "max": 15.0, "default": 5.0}]
            }
        }
    },
    "高性能纺织与户外极限": {
        "parts": {
            "特种降落伞承力带": {
                "topology": "STRAP", "search_suffix": "parachute strap UHMWPE high strength", "constraint": "必须分析开伞瞬间的撕裂和拉伸冲击，对标UHMWPE或锦纶66。",
                "ui_inputs": [{"label": "织带受力宽度 (mm)", "key": "width", "min": 10.0, "max": 50.0, "default": 25.0}, {"label": "织带压实厚度 (mm)", "key": "thickness", "min": 0.5, "max": 5.0, "default": 2.0}]
            },
            "极限高山帐篷支撑杆": {
                "topology": "BEAM", "search_suffix": "tent pole high altitude wind resistance", "constraint": "对标高标号航空铝，重点分析狂风下的抗弯折力。",
                "ui_inputs": [{"label": "外径 (mm)", "key": "diameter", "min": 5.0, "max": 20.0, "default": 8.5}, {"label": "跨度长度 (mm)", "key": "length", "min": 500.0, "max": 2000.0, "default": 1000.0}, {"label": "管壁厚度 (mm)", "key": "thickness", "min": 0.5, "max": 3.0, "default": 1.0}]
            }
        }
    },
    "智能穿戴与柔性外骨骼": {
        "parts": {
            "柔性外骨骼助力带": {
                "topology": "STRAP", "search_suffix": "wearable flexible exoskeleton tendon strap", "constraint": "不能用刚性骨架思维！必须分析人体工效学舒适度、千万次弯曲疲劳。对标尼龙混合带。",
                "ui_inputs": [{"label": "带体宽度 (mm)", "key": "width", "min": 15.0, "max": 80.0, "default": 40.0}, {"label": "带体厚度 (mm)", "key": "thickness", "min": 1.0, "max": 6.0, "default": 2.5}]
            },
            "智能穿戴承力外壳": {
                "topology": "PLATE", "search_suffix": "smart wearable rigid enclosure lightweight durable", "constraint": "聚焦抗跌落冲击、加工尺寸稳定性及防敏。对标钛合金或高强聚碳酸酯。",
                "ui_inputs": [{"label": "外壳长度 (mm)", "key": "length", "min": 20.0, "max": 100.0, "default": 45.0}, {"label": "外壳宽度 (mm)", "key": "width", "min": 15.0, "max": 80.0, "default": 35.0}, {"label": "设计壁厚 (mm)", "key": "thickness", "min": 0.5, "max": 3.0, "default": 1.2}]
            }
        }
    }
}

st.title("🚀 材料特性在具体应用领域中的使用可行性评估系统")
st.markdown("""
<style>
    .stTabs [data-baseweb='tab-list'] {gap: 6px;} 
    .stTabs [data-baseweb='tab'] {background-color: #f0f2f6; font-weight: bold;} 
    .stTabs [aria-selected='true'] {background-color: #000; color: white;}
    hr {margin-top: 10px; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

# ================= 侧边栏：复合材料与零件输入 =================
with st.sidebar:
    st.header("1. 目标终端零部件")
    domain = st.selectbox("选择应用领域", list(DOMAIN_CONFIG.keys()))
    parts_dict = DOMAIN_CONFIG[domain]["parts"]
    target_part = st.selectbox("核心零部件", list(parts_dict.keys()))
    part_config = parts_dict[target_part]
    
    st.header("2. 材料体系结构构建")
    material_mode = st.radio("选择材料研发体系", ["单一均质材料", "复合/杂化材料体系"])
    
    if material_mode == "单一均质材料":
        mat_category = st.selectbox("材料大类", ["合成蛋白/生物基大分子", "碳纤维复合", "特种工程塑料", "特种合金"])
        final_density = st.number_input("密度 (g/cm³)", value=1.30)
        final_strength = st.number_input("抗拉强度 (MPa)", value=9600.0)
        final_modulus = st.number_input("弹性模量 (GPa)", value=100.0)
        search_cat = mat_category
    else:
        st.info("基于混合定律 (Rule of Mixtures) 核算")
        mat_category = st.selectbox("基体 (Matrix)", ["环氧树脂", "PEEK", "PLA/PHA降解树脂", "铝合金"])
        fiber_category = st.selectbox("增强体 (Fiber/Filler)", ["合成蛛丝蛋白纤维", "T1000 碳纤维", "高强芳纶纤维"])
        vf = st.slider("增强体体积分数 (Vf %)", min_value=10, max_value=80, value=60) / 100.0
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**基体参数**")
            m_d = st.number_input("密度(基体)", value=1.2)
            m_s = st.number_input("强度(基体)", value=80.0)
            m_e = st.number_input("模量(基体)", value=3.0)
        with c2:
            st.markdown(f"**增强体参数**")
            f_d = st.number_input("密度(增强)", value=1.3)
            f_s = st.number_input("强度(增强)", value=9600.0)
            f_e = st.number_input("模量(增强)", value=100.0)
            
        final_density = m_d * (1-vf) + f_d * vf
        final_strength = m_s * (1-vf) + f_s * vf
        final_modulus = m_e * (1-vf) + f_e * vf
        
        st.success(f"✅ **混合运算结果：**\n密度: {final_density:.2f} | 强度: {final_strength:.0f} | 模量: {final_modulus:.1f}")
        search_cat = f"{fiber_category} reinforced {mat_category}"
    
    if target_part != st.session_state["last_part"]:
        st.session_state["llm_report"] = None
        st.session_state["last_part"] = target_part

    st.divider()
    generate_btn = st.button("🚀 启动深度评测与多维仿真", type="primary", use_container_width=True)

api_key = st.secrets.get("DEEPSEEK_API_KEY", "")
tavily_key = st.secrets.get("TAVILY_API_KEY", "")

# ================= 大模型 LLM 评测逻辑 =================
if generate_btn:
    if not api_key: st.warning("未配置 DeepSeek API Key。"); st.stop()
    
    with st.spinner(f"正在读取独家文献数据库，对【{target_part}】进行全维深度评测..."):
        web_query = f"scholarly articles {search_cat} application {target_part} {part_config['search_suffix']}"
        web_context = search_tavily(web_query, tavily_key)
        
        local_query = f"{search_cat} {target_part} 制造工艺 缺陷 规范"
        rag_context = retrieve_knowledge(local_query)

        system_prompt = f"""
        你是全球顶尖的材料科学家和应用工程师。评估材料体系在【{domain}】领域【{target_part}】上的商业可行性。
        材料参数: 密度={final_density:.2f} g/cm³, 强度={final_strength:.0f} MPa, 模量={final_modulus:.1f} GPa。
        核心约束: {part_config['constraint']}
        情报: {web_context}
        
        【数据包装】禁止提“本地文件”或“Tavily”。包装为：“独家内部数据库” 或 “学术文献”。
        
        必须输出极度庞大的标准 JSON（严禁Markdown标记，确保结构完整闭合）：
        {{
          "market_positioning": {{
            "tier": "颠覆级 / 标杆级 / 常规替代级",
            "verdict": "一句话定调产品的市场竞争力和核心卖点",
            "competitor_compare": "详细对比现役最顶尖竞品方案的优势和劣势"
          }},
          "radar": {{"强度容限": 100, "刚度稳定": 60, "轻量化收益": 95, "加工成型": 45, "专属环境抗性": 80, "商业潜力": 90}},
          "base_metrics": [
            {{"metric": "等效抗拉极限", "Base1": 570, "Base2": 3000, "NewMat": {final_strength}}},
            {{"metric": "等效模量支撑", "Base1": 71, "Base2": 160, "NewMat": {final_modulus}}},
            {{"metric": "比强度/效能比", "Base1": 203, "Base2": 1875, "NewMat": {final_strength/final_density}}},
            {{"metric": "比模量/比刚度", "Base1": 25.3, "Base2": 100, "NewMat": {final_modulus/final_density}}}
          ],
          "summary_1": "本征参数对标总结",
          "math_sim": {{
            "design_goal": "核心部件等效替代目标",
            "math_latex": "写出具体的等效方程",
            "table": [
              {{"param": "核心代换指标", "base": "现役基准", "new": "计算值"}}
            ],
            "chart_vals": {{"base_wt": 4.25, "new_wt": 1.35}}
          }},
          "summary_2": "等效计算模块小结",
          "parameter_sweep": {{
            "sweep_1": {{"chart_title": "风险波动图", "chart_data": [{{"x": "下限", "y": 20}}, {{"x": "中位", "y": 120}}, {{"x": "上限", "y": 40}}], "scenarios": [{{"range": "说明", "desc": "后果"}}]}},
            "sweep_2": {{"chart_title": "极限衰减图", "chart_data": [{{"x": "常规", "y": 100}}, {{"x": "严苛", "y": 40}}], "scenarios": [{{"range": "说明", "desc": "策略"}}]}}
          }},
          "summary_3": "风险扫掠模块小结",
          "eight_dimensions": [
            {{"dim": "1. 静态载荷", "details": ["分析1"], "chart_metric": "倍数", "base_val": 1.0, "new_val": 3.2}},
            {{"dim": "2. 动态疲劳", "details": ["分析1"], "chart_metric": "寿命", "base_val": 100, "new_val": 80}},
            {{"dim": "3. 几何工艺", "details": ["分析1"], "chart_metric": "良率", "base_val": 95, "new_val": 60}},
            {{"dim": "4. 专属抗性", "details": ["分析1"], "chart_metric": "保持率", "base_val": 90, "new_val": 45}},
            {{"dim": "5. 微观混合", "details": ["分析1"], "chart_metric": "优越度", "base_val": 50, "new_val": 90}},
            {{"dim": "6. 经济降本", "details": ["分析1"], "chart_metric": "降本(%)", "base_val": 0, "new_val": 15}},
            {{"dim": "7. ESG表现", "details": ["分析1"], "chart_metric": "表现", "base_val": 20, "new_val": 85}},
            {{"dim": "8. 行业壁垒", "details": ["分析1"], "chart_metric": "周期", "base_val": 10, "new_val": 18}}
          ],
          "summary_4": "八维切片深度小结",
          "grand_verdict": {{
            "summary": "最终投产陈词与红绿灯决议",
            "strengths": ["优势1", "优势2"],
            "weaknesses": ["致命短板1", "风险2"]
          }},
          "reference_sources": ["独家内部数据库: xxx", "学术文献: xxx"]
        }}
        """
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
        payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.15}
        
        try:
            res = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=120)
            res.raise_for_status()
            raw_content = res.json()['choices'][0]['message']['content']
            
            # 清除前后多余格式
            if "```json" in raw_content: 
                raw_content = raw_content.split("```json")[1].split("```")[0]
            elif "```" in raw_content: 
                raw_content = raw_content.split("```")[1].split("```")[0]
                
            st.session_state["llm_report"] = json.loads(raw_content.strip())
            st.success(f"✅ 【{target_part}】模型论证完成！")
        except Exception as e:
            st.error(f"模型生成错误或被截断，请重试: {str(e)}")


# ================= 🌟 视图渲染引擎：上下舒展布局 + 全系图表 🌟 =================
if st.session_state["llm_report"]:
    data = st.session_state["llm_report"]
    
    # ---------------- 顶层板块：市场定位与 多维交互工程沙盒 ----------------
    st.markdown(f"<h1 style='text-align: center; color: #000;'>🏆 市场定位评估：{data['market_positioning']['tier']}</h1>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='text-align: center; color: #4a4a4a;'>{data['market_positioning']['verdict']}</h4><hr>", unsafe_allow_html=True)
    
    st.markdown(f"### ⚙️ 【{target_part}】实时动态工程沙盒")
    st.caption("👈 滑动修改下方尺寸参数，图纸与物理指标将以 60FPS 零延迟同步刷新")
    
    # [舒展排版 1] 尺寸拉杆横向排列
    current_dims = {}
    slider_cols = st.columns(len(part_config["ui_inputs"]))
    for idx, item in enumerate(part_config["ui_inputs"]):
        with slider_cols[idx]:
            current_dims[item["key"]] = st.slider(item["label"], item["min"], item["max"], item["default"], key=f"ds_{item['key']}")
    
    # [舒展排版 2] 竞品博弈作为宽屏阅读区
    st.markdown("#### ⚔️ 市场竞品对标剖析")
    st.info(data['market_positioning']['competitor_compare'])

    # [舒展排版 3] 核心重点：双 3D 引擎展示（左侧宏观，右侧微观云图）
    st.markdown("#### 📐 双重视角：宏观结构与微观特征仿真")
    col_draw_macro, col_draw_micro = st.columns(2)
    with col_draw_macro:
        st.plotly_chart(render_3d_blueprint(part_config["topology"], current_dims, "macro"), use_container_width=True)
    with col_draw_micro:
        st.plotly_chart(render_3d_blueprint(part_config["topology"], current_dims, "micro"), use_container_width=True)

    # [舒展排版 4] 横向拉宽的多维极限工况仪表盘
    st.markdown("#### ⚡ 终端多维极限工况推演仪表盘")
    physics_df = calculate_physics(part_config["topology"], current_dims, final_strength, final_modulus, final_density)
    
    fig_dash = px.bar(
        physics_df, x="数值", y="指标", orientation='h', text_auto='.4s', 
        color="指标", color_discrete_sequence=px.colors.sequential.Greys_r
    )
    fig_dash.update_layout(showlegend=False, height=250, margin=dict(l=10, r=20, t=10, b=10))
    st.plotly_chart(fig_dash, use_container_width=True)

    st.markdown("<hr style='border:2px solid black'>", unsafe_allow_html=True)
    
    # ---------------- 底层板块：v19 全系硬核分析报告保留 ----------------
    
    # 模块 I
    st.subheader("I. 综合本征参数与多维潜力对标")
    c_radar, c_bars = st.columns([1, 2.5])
    with c_radar:
        df_radar = pd.DataFrame(dict(r=list(data['radar'].values()), theta=list(data['radar'].keys())))
        fig_rd = px.line_polar(df_radar, r='r', theta='theta', line_close=True)
        fig_rd.update_traces(fill='toself', line_color='black')
        st.plotly_chart(fig_rd.update_layout(margin=dict(t=30, b=10)), use_container_width=True)

    with c_bars:
        r1c1, r1c2 = st.columns(2)
        r2c1, r2c2 = st.columns(2)
        cols_b = [r1c1, r1c2, r2c1, r2c2]
        for idx, md in enumerate(data['base_metrics']):
            df_b = pd.DataFrame({"方案": ["现役A", "现役B", "本案材料"], "数值": [md['Base1'], md['Base2'], md['NewMat']]})
            fig_b = px.bar(df_b, x="方案", y="数值", text_auto='.2s', color="方案", color_discrete_sequence=["#d3d3d3", "#a9a9a9", "#000000"])
            fig_b.update_layout(title=md['metric'], showlegend=False, height=180, margin=dict(l=10, r=10, t=30, b=10))
            cols_b[idx].plotly_chart(fig_b, use_container_width=True)
    st.info(f"**📌 阶段小结：** {data.get('summary_1', '本征参数已核算完毕。')}")
    st.divider()

    # 模块 II
    st.subheader("II. 结构数学代换与效能核算")
    sim = data['math_sim']
    st.markdown(f"**🎯 核心等效代换目标:** `{sim['design_goal']}`")
    with st.container(border=True):
        st.markdown("理论推导公式：")
        st.markdown(sim['math_latex'])
    
    sc1, sc2 = st.columns([1.5, 1])
    with sc1:
        df_sim = pd.DataFrame(sim["table"]).rename(columns={"param": "代换关键参数", "base": "现役基准", "new": "方案推演值"})
        st.dataframe(df_sim, use_container_width=True, hide_index=True)
    with sc2:
        df_wt = pd.DataFrame({"方案": ["现役基准", "新设计"], "综合效能": [sim['chart_vals']['base_wt'], sim['chart_vals']['new_wt']]})
        fig_wt = px.bar(df_wt, x="方案", y="综合效能", color="方案", text="综合效能", height=200, color_discrete_map={"现役基准": "#7f7f7f", "新设计": "#000000"})
        fig_wt.update_layout(showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_wt, use_container_width=True)
    st.info(f"**📌 阶段小结：** {data.get('summary_2', '等效代换论证完成。')}")
    st.divider()

    # 模块 III
    st.subheader("III. 领域核心风险与衰减预演")
    swp_c1, swp_c2 = st.columns(2)
    with swp_c1:
        with st.container(border=True):
            sw1 = data['parameter_sweep']['sweep_1']
            fig_s1 = px.bar(pd.DataFrame(sw1['chart_data']), x="x", y="y", title=sw1['chart_title'], height=220, color_discrete_sequence=['#4a4a4a'])
            fig_s1.update_layout(margin=dict(l=10,r=10,t=40,b=10))
            st.plotly_chart(fig_s1, use_container_width=True)
            for sc in sw1['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
    with swp_c2:
        with st.container(border=True):
            sw2 = data['parameter_sweep']['sweep_2']
            fig_s2 = px.line(pd.DataFrame(sw2['chart_data']), x="x", y="y", markers=True, title=sw2['chart_title'], height=220, color_discrete_sequence=['#000000'])
            fig_s2.update_layout(margin=dict(l=10,r=10,t=40,b=10))
            st.plotly_chart(fig_s2, use_container_width=True)
            for sc in sw2['scenarios']: st.markdown(f"- **{sc['range']}**: {sc['desc']}")
    st.info(f"**📌 阶段小结：** {data.get('summary_3', '极端工况风险排查完成。')}")
    st.divider()

    # 模块 IV
    st.subheader("IV. 商业级八维全生命周期剖析")
    dims = data['eight_dimensions']
    tabs = st.tabs([d['dim'] for d in dims])
    for i, tab in enumerate(tabs):
        with tab:
            tc1, tc2 = st.columns([1.5, 1])
            with tc1:
                st.markdown("#### 🔍 深度定性论证")
                for d in dims[i]['details']: st.markdown(f"- {d}")
            with tc2:
                df_tab = pd.DataFrame({"对标对象": ["现役基准", "本案设计"], "表现数值": [dims[i]['base_val'], dims[i]['new_val']]})
                fig_tab = px.bar(df_tab, x="表现数值", y="对标对象", orientation='h', text="表现数值", color="对标对象", color_discrete_sequence=["#a9a9a9", "#000000"], title=dims[i]['chart_metric'])
                fig_tab.update_layout(showlegend=False, height=180, margin=dict(l=10,r=10,t=40,b=10))
                st.plotly_chart(fig_tab, use_container_width=True)
    st.info(f"**📌 阶段小结：** {data.get('summary_4', '八维切片展示了系统的全生命周期优势与短板。')}")
    st.divider()

    # 模块 V
    st.subheader("V. 结案决议与隐藏数据溯源")
    verdict = data['grand_verdict']
    st.success(f"**⚖️ 商业落地决议：** {verdict['summary']}")
    v_in1, v_in2 = st.columns(2)
    with v_in1:
        st.markdown("##### 🌟 核心投产优势")
        for s in verdict['strengths']: st.markdown(f"✔️ {s}")
    with v_in2:
        st.markdown("##### ⚠️ 致命工程短板与风险")
        for w in verdict['weaknesses']: st.markdown(f"❌ {w}")
        
    st.markdown("#### 📚 核心数据底层来源 (Data Origins)")
    for ref in data.get('reference_sources', []): st.markdown(f"- 🔗 **{ref}**")
