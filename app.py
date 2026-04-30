import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ================= UI 页面配置 =================
st.set_page_config(page_title="量化材料评估系统", layout="wide", initial_sidebar_state="expanded")

st.title("📊 材料物性与工程应用量化评估系统 (v7.0 数据驱动版)")
st.caption("基于多维物理模型 | 客观指标拆解 | 量化结构代换计算 | 纯数据驱动")

# ================= 侧边栏：全参数输入 =================
with st.sidebar:
    st.header("1. 目标应用领域")
    domain = st.selectbox(
        "选择对标基准库",
        ["机器人与工业自动化", "航空航天与无人机", "生物医疗植入物", "新能源汽车结构件"]
    )

    st.header("2. 核心物性参数 (必填)")
    density = st.number_input("密度 (g/cm³)", value=1.30, format="%.2f")
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    
    st.header("3. 物理形态约束")
    material_form = st.selectbox(
        "宏观结构",
        ["高强纤维/长丝 (单向受力/复材增强相)", "各向同性体块/浇铸件 (多向受力承载体)"]
    )

    st.header("4. 高阶环境参数 (选填)")
    with st.expander("展开输入参数"):
        elongation = st.number_input("断裂伸长率 (%)", value=0.0)
        water_abs = st.number_input("饱和吸水率 (%)", value=0.0)

    st.header("5. 引擎配置")
    api_key = st.text_input("DeepSeek API Key", type="password", value=st.secrets.get("DEEPSEEK_API_KEY", ""))

# ================= 主界面：评估逻辑 =================

