import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ================= UI 页面配置 =================
st.set_page_config(page_title="AI 工业级选材评估套件", layout="wide", initial_sidebar_state="expanded")

st.title("🛡️ 全领域材料-应用映射评估引擎 (Enterprise v6.0)")
st.caption("基于 DeepSeek-V3 | 零部件级下钻分析 | 动态/静态全维解析 | 加工成型白皮书")

# ================= 侧边栏：全参数输入 =================
with st.sidebar:
    st.header("🌐 1. 选择评估领域")
    domain = st.selectbox(
        "下游目标行业",
        ["机器人与工业自动化", "航空航天与无人机", "生物医疗植入物", "新能源汽车结构件"]
    )

    st.header("📏 2. 核心力学数据 (必填)")
    density = st.number_input("密度 (g/cm³)", value=1.30, format="%.2f")
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    
    st.header("🧱 3. 材料物理形态")
    material_form = st.selectbox(
        "该材料的宏观表现形式",
        [
         "高强纤维/长丝 (Fiber - 复合材料增强相/张拉体系)", 
         "各向同性体块/浇铸件 (Bulk - 整体主承力件)"
        ]
    )

    st.header("🧪 4. 跨领域选填指标")
    with st.expander("展开输入高阶数据 (影响疲劳与加工分析)"):
        elongation = st.number_input("断裂伸长率 (%)", value=0.0)
        water_abs = st.number_input("饱和吸水率 (%)", value=0.0)

    st.header("🔑 5. 云端 API 配置")
    api_key = st.text_input("输入 DeepSeek API Key", type="password", value=st.secrets.get("DEEPSEEK_API_KEY", ""))

# ================= 主界面：评估逻辑 =================

