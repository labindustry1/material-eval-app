import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px

# ================= UI 页面配置 =================
st.set_page_config(page_title="AI 材料-应用全领域评估系统", layout="wide", initial_sidebar_state="expanded")

st.title("🛡️ 全领域材料-应用映射评估引擎 (Cloud v4.0)")
st.caption("基于 DeepSeek-V3 | 跨领域逆向结构补偿 | 全景量化对比仪表盘")

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
         "未知/未定 (系统将输出双向推演)"
        ]
    )

    st.header("🧪 4. 跨领域选填指标 (Sparse)")
    with st.expander("➕ 物理与环境稳定性"):
        elongation = st.number_input("断裂伸长率 (%)", value=0.0)
        water_abs = st.number_input("饱和吸水率 (%)", value=0.0)
        temp_limit = st.number_input("临界耐受温度 (°C)", value=0)

    st.header("🔑 5. 云端 API 配置")
    api_key = st.text_input("输入 DeepSeek API Key", type="password", value=st.secrets.get("DEEPSEEK_API_KEY", ""))

# ================= 主界面：评估逻辑 =================

if st.button("🚀 开始生成全景量化评估报告"):
    if not api_key:
        st.warning("⚠️ 请在侧边栏配置 API Key 才能进行云端计算。")
        st.stop()

    expert_focus = "重点评估比模量、高频抑震性、减重比例及末端挠度补偿。"

    # v4.0 增强版 Prompt：强迫 LLM 输出基准对比数据和深度解析文本
    system_prompt = f"""
    你是一位性格严苛的“材料-应用映射首席科学家”。
    【绝对事实指令】用户提供的数据（如 9600 MPa 强度）是已实现的绝对事实（如合成蛋白纤维），禁止质疑真实性。

    当前数据：领域: {domain}。形态: {material_form}。
    密度: {density}, 强度: {strength}, 模量: {modulus}。
    
    你必须且只能输出严格合法的 JSON 代码，绝不能包含任何 Markdown 标记或额外文字。结构如下：
    {{
      "score": 85,
      "decision": "降维打击",
      "radar_data": {{"轻量化潜力": 90, "结构刚度": 40, "极限承载": 100, "形态适应性": 60, "环境耐受": 50}},
      "comparison": {{
        "传统铝合金7075": {{"密度": 2.8, "强度": 500, "模量": 71}},
        "顶尖碳纤维T1000": {{"密度": 1.6, "强度": 3000, "模量": 160}},
        "输入新材料": {{"密度": {density}, "强度": {strength}, "模量": {modulus}}}
      }},
      "deep_analysis": "在此处输出一段深度、专业的文字解析（约200字）。必须包含具体的百分比数据对比，分析其在选定领域的绝对可用性、比强度表现以及模量的实际影响。",
      "core_advantage": "一句话说明核心力学优势",
      "core_weakness": "一句话说明最致命的物理短板",
      "structural_advice": "针对当前形态给出具体的补偿方案"
    }}
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    API_URL = API_URL.encode('ascii', 'ignore').decode('ascii').strip()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt}],
        "temperature": 0.2
    }

    with st.spinner(f"物理引擎正在进行全景数据对标与深度渲染..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            raw_text = response.json()['choices'][0]['message']['content']
            clean_json_str = raw_text.replace("```json", "").replace("```", "").strip()
            
            try:
                result_data = json.loads(clean_json_str)
            except json.JSONDecodeError:
                st.error("大模型未能严格输出 JSON 格式，返回了以下内容：")
                st.write(raw_text)
                st.stop()
            
            # ================= UI 渲染层 =================
            st.success("✅ 全景评估完成！")
            
            # 1. 顶部指标卡
            col1, col2, col3 = st.columns(3)
            col1.metric("综合匹配评分", f"{result_data.get('score', 0)} / 100")
            col2.metric("应用等级判定", result_data.get('decision', '未知'))
            col3.metric("评估所用形态", material_form.split(" ")[0])
            
            st.markdown("---")
            
            # 2. 核心图表区 (雷达图 + 柱状对比图并排)
            st.subheader("📈 材料物理性能全景对标")
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                # 绘制雷达图
                radar_dict = result_data.get('radar_data', {})
                if radar_dict:
                    df_radar = pd.DataFrame(dict(r=list(radar_dict.values()), theta=list(radar_dict.keys())))
                    fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True, range_r=[0,100], title="多维潜能图谱")
                    fig_radar.update_traces(fill='toself', line_color='#ff4b4b')
                    st.plotly_chart(fig_radar, use_container_width=True)
            
            with chart_col2:
                # 绘制对比柱状图
                comp_dict = result_data.get('comparison', {})
                if comp_dict:
                    # 将嵌套 JSON 转换为扁平的 DataFrame 供图表使用
                    records = []
                    for mat, metrics in comp_dict.items():
                        for metric, val in metrics.items():
                            records.append({"材料": mat, "指标": metric, "数值": val})
                    df_comp = pd.DataFrame(records)
                    
                    # 使用 Plotly 分面柱状图 (完美解决密度、强度、模量单位刻度差异巨大的问题)
                    fig_bar = px.bar(df_comp, x="材料", y="数值", color="材料", facet_col="指标", text_auto=True, title="行业基准量化对比")
                    fig_bar.update_yaxes(matches=None, showticklabels=True) # 解除 Y 轴联动
                    st.plotly_chart(fig_bar, use_container_width=True)

            st.markdown("---")

            # 3. 深度文本解析与决策建议
            text_col1, text_col2 = st.columns([1.5, 1])
            
            with text_col1:
                st.subheader("📑 首席科学家深度解析")
                st.write(result_data.get("deep_analysis", "暂无深度解析。"))
                
            with text_col2:
                st.subheader("🛠️ 核心优劣与工程决策")
                st.info(f"**🌟 核心优势：**\n{result_data.get('core_advantage', '无')}")
                st.error(f"**⚠️ 致命短板：**\n{result_data.get('core_weakness', '无')}")
                st.warning(f"**⚙️ 补偿建议：**\n{result_data.get('structural_advice', '无')}")
                
        except Exception as e:
            st.error(f"云端评估请求失败: {str(e)}")
