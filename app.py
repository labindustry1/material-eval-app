import streamlit as st
import requests
import json

# ================= UI 页面配置 =================
st.set_page_config(page_title="AI 材料-应用全领域评估系统", layout="wide", initial_sidebar_state="expanded")

# 自定义样式：让报告更像正式文档
st.markdown("""
    <style>
    .report-box { padding: 20px; border-radius: 10px; border: 1px solid #e0e0e0; background-color: #f9f9f9; }
    .stButton>button { width: 100%; font-weight: bold; height: 3em; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ 全领域材料-应用映射评估引擎 (Cloud v3.0)")
st.caption("基于 DeepSeek-V3 物理推理模型 | 跨领域逆向结构补偿")

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
    
    st.header("🧪 3. 跨领域选填指标 (Sparse)")
    with st.expander("➕ 物理与环境稳定性"):
        elongation = st.number_input("断裂伸长率 (%)", value=0.0)
        water_abs = st.number_input("饱和吸水率 (%)", value=0.0)
        temp_limit = st.number_input("临界耐受温度 (°C)", value=0)
        conductivity = st.number_input("导电率 (S/m)", value=0.0)

    st.header("🔑 4. 云端 API 配置")
    # 优先从 Streamlit Secrets 读取，本地调试可手动填
    api_key = st.text_input("输入 DeepSeek API Key", type="password", value=st.secrets.get("DEEPSEEK_API_KEY", ""))

# ================= 主界面：评估逻辑 =================

if st.button("🚀 开始跨领域多维度评估"):
    if not api_key:
        st.warning("请在侧边栏配置 API Key 才能进行云端计算。")
        st.stop()

    # 动态构建输入数据上下文
    input_context = f"领域: {domain}; 密度: {density}; 强度: {strength}; 模量: {modulus}; "
    if elongation > 0: input_context += f"伸长率: {elongation}%; "
    if water_abs > 0: input_context += f"吸水率: {water_abs}%; "
    if temp_limit > 0: input_context += f"耐温: {temp_limit}C; "

    # 针对不同领域注入不同的“专家之魂”
    domain_prompts = {
        "机器人与工业自动化 (Robotics)": "重点评估比模量、高频抑震性及机械臂末端挠度补偿。",
        "航空航天与无人机 (Aerospace)": "重点评估极致比强度、热膨胀系数及高低温环境下的模量稳定性。",
        "生物医疗植入物 (Biomedical)": "重点评估生物相容性风险、降解速率及模量与人体骨骼/组织的匹配度。",
        "新型食品与可持续包装 (Novel Food)": "重点评估在特定化学浴（如甲醇/甲酸）中的成型稳定性、多聚体堆叠逻辑及食用安全性。",
        "新能源汽车结构件 (Automotive)": "重点评估冲击能吸收（吸能比）、阻燃性及大尺寸件的注塑/成型良率。"
    }

    system_prompt = f"""
    你是一位性格严苛的“材料-应用映射首席科学家”。
    
    【你的任务】
    基于提供的材料数据，给出针对【{domain}】场景的深度评估。
    {domain_prompts.get(domain, "")}

    【必须包含的输出板块】
    1. 🏆 **综合匹配评分 (0-100)** 与 **应用等级判定** (例如：降维打击/优势明显/风险巨大)。
    2. 📊 **对标基准分析**：必须将该材料与该领域的“标杆材料”进行量化数据对比（如铝合金、碳纤维、钛合金或特定聚合物）。
    3. 🛠️ **逆向结构补偿方案**：如果不达标，给出具体的几何改进或成型工艺优化建议。
    4. ⚠️ **致命缺陷预警**：基于缺失数据，指出最可能导致失效的盲区，并点名下一步必须测量的参数。
    5. 🔮 **行业替代潜力**：预测该材料能替代该领域的哪种传统零部件，并计算减重或性能提升百分比。
    """

    # 调用公网 API (OpenAI 兼容格式)
    API_URL = "https://api.deepseek.com/chat/completions" # 可根据需要改为阿里云等其他地址
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"材料数据如下：{input_context}"}
        ],
        "temperature": 0.3 # 降低随机性，保证严谨
    }

    with st.spinner(f"正在连接云端服务器，针对 {domain} 领域进行深度推演..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()['choices'][0]['message']['content']
            
            st.success("评估报告生成成功！")
            st.markdown(f'<div class="report-box">{result}</div>', unsafe_allow_html=True)
            
            # 提供下载按钮
            st.download_button("💾 下载评估报告 (.txt)", result, file_name=f"Material_Report_{domain}.txt")
            
        except Exception as e:
            st.error(f"云端评估请求失败: {str(e)}")
