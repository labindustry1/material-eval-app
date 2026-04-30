import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px

# ================= UI 页面配置 =================
st.set_page_config(page_title="AI 材料工程评估套件", layout="wide", initial_sidebar_state="expanded")

st.title("🛡️ 全领域材料-应用映射评估引擎 (Cloud v5.0 Pro)")
st.caption("基于 DeepSeek-V3 | 多维度切片分析 | 独立指标打分与靶向图表")

# ================= 侧边栏：全参数输入矩阵 =================
with st.sidebar:
    st.header("🌐 1. 选择评估领域")
    domain = st.selectbox(
        "下游目标行业",
        ["机器人与工业自动化 (Robotics)", "航空航天与无人机 (Aerospace)", "生物医疗植入物 (Biomedical)"]
    )

    st.header("📏 2. 核心力学数据 (必填)")
    density = st.number_input("密度 (g/cm³)", value=1.30, format="%.2f")
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    
    st.header("🧱 3. 材料物理形态")
    material_form = st.selectbox(
        "该材料的宏观表现形式",
        [
         "高强纤维/长丝 (Fiber - 用于复合材料增强相或张拉索具)", 
         "各向同性体块/浇铸件 (Bulk - 直接作为主承力结构)", 
         "未知/未定 (系统将双向推演)"
        ]
    )

    st.header("🧪 4. 跨领域选填指标")
    with st.expander("➕ 物理与环境稳定性"):
        elongation = st.number_input("断裂伸长率 (%)", value=0.0)
        water_abs = st.number_input("饱和吸水率 (%)", value=0.0)

    st.header("🔑 5. 云端 API 配置")
    api_key = st.text_input("输入 DeepSeek API Key", type="password", value=st.secrets.get("DEEPSEEK_API_KEY", ""))

# ================= 主界面：评估逻辑 =================

if st.button("🚀 生成多维度切片工程报告"):
    if not api_key:
        st.warning("⚠️ 请配置 API Key。")
        st.stop()

    # 构建带有多维切片要求的 JSON 结构指令
    system_prompt = f"""
    你是一位性格严苛的“材料首席科学家”。用户提供的数据（如 9600 MPa 强度）是已实现的绝对事实，禁止质疑。
    当前参数：领域={domain}, 形态={material_form}, 密度={density}, 强度={strength}, 模量={modulus}。
    
    你必须输出严格的 JSON 代码，不得包含 markdown 标记。结构必须严格如下：
    {{
      "executive_summary": {{
        "overall_score": 85,
        "decision": "降维打击",
        "radar_data": {{"力学极限": 100, "刚度形变": 60, "轻量化": 95, "环境加工": 50}}
      }},
      "dimensions": [
        {{
          "tab_name": "💪 力学极限与承载",
          "sub_score": 98,
          "metric_name": "比强度 (MPa·cm³/g)",
          "comparison_data": {{"航空铝7075": 178, "碳纤维T1000": 1875, "输入材料": {strength/density}}},
          "analysis": "针对承重、防爆或拉伸极限的具体工程分析，结合数据说明优势或隐患。"
        }},
        {{
          "tab_name": "📐 刚度与形变控制",
          "sub_score": 60,
          "metric_name": "绝对模量 (GPa)",
          "comparison_data": {{"航空铝7075": 71, "碳纤维T1000": 160, "输入材料": {modulus}}},
          "analysis": "针对机械臂挠度、定位精度或支撑刚性的苛刻分析，必须指出模量带来的具体影响。"
        }},
        {{
          "tab_name": "🪶 轻量化与效能",
          "sub_score": 95,
          "metric_name": "密度 (g/cm³)",
          "comparison_data": {{"航空铝7075": 2.8, "碳纤维T1000": 1.6, "输入材料": {density}}},
          "analysis": "分析在等体积或等强度替换下的减重比例，及其对电机负载/续航的价值。"
        }}
      ],
      "engineering_decision": {{
        "core_advantage": "一句话核心优势",
        "core_weakness": "一句话致命短板",
        "action_plan": "针对该形态材料的具体结构设计与成型建议"
      }}
    }}
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    API_URL = API_URL.encode('ascii', 'ignore').decode('ascii').strip()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt}],
        "temperature": 0.1
    }

    with st.spinner(f"正在进行多维度矩阵切片与图表生成..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            raw_text = response.json()['choices'][0]['message']['content']
            clean_json_str = raw_text.replace("```json", "").replace("```", "").strip()
            
            try:
                data = json.loads(clean_json_str)
            except json.JSONDecodeError:
                st.error("模型数据解析失败，请重试。")
                st.stop()
            
            # ================= UI 渲染：总览区 =================
            st.success("✅ 多维度切片分析完成！")
            summary = data.get("executive_summary", {})
            
            col1, col2, col3 = st.columns(3)
            col1.metric("综合工程评分", f"{summary.get('overall_score', 0)} / 100")
            col2.metric("宏观应用判定", summary.get('decision', '未知'))
            col3.metric("评估基准形态", material_form.split(" ")[0])
            
            # ================= UI 渲染：多维度深度切片 (选项卡) =================
            st.markdown("### 🔍 工程师各维度下钻分析 (Drill-down Analysis)")
            
            dimensions = data.get("dimensions", [])
            if dimensions:
                # 动态生成选项卡
                tabs = st.tabs([dim.get("tab_name", "维度") for dim in dimensions])
                
                for i, tab in enumerate(tabs):
                    with tab:
                        dim_data = dimensions[i]
                        # 每个选项卡内部分为左右两列：左侧图表，右侧分析
                        tab_col1, tab_col2 = st.columns([1.5, 1])
                        
                        with tab_col1:
                            # 渲染该维度专属的条形图
                            comp_data = dim_data.get("comparison_data", {})
                            if comp_data:
                                df_dim = pd.DataFrame({
                                    "材料": list(comp_data.keys()),
                                    "数值": list(comp_data.values())
                                })
                                fig_dim = px.bar(
                                    df_dim, x="数值", y="材料", orientation='h',
                                    title=f"核心指标对比: {dim_data.get('metric_name', '')}",
                                    text_auto='.2s',
                                    color="材料",
                                    color_discrete_sequence=["#a6b8c7", "#5a6e7f", "#ff4b4b"] # 突出新材料
                                )
                                fig_dim.update_layout(showlegend=False, xaxis_title=dim_data.get('metric_name', ''))
                                st.plotly_chart(fig_dim, use_container_width=True)
                        
                        with tab_col2:
                            # 渲染该维度的独立评分与深度文本
                            st.metric(label=f"{dim_data.get('tab_name').split(' ')[-1]} 子项评分", value=f"{dim_data.get('sub_score')}/100")
                            st.info(dim_data.get("analysis", "暂无分析"))
            
            st.markdown("---")
            
            # ================= UI 渲染：工程落地决策 =================
            decision = data.get("engineering_decision", {})
            st.markdown("### 🛠️ 首席总工最终决议")
            dec_col1, dec_col2 = st.columns(2)
            with dec_col1:
                st.success(f"**🌟 核心优势：** {decision.get('core_advantage', '')}")
                st.error(f"**⚠️ 致命短板：** {decision.get('core_weakness', '')}")
            with dec_col2:
                st.warning(f"**⚙️ 落地方案：** {decision.get('action_plan', '')}")

        except Exception as e:
            st.error(f"云端评估请求失败: {str(e)}")