if st.button("🚀 生成工业级全景评估白皮书", type="primary"):
    if not api_key:
        st.warning("⚠️ 请配置 API Key。")
        st.stop()

    # 极端变态的系统指令：强迫 LLM 输出企业级结构的 JSON
    system_prompt = f"""
    你是全球顶尖的材料科学与制造总工。用户输入的数据（如9600MPa）是绝对工程事实，禁止质疑。
    目标领域：{domain}。材料形态：{material_form}。密度:{density}, 强度:{strength}, 模量:{modulus}。
    
    【隐性专家指令】
    如果形态为“纤维”且密度在1.3左右，你必须在【加工工艺】部分，像评估顶尖合成大分子/特种蛋白纤维一样，深度推演其在溶剂体系、凝固浴（如醇类/胺类双重凝固浴体系）湿法纺丝成型、以及与树脂基体复合（长丝缠绕/拉挤）时的关键技术壁垒和解决方案。

    你必须只输出严谨的 JSON，绝对不要包含 markdown 代码块标记。JSON 结构必须完全如下：
    {{
      "executive_summary": {{
        "overall_score": 85,
        "radar": {{"静态强度": 100, "动态疲劳": 40, "刚度形变": 60, "加工成型": 50, "环境抗性": 70}}
      }},
      "component_mapping": [
        {{"part": "零部件名称A(如:外壳蒙皮)", "suitability": "极度推荐", "reason": "具体力学匹配理由"}},
        {{"part": "零部件名称B(如:主承力传动轴)", "suitability": "严禁使用", "reason": "具体失效风险(如剪切破坏)"}},
        {{"part": "零部件名称C(如:轻量化连杆)", "suitability": "需结构补偿", "reason": "需要如何补偿"}}
      ],
      "dimensional_analysis": [
        {{
          "dimension": "静态力学与极限承载",
          "metrics": [
            {{"name": "比强度", "value": 7384, "unit": "kN·m/kg", "benchmark": 200, "bench_name": "铝7075"}}
          ],
          "analysis": "200字深度解析，包含拉压弯剪的失效模式推演。"
        }},
        {{
          "dimension": "动态响应与形变控制",
          "metrics": [
            {{"name": "绝对模量", "value": 100, "unit": "GPa", "benchmark": 160, "bench_name": "T1000碳纤"}}
          ],
          "analysis": "200字深度解析，包含挠度、高频抑震、疲劳寿命预估。"
        }}
      ],
      "manufacturing_guide": {{
        "primary_process": "推荐的主力成型工艺(如:双浴湿法纺丝+环氧树脂长丝缠绕)",
        "process_steps": [
          "步骤1的深度指导及参数控制建议",
          "步骤2的深度指导及参数控制建议"
        ],
        "defect_risks": "容易出现的制造缺陷（如孔隙率高、皮芯结构不均、界面脱粘）及预防策略"
      }}
    }}
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.15}

    with st.spinner(f"正在进行分子级推演与全产业链制造评估，请稍候..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            raw_text = response.json()['choices'][0]['message']['content']
            clean_json_str = raw_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json_str)
            
            st.success("✅ 工业级全景评估白皮书生成完毕！")
            
            # ================= 1. 顶层看板 =================
            col_score, col_radar = st.columns([1, 2])
            with col_score:
                st.metric("📊 综合工程评级 (Overall Score)", f"{data['executive_summary']['overall_score']} / 100")
                st.info(f"**评估基准:** {domain} | {material_form.split(' ')[0]}")
            with col_radar:
                radar_data = data['executive_summary']['radar']
                fig_radar = px.line_polar(
                    pd.DataFrame(dict(r=list(radar_data.values()), theta=list(radar_data.keys()))),
                    r='r', theta='theta', line_close=True, height=250
                )
                fig_radar.update_traces(fill='toself', line_color='#0068c9')
                fig_radar.update_layout(margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_radar, use_container_width=True)

            st.markdown("---")

            # ================= 2. 零部件级适用性地图 (Traffic Lights) =================
            st.markdown(f"### 🧩 【{domain}】具体零部件适用性判定")
            cols = st.columns(len(data.get("component_mapping", [])))
            for i, comp in enumerate(data.get("component_mapping", [])):
                with cols[i]:
                    suitability = comp.get("suitability", "")
                    color = "🟢" if "推荐" in suitability else "🔴" if "严禁" in suitability or "禁用" in suitability else "🟡"
                    st.markdown(f"**{color} {comp.get('part')}**")
                    st.caption(f"**判定:** {suitability}")
                    st.write(comp.get("reason"))

            st.markdown("---")

            # ================= 3. 多维深度解析 (Tabs) =================
            st.markdown("### 🔬 物理力学多维深度解析")
            dims = data.get("dimensional_analysis", [])
            tabs = st.tabs([d['dimension'] for d in dims])
            
            for i, tab in enumerate(tabs):
                with tab:
                    dim_data = dims[i]
                    c1, c2 = st.columns([1, 1.5])
                    with c1:
                        for metric in dim_data.get('metrics', []):
                            # 对比微型图表
                            fig_bar = go.Figure()
                            fig_bar.add_trace(go.Bar(y=[metric['name']], x=[metric['benchmark']], name=metric['bench_name'], orientation='h', marker_color='lightgray'))
                            fig_bar.add_trace(go.Bar(y=[metric['name']], x=[metric['value']], name="新材料", orientation='h', marker_color='#ff2b2b'))
                            fig_bar.update_layout(barmode='group', height=150, margin=dict(l=0, r=0, t=30, b=0), title=f"{metric['name']} ({metric['unit']})")
                            st.plotly_chart(fig_bar, use_container_width=True)
                    with c2:
                        st.write(dim_data.get('analysis'))

            st.markdown("---")

            # ================= 4. 加工与制造指南 =================
            st.markdown("### 🏭 制造工程与加工白皮书")
            mfg = data.get("manufacturing_guide", {})
            st.success(f"**推荐主工艺路线：** {mfg.get('primary_process')}")
            
            st.markdown("#### ⚙️ 关键工序与参数控制建议")
            for step in mfg.get("process_steps", []):
                st.markdown(f"- {step}")
                
            st.error(f"**⚠️ 致命缺陷预警及预防：**\n{mfg.get('defect_risks')}")

        except Exception as e:
            st.error(f"评估失败，可能由于大模型响应格式不规整。请重试。错误信息: {str(e)}")
