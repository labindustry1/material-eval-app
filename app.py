import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px

# ================= UI 页面配置 =================
st.set_page_config(page_title="AI 材料-应用全领域评估系统", layout="wide", initial_sidebar_state="expanded")

st.title("🛡️ 全领域材料-应用映射评估引擎 (Cloud v3.5)")
st.caption("基于 DeepSeek-V3 物理推理模型 | 跨领域逆向结构补偿 | 强制 JSON 渲染")

# ================= 侧边栏：全参数输入矩阵 =================
with st.sidebar:
    st.header("🌐 1. 选择评估领域")
    domain = st.selectbox(
        "下游目标行业",
        [
            "机器人与工业自动化 (Robotics)",
            "航空航天与无人机 (Aerospace)",
            "生物医疗植入物 (Biomedical)",
            "新型食品与可持续包装 (Novel Food)",
            "新能源汽车结构件 (Automotive)"
        ]
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

if st.button("🚀 开始跨领域多维度评估 (图表版)"):
    if not api_key:
        st.warning("⚠️ 请在侧边栏配置 API Key 才能进行云端计算。")
        st.stop()

    # 针对不同领域注入专家视角
    domain_prompts = {
        "机器人与工业自动化 (Robotics)": "重点评估比模量、高频抑震性及机械臂末端挠度补偿。",
        "航空航天与无人机 (Aerospace)": "重点评估极致比强度、热膨胀系数及高低温环境下的模量稳定性。",
        "生物医疗植入物 (Biomedical)": "重点评估生物相容性风险、降解速率及模量与人体骨骼/组织的匹配度。"
    }
    expert_focus = domain_prompts.get(domain, "综合评估其在该领域的替代潜力。")

    # 构建极端严苛的 JSON 强制提示词
    system_prompt = f"""
    你是一位性格严苛的“材料-应用映射首席科学家”。
    
    【绝对事实指令】
    用户提供的材料数据（如 9600 MPa 的强度）是实验室已实现的绝对事实。绝对禁止你提出质疑、猜测其为数据错误或单位错误。你的任务是基于此数据向下游推演应用方案！

    【当前数据】
    领域: {domain}。视角: {expert_focus}。
    材料形态: {material_form}。
    密度: {density} g/cm³, 强度: {strength} MPa, 模量: {modulus} GPa。
    伸长率: {elongation}%, 吸水率: {water_abs}%, 耐温: {temp_limit}°C。

    【核心指令】
    你必须且只能输出一段严格合法的 JSON 代码，绝不能包含任何 Markdown 标记（如 ```json）、分析过程或额外文字。
    如果形态为“纤维”，必须基于复合材料法则评估；如果为“体块”，严查其绝对应变挠度。

    【严格的输出 JSON 结构】
    {{
      "score": 85, 
      "decision": "降维打击", 
      "radar_data": {{"轻量化潜力": 90, "结构刚度": 40, "极限承载": 100, "形态适应性": 60, "环境耐受": 50}},
      "core_advantage": "一句话说明核心力学优势",
      "core_weakness": "一句话说明最致命的物理短板或缺失数据的盲区",
      "structural_advice": "针对当前形态给出具体的几何截面、复材工艺或成型补偿方案",
      "rag_citation": "暂无外挂知识库匹配标准"
    }}
    注意："decision" 字段的值只能是以下四个之一："降维打击"、"优势明显"、"勉强可用"、"风险巨大"。
    """

    API_URL = "[https://api.deepseek.com/chat/completions](https://api.deepseek.com/chat/completions)"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "system", "content": system_prompt}],
        "temperature": 0.1 # 极低温度，确保输出严谨 JSON
    }

    with st.spinner(f"物理引擎正在处理数据，绘制多维潜能图谱..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            raw_text = response.json()['choices'][0]['message']['content']
            # 清洗大模型可能自带的 markdown 格式
            clean_json_str = raw_text.replace("```json", "").replace("```", "").strip()
            
            try:
                result_data = json.loads(clean_json_str)
            except json.JSONDecodeError:
                st.error("大模型未能严格输出 JSON 格式，返回了以下内容：")
                st.write(raw_text)
                st.stop()
            
            # ================= UI 渲染层 =================
            st.success("✅ 云端推演完成！")
            
            # 1. 顶部指标卡
            col1, col2, col3 = st.columns(3)
            col1.metric("综合匹配评分", f"{result_data.get('score', 0)} / 100")
            col2.metric("应用等级判定", result_data.get('decision', '未知'))
            form_display = material_form.split(" ")[0] if material_form else "未知"
            col3.metric("评估所用形态基准", form_display)
            
            st.markdown("---")
            
            # 2. 图表与文字分析并排
            col_chart, col_text = st.columns([1, 1.2])
            
            with col_chart:
                st.subheader("📊 多维物理潜能雷达")
                radar_dict = result_data.get('radar_data', {})
                if radar_dict:
                    df = pd.DataFrame(dict(
                        r=list(radar_dict.values()),
                        theta=list(radar_dict.keys())
                    ))
                    fig = px.line_polar(df, r='r', theta='theta', line_close=True, range_r=[0,100])
                    fig.update_traces(fill='toself', line_color='#ff4b4b')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("暂无雷达图数据")
                
            with col_text:
                st.subheader("🛠️ 工程决策与补偿方案")
                st.info(f"**🌟 核心优势：** {result_data.get('core_advantage', '无')}")
                st.error(f"**⚠️ 致命短板：** {result_data.get('core_weakness', '无')}")
                st.warning(f"**⚙️ 结构与工艺建议：** {result_data.get('structural_advice', '无')}")
                st.caption(f"📚 {result_data.get('rag_citation', '')}")
                
        except Exception as e:
            st.error(f"云端评估请求失败: {str(e)}")
