import streamlit as st
import requests
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse

# ================= UI 页面配置 =================
st.set_page_config(page_title="工业级材料量化推演系统", layout="wide", initial_sidebar_state="expanded")

st.title("🧬 材料本征与系统级效应全景推演引擎 (v10.0)")
st.caption("基准对标 | 缺失参数敏感性扫掠 | 整机效能折算 | 工程实景映射")

# ================= 侧边栏：全参数输入 =================
with st.sidebar:
    st.header("1. 目标应用工况")
    domain = st.selectbox(
        "下游整机系统",
        ["高负载协作机械臂", "长航时工业无人机", "深海探测器结构件", "可穿戴外骨骼"]
    )

    st.header("2. 核心物性参数")
    density = st.number_input("密度 (g/cm³)", value=1.30, format="%.2f")
    strength = st.number_input("极限抗拉强度 (MPa)", value=9600)
    modulus = st.number_input("弹性模量 (GPa)", value=100)
    
    st.header("3. 宏观结构形态")
    material_form = st.selectbox(
        "材料加工形态",
        ["连续长丝/高取向纤维 (单向极限承载)", "多轴向织物预浸料 (平面各向同性)", "浇铸体/3D打印件 (体块受力)"]
    )

    st.header("4. 高阶参数 (选填/触发扫掠)")
    with st.expander("留空将自动触发区间敏感性扫掠"):
        elongation = st.number_input("断裂伸长率 (%)", value=0.0, help="留空为0时，系统将推演脆性/韧性区间")
        water_abs = st.number_input("饱和吸水率 (%)", value=0.0)

    st.header("5. 算力引擎")
    api_key = st.text_input("DeepSeek API Key", type="password", value=st.secrets.get("DEEPSEEK_API_KEY", ""))

# ================= 主界面：评估逻辑 =================