if st.button("运行多维量化数据分析引擎", type="primary"):
    if not api_key:
        st.warning("⚠️ 需配置 API Key 方可运行。")
        st.stop()

    # 极度冷酷的数据提取指令，严禁任何废话和主观情感
    system_prompt = f"""
    你是一个无情感的工业材料数据分析引擎。任务是对用户输入的材料数据进行多维量化拆解。
    输入参数：领域={domain}, 形态={material_form}, 密度={density}, 强度={strength}, 模量={modulus}。
    
    【核心指令】
    1. 严禁使用“首席科学家”、“我建议”、“极度推荐”等主观角色扮演或夸张词汇。
    2. 所有分析必须基于数据，语言冷峻、客观、条理化。
    3. 必须输出包含5个维度的详细数据对比。
    4. 必须输出基于近似计算的量化代换建议（如：等刚度代换下，面积需增加的百分比）。
    
    只输出纯 JSON，不含任何 Markdown，格式必须严格如下：
    {{
      "overview": {{
        "composite_index": 82,
        "radar_metrics": {{"比强度极限": 100, "刚度与形变": 55, "抗疲劳潜力": 40, "轻量化效益": 95, "加工良率预估": 50, "环境稳定性": 60}}
      }},
      "detailed_dimensions": [
        {{
          "dim_name": "静态承载极限",
          "score": 95,
          "chart_data": [
            {{"material": "输入材料", "metric": "比强度(kN·m/kg)", "value": 7384}},
            {{"material": "航空铝7075", "metric": "比强度(kN·m/kg)", "value": 203}},
            {{"material": "碳纤维T1000", "metric": "比强度(kN·m/kg)", "value": 1875}}
          ],
          "objective_analysis": ["数据分析点1(带具体数字倍数)", "数据分析点2"]
        }},
        // 必须按此结构严格补充另外4个维度：
        // "刚度与挠度控制" (对比绝对模量)
        // "动态与疲劳预估" (对比伸长率或理论疲劳极限)
        // "轻量化效能" (对比密度)
        // "制造与工艺约束" (根据形态，列出加工难点)
      ],
      "quantitative_guidelines": [
        {{"scenario": "等刚度代换铝合金(受弯截面)", "data_support": "因模量为100GPa(高于铝的71GPa)，同等截面下挠度将减少约29%；若追求极限减重，管壁厚度可缩减约15%。"}},
        {{"scenario": "等强度代换钢索(受拉结构)", "data_support": "强度达9600MPa，承载横截面积理论上可缩小至高强钢丝的1/4，重量缩减超80%。"}}
      ],
      "case_comparisons": [
        {{
          "application": "机械臂主承力骨架",
          "traditional_solution": "7075铝合金管材",
          "traditional_data": "密度2.8, 模量71GPa, 壁厚3mm",
          "proposed_solution": "新材料纤维缠绕复合管",
          "proposed_data": "密度1.3, 模量100GPa, 建议壁厚2.5mm以匹配原抗扭刚度",
          "net_benefit": "总成减重约58%，末端静挠度降低10%"
        }},
        {{"application": "案例2名称", "traditional_solution": "传统方案", "traditional_data": "数据", "proposed_solution": "新方案", "proposed_data": "数据", "net_benefit": "收益"}}
      ]
    }}
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    API_URL = API_URL.encode('ascii', 'ignore').decode('ascii').strip()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.1}

    with st.spinner(f"引擎正在运行多维量化矩阵计算与案例推演..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            raw_text = response.json()['choices'][0]['message']['content']
            clean_json_str = raw_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json_str)
            
            st.success("✅ 量化分析完成。")
            
            # ================= 1. 顶层看板 =================
            col_idx, col_radar = st.columns([1, 2.5])
            with col_idx:
                st.metric("综合物性指数", f"{data['overview']['composite_index']} / 100")
                st.caption(f"标定基准: {domain}")
                st.caption(f"评估形态: {material_form.split(' ')[0]}")
            with col_radar:
                radar_metrics = data['overview']['radar_metrics']
                df_radar = pd.DataFrame(dict(r=list(radar_metrics.values()), theta=list(radar_metrics.keys())))
                fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True, height=300)
                fig_radar.update_traces(fill='toself', line_color='#2ca02c') # 使用理性的绿色
                fig_radar.update_layout(margin=dict(l=40, r=40, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_radar, use_container_width=True)

            st.markdown("---")

            # ================= 2. 多维客观数据切片 =================
            st.markdown("### 📊 独立维度数据对标")
            dimensions = data.get("detailed_dimensions", [])
            if dimensions:
                tabs = st.tabs([d['dim_name'] for d in dimensions])
                for i, tab in enumerate(tabs):
                    with tab:
                        dim = dimensions[i]
                        c1, c2 = st.columns([1.2, 1])
                        
                        with c1:
                            # 渲染当前维度的精细柱状图
                            df_chart = pd.DataFrame(dim['chart_data'])
                            if not df_chart.empty:
                                metric_name = df_chart['metric'].iloc[0]
                                # 颜色映射：输入材料为突出的红色，基准为灰色系
                                color_map = {row['material']: '#d62728' if '输入' in row['material'] else '#7f7f7f' for _, row in df_chart.iterrows()}
                                
                                fig_bar = px.bar(
                                    df_chart, y="material", x="value", orientation='h',
                                    text="value", color="material", color_discrete_map=color_map,
                                    height=250
                                )
                                fig_bar.update_layout(
                                    showlegend=False, xaxis_title=metric_name, yaxis_title="",
                                    margin=dict(l=0, r=0, t=10, b=0)
                                )
                                st.plotly_chart(fig_bar, use_container_width=True)
                        
                        with c2:
                            st.markdown(f"**客观项评分：{dim['score']}/100**")
                            for point in dim['objective_analysis']:
                                st.markdown(f"- {point}")

            st.markdown("---")

            # ================= 3. 量化代换计算与设计指导 =================
            st.markdown("### 📐 量化结构代换指导 (Quantitative Guidelines)")
            st.caption("基于理论力学公式的近似结构补偿测算")
            df_guidelines = pd.DataFrame(data.get("quantitative_guidelines", []))
            if not df_guidelines.empty:
                df_guidelines.columns = ["应用场景/代换目标", "量化测算数据与设计支撑"]
                # 使用 DataFrame 的表格化展示，去情感化
                st.dataframe(df_guidelines, use_container_width=True, hide_index=True)

            st.markdown("---")

            # ================= 4. 具体部件应用案例对比 =================
            st.markdown("### 📋 虚拟对标案例研究 (Case Comparisons)")
            cases = data.get("case_comparisons", [])
            for case in cases:
                with st.expander(f"案例对标：{case.get('application', '未知应用')}", expanded=True):
                    col_t, col_p = st.columns(2)
                    with col_t:
                        st.markdown("#### 🟦 现役基准方案")
                        st.info(f"**材料：** {case.get('traditional_solution')}\n\n**数据支撑：** {case.get('traditional_data')}")
                    with col_p:
                        st.markdown("#### 🟥 导入新材料方案")
                        st.error(f"**材料：** {case.get('proposed_solution')}\n\n**数据支撑：** {case.get('proposed_data')}")
                    
                    st.success(f"**💡 量化净收益预估 (Net Benefit)：** {case.get('net_benefit')}")

        except Exception as e:
            st.error(f"系统运行异常。请检查参数或重试。异常明细: {str(e)}")
