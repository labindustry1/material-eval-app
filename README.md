# 材料可行性评估 MVP

这是一个面向内部研发的材料应用可行性初筛 MVP。

旧版 Streamlit 原型已保留在 `legacy/app_legacy_streamlit.py`。当前入口 `app.py` 是重构后的轻量版本，核心业务逻辑拆在 `material_eval/` 包内。

旧版 RAG 和 SQLite demo 连接器也已移动到 `legacy/`，仅作为历史参考，不再被新 MVP 使用。

## 技术栈

- UI：Streamlit
- 本地记录：SQLite 评估记录 + SQLite 证据库/chunk/embedding 缓存
- 种子配置：`data/seed/domain_config.json`
- 基准材料库：`data/seed/material_property_library.json`
- 内部资料：`knowledge_base/` 下的 txt/md/html/pdf/docx/pptx
- 计算：确定性公式模块 + `sectionproperties` 截面分析适配器
- 单位：`Pint` 材料物性单位归一化和量纲校验
- 报告：本地中文 Markdown 生成，可选 OpenAI 润色
- 结构化输出：`Pydantic` 报告/claim/binding schema
- 评分：透明规则化 scorecard，覆盖数据、性能、结构、工况、工艺、合规维度
- 开源解析/检索：`Docling` 解析多格式资料，`rank-bm25` 默认召回，可选 `BGE-M3` dense embedding 语义检索

## 存储路线

当前 MVP 固定使用 SQLite，目的是尽快跑通内部研发评估闭环，降低部署、权限和运维复杂度。

正式上线版本再切换到 Supabase：

- Supabase Postgres：项目、材料、计算结果、证据卡、报告记录
- Supabase Auth：内部研发账号和权限
- Supabase Storage：内部文档、报告附件、后续仿真文件
- pgvector：正式版 RAG/证据语义检索

代码层面会保持 `material_eval/storage.py` 的边界清晰，后续可新增 Supabase storage adapter，不把 Supabase 逻辑混进计算、报告和 UI 模块。

正式版 Supabase schema 草案已放在 `supabase/migrations/20260507145720_material_eval_core.sql`，说明见 `docs/supabase-production-schema.md`。

## 快速启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

如果需要启用 BGE-M3 语义检索，额外安装可选依赖：

```bash
uv pip install '.[bge]'
```

或在普通 pip 环境中安装：

```bash
pip install FlagEmbedding
```

如果需要访问码保护：

```bash
export MVP_ACCESS_CODE="your-code"
streamlit run app.py
```

如果需要 OpenAI 润色报告：

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4.1-mini"
streamlit run app.py
```

不配置 `OPENAI_API_KEY` 时，系统会使用本地确定性中文报告，不影响 MVP 使用。

环境变量示例见 `.env.example`。

## MVP 首测场景

- 人形机器人核心骨架 / 下肢大扭矩管状连杆
- 智能穿戴与柔性外骨骼 / 智能穿戴承力外壳
- 智能穿戴与柔性外骨骼 / 柔性外骨骼助力带

左侧可以关闭“只显示 MVP 首测场景”，查看旧项目迁移来的全部 8 个行业、17 个零部件模板。

## 项目结构

```text
material_eval/
  catalog.py          # 行业/零部件 seed catalog
  materials.py        # 材料候选与复合材料初筛估算
  material_property_library.py # 材料属性、来源、条件、置信度 seed 读取
  units.py            # Pint 单位归一化与量纲校验
  laminates.py        # Classical Laminate Theory 铺层初筛
  computation.py      # BEAM/PLATE/STRAP 等确定性计算模块
  section_analysis.py # sectionproperties 截面几何分析适配器
  ingestion.py        # Docling/纯文本资料解析
  embeddings.py       # BGE-M3 dense embedding 适配器
  evidence_store.py   # SQLite documents/chunks/embeddings 证据库
  evidence.py         # 内部资料检索和证据卡
  rag_eval.py         # 固定问题集检索评估
  evaluation.py       # 评估编排：计算 -> 证据 -> 报告 -> 存储
  reporting.py        # 中文内部研发报告生成
  report_schema.py    # Pydantic 结构化报告、claim 和来源绑定
  scoring.py          # 透明规则化评分卡
  storage.py          # SQLite 评估记录和报告复核
  ui_streamlit.py     # Streamlit 页面表单和渲染
  openai_provider.py  # 可选 OpenAI 润色

data/seed/domain_config.json
knowledge_base/
legacy/
docs/
supabase/migrations/
tests/
```

## 测试

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## 当前边界

- 当前结果是内部研发初筛，不构成量产、认证、准入或客户承诺。
- 当前没有真实 CAE 仿真，图表只是确定性计算结果可视化。
- 复合材料当前只使用线性混合定律，未考虑铺层、界面、孔隙率、疲劳和环境衰减。

## 已接入的开源能力

- `rank-bm25`：用于 `knowledge_base/` 内部资料检索，报告中会显示证据召回方法和分数。
- `Docling`：用于解析 md/html/pdf/docx/pptx 等内部资料，txt 仍走轻量纯文本入口。
- `sectionproperties`：用于管、工字梁、矩形板/带的截面面积与惯性矩计算，失败时回退闭式公式并输出告警。
- `Pint`：用于材料物性单位归一化和量纲校验，避免把 `kg/m^3`、`g/cm^3`、`MPa`、`GPa` 混用后直接进入工程计算。
- `Pydantic`：用于结构化报告、claim 和来源绑定 schema，报告 JSON 已包含 `structured_report`。
- `BGE-M3`：通过 `FlagEmbedding` 可选适配器接入 dense embedding 语义检索；MVP 默认不加载模型，避免启动和部署成本过重。
- SQLite 证据库：`documents`、`document_chunks`、`chunk_embeddings` 已落地，BGE-M3 文档向量会复用缓存。
- Supabase/pgvector schema：已提供正式版 migration，包含私有 schema、RLS、HNSW 向量索引和 `match_document_chunks` RPC。
- CLT 铺层初筛：`laminates.py` 已提供 Classical Laminate Theory 的 A 矩阵和等效 Ex/Ey/Gxy 初筛，并已接入复合材料 UI 和报告。
- RAG 评估集：`rag_eval.py` 可用固定问题集计算检索命中率和检索方法分布，并已接入 Streamlit 检索评估页。
- 报告复核流：评估报告可保存研发复核状态和意见，SQLite/Supabase schema 均已预留。
- 基准材料属性库：已提供 12 个基准材料和 37 条属性观察，包含单位、测试条件、来源标签和置信度，并接入 Streamlit 材料输入；读取时会生成计算用 canonical value/canonical unit。
- 结构化结论追踪：报告中每条 claim 会绑定计算指标、证据卡、铺层结果或人工规则判断。
- 透明评分卡：报告中输出数据可信度、本征性能、结构适配、工况风险、工艺成熟度、合规/准入风险，并写入 JSON。

## 下一批开源能力接入顺序

1. Claim binding 细化：绑定到具体证据片段、计算变量、人工判断记录。
2. `SfePy / CalculiX / OpenRadioss`：接真实仿真 worker。
3. RAG 评估增强：展示失败样本、期望来源、召回来源和方法对比趋势。
4. 报告审核流增强：证据卡人工确认、结论状态和研发复核意见。
5. Supabase adapter：把当前 SQLite repository 切出正式版实现。