if st.button("启动系统级数据矩阵与参数扫掠", type="primary"):
    if not api_key:
        st.warning("⚠️ 需配置 API Key。")
        st.stop()

    system_prompt = f"""
    你是一个终极工业材料数据演算引擎。
    输入：系统={domain}, 形态={material_form}, 密度={density}, 强度={strength}, 模量={modulus}, 伸长率={elongation}%, 吸水率={water_abs}%。
    
    【核心演算要求】
    1. 必须输出极度硬核的数据，禁止废话。
    2. 【缺失扫掠】若伸长率或吸水率趋近于0，必须预设2个关键的缺失参数（如高分子纤维的吸湿膨胀系数、非晶区玻璃化温度、或韧性断裂能），并给出不同数值区间的工程后果。
    3. 【整机效应】必须把材料在局部零部件上的减重/增强，折算成对最终整机系统（如无人机、机械臂）的宏观提升（包含估算百分比）。
    
    严格输出以下 JSON，不可改变结构，不含 Markdown：
    {{
      "radar_score": {{"比强度极限": 100, "系统级刚度": 60, "整机轻量化": 95, "环境容忍度": 45, "加工成型率": 50, "能量吸收/韧性": 70}},
      "multi_dimensional_data": [
        {{"metric": "拉伸比强度 (kN·m/kg)", "baseline_name": "T1000碳纤", "baseline_val": 1875, "new_val": {strength/density}}},
        {{"metric": "弯曲比刚度 (GPa·cm³/g)", "baseline_name": "铝合金7075", "baseline_val": 25.3, "new_val": {modulus/density}}}
      ],
      "missing_data_sweep": [
        {{
          "parameter": "断裂伸长率预设区间",
          "scenarios": [
            {{"range": "< 2%", "consequence": "呈现极度脆性，对冲击载荷极度敏感。仅能用于纯静态拉伸件，需在表面包覆芳纶吸能层。"}},
            {{"range": "5% - 8%", "consequence": "结合9600MPa的强度，断裂功（韧性）将超越所有已知纤维，可直接作为防爆装甲或跌落吸能骨架。"}},
            {{"range": "> 15%", "consequence": "可能引发严重的模量衰减，在受力后产生不可逆塑性变形，精密机器人领域严禁使用。"}}
          ]
        }},
        {{
          "parameter": "吸湿/热变性预设区间 (特种大分子常见盲区)",
          "scenarios": [
            {{"range": "强极性溶剂中超收缩", "consequence": "若遇水/湿气发生超过5%的结构收缩，必须采用全封闭树脂基体包裹，禁止裸露使用。"}},
            {{"range": "Tg (非晶区玻璃化温度) < 80°C", "consequence": "电机附近等中温区需做隔热处理，否则模量呈断崖式下跌。"}}]
        }}
      ],
      "system_level_impact": {{
        "component_level": "机械臂大臂管材减重 65% (等刚度前提下)",
        "macro_effects": [
          {{"indicator": "末端有效载荷 (Payload)", "improvement": "+ 18%", "justification": "因大臂自重减少，关节电机输出扭矩的无效占用降低18%。"}},
          {{"indicator": "高速抑震响应 (Settling Time)", "improvement": "- 12%", "justification": "纤维的高阻尼特性结合低惯量，使末端到位后的残余震荡时间缩短。"}},
          {{"indicator": "综合能耗 (Power Consumption)", "improvement": "- 22%", "justification": "动态加减速过程中的惯性力大幅下降，直接降低峰值电流。"}}]
      }},
      "real_world_case": {{
        "image_keyword": "Robotic Arm Carbon Fiber",
        "title": "某型 10kg 级协作机械臂底座至大臂段升级方案",
        "description": "原采用铸铝合金。换用该材料长丝缠绕工艺后，需注意纤维铺层角度需采用 [0/±45/90] 混编以弥补径向刚度不足。最终系统减重带来电机规格可降一档，BOM成本理论上可对冲新材料溢价。"
      }},
      "conclusion_data_string": "综合推演：本征比强度超越基准 3.9 倍，但在整机系统中，受制于模量需进行几何补偿，最终系统级轻量化净收益为 40%-55%。需重点防范吸水塑化风险。"
    }}
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    API_URL = API_URL.encode('ascii', 'ignore').decode('ascii').strip()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key.strip()}"}
    payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system_prompt}], "temperature": 0.2}

    with st.spinner("算力引擎正在进行缺失参数扫掠与整机效能换算..."):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=100)
            response.raise_for_status()
            clean_json_str = response.json()['choices'][0]['message']['content'].replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json_str)
            
            st.success("✅ 全景系统级推演完成。")
            
            # ================= I. 基础指标矩阵 =================
            st.subheader("I. 多维本征指标与系统级映射")
            c_radar, c_bar = st.columns([1, 2])
            with c_radar:
                df_radar = pd.DataFrame(dict(r=list(data['radar_score'].values()), theta=list(data['radar_score'].keys())))
                fig_radar = px.line_polar(df_radar, r='r', theta='theta', line_close=True, height=320)
                fig_radar.update_traces(fill='toself', line_color='#ff4b4b')
                st.plotly_chart(fig_radar, use_container_width=True)
            with c_bar:
                st.markdown("##### 核心指标跨维打击力度")
                for metric in data['multi_dimensional_data']:
                    df_m = pd.DataFrame({"方案": [metric['baseline_name'], "输入材料"], "数值": [metric['baseline_val'], metric['new_val']]})
                    fig = px.bar(df_m, x="数值", y="方案", orientation='h', color="方案", text_auto='.2s', height=140,
                                 color_discrete_map={metric['baseline_name']: "#5a6e7f", "输入材料": "#ff4b4b"})
                    fig.update_layout(title=metric['metric'], showlegend=False, margin=dict(l=10, r=10, t=30, b=10))
                    st.plotly_chart(fig, use_container_width=True)

            st.divider()

            # ================= II. 缺失参数区间扫掠 (重头戏) =================
            st.subheader("II. 缺失参数敏感性扫掠矩阵 (Parameter Sweep Analysis)")
            st.caption("针对未测定或易波动的关键环境/力学指标，系统强制展开多区间推演。")
            
            sweeps = data.get("missing_data_sweep", [])
            for sweep in sweeps:
                st.markdown(f"#### 🔎 扫掠参数：`{sweep['parameter']}`")
                cols = st.columns(len(sweep['scenarios']))
                for i, scene in enumerate(sweep['scenarios']):
                    with cols[i]:
                        with st.container(border=True):
                            st.info(f"**设定区间:** {scene['range']}")
                            st.write(scene['consequence'])

            st.divider()

            # ================= III. 整机宏观效能折算 =================
            st.subheader(f"III. {domain} 整机系统级效能折算")
            sys_impact = data.get("system_level_impact", {})
            st.markdown(f"**基础前提：** `{sys_impact.get('component_level')}`")
            
            # 使用指标卡片展示整机提升
            effects = sys_impact.get('macro_effects', [])
            e_cols = st.columns(len(effects))
            for i, effect in enumerate(effects):
                with e_cols[i]:
                    st.metric(label=effect['indicator'], value=effect['improvement'])
                    st.caption(effect['justification'])

            st.divider()

            # ================= IV. 实景案例映射 =================
            st.subheader("IV. 商业级工程实景映射")
            case = data.get("real_world_case", {})
            
            img_col, txt_col = st.columns([1, 1.5])
            with img_col:
                # 动态生成占位工业配图，使用者对其产生直观概念
                keyword = urllib.parse.quote(case.get('image_keyword', 'Engineering'))
                # 使用 placehold.co 结合关键字生成专业占位图，实际项目中可替换为本地数据库图片
                img_url = f"https://placehold.co/600x400/2c3e50/ecf0f1?text={keyword}"
                st.image(img_url, caption="工程部件概念图 (占位)")
            with txt_col:
                st.markdown(f"#### {case.get('title')}")
                st.markdown(case.get('description'))
                st.info(data.get('conclusion_data_string'))

        except Exception as e:
            st.error(f"引擎计算出错: {str(e)}")
