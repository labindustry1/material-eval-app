# 材料评估 MVP 实施交接记录

本文档用于让任何接手者快速理解：已经做了什么、下一步做什么、过程中发现了什么。每次推进架构或功能后都需要更新。

## 当前总体状态

- 项目入口：`app.py`，实际 UI 在 `material_eval/ui_streamlit.py`。
- 当前数据库：SQLite，本地文件默认 `data/mvp.sqlite3`。
- 当前运行地址：`http://127.0.0.1:8501`。
- 当前验证基线：全量 `unittest`、`compileall`、Streamlit AppTest、业务 smoke test。

## 已完成

### 1. 原型拆分与 MVP 骨架

- 旧单文件 Streamlit 原型移动到 `legacy/`。
- 核心逻辑拆到 `material_eval/` 包：
  - `catalog.py`
  - `materials.py`
  - `computation.py`
  - `evidence.py`
  - `reporting.py`
  - `storage.py`
  - `ui_streamlit.py`
- 旧行业/零部件配置迁移到 `data/seed/domain_config.json`。

### 2. 证据与 RAG 基础

- 接入 `Docling` 解析 txt/md/html/pdf/docx/pptx。
- 接入 `rank-bm25` 做默认证据召回。
- 接入可选 `BGE-M3` dense embedding 语义检索。
- 新增 SQLite 证据库：
  - `documents`
  - `document_chunks`
  - `chunk_embeddings`
- 增加 RAG 固定问题集评估模块 `rag_eval.py` 并接入页面。

### 3. 工程计算

- BEAM/I_BEAM/PLATE/STRAP 初筛计算从 UI 拆到 `computation.py`。
- 接入 `sectionproperties` 做管、工字梁、矩形截面属性。
- 新增 `laminates.py`，实现 Classical Laminate Theory 的 A 矩阵和等效 Ex/Ey/Gxy 初筛。
- CLT 铺层输入和结果已接入 Streamlit 与报告。

### 4. 报告与复核

- 中文 Markdown 报告生成在 `reporting.py`。
- 可选 OpenAI 润色在 `openai_provider.py`。
- SQLite 增加 `report_reviews`，报告页面可保存研发复核状态和意见。

### 5. 正式版 schema 预留

- 新增 Supabase migration：
  - `supabase/migrations/20260507145720_material_eval_core.sql`
- 包含私有 schema、RLS、pgvector、HNSW 索引、`match_document_chunks` RPC。
- 当前不急着接 Supabase adapter，先保证本地 MVP 准确性。

### 6. 材料属性库第一版

- 新增 `data/seed/material_property_library.json`。
- 新增 `material_eval/material_property_library.py`。
- 当前包含 12 个基准材料、37 条属性观察。
- 每条属性观察包含：
  - property name
  - value
  - unit
  - test condition
  - source type
  - source label
  - confidence
- Streamlit 材料模式新增“从基准材料库选择”。

### 7. 单位系统第一版

- 新增 `material_eval/units.py`。
- 接入开源 `Pint` 做材料物性单位换算和量纲校验。
- 当前支持并归一化：
  - 密度：`kg/m^3`、`g/cm^3` -> `g/cm^3`
  - 强度：`Pa`、`MPa`、`GPa`、`N/mm^2` -> `MPa`
  - 弹性模量：`Pa`、`MPa`、`GPa`、`N/mm^2` -> `GPa`
- 材料属性库读取时保留原始值/单位，同时生成计算用 canonical value/canonical unit。
- `build_candidate()` 已改为使用 canonical value，避免把 `1800 kg/m^3` 误当成 `1800 g/cm^3`。
- Streamlit 材料库详情里会展示原始单位到计算单位的转换。

### 8. 结构化报告与 claim schema 第一版

- 新增 `material_eval/report_schema.py`。
- 接入 `Pydantic` 定义：
  - `StructuredReport`
  - `ReportClaim`
  - `ClaimBinding`
- 每条 claim 必须包含：
  - claim id
  - section
  - claim type
  - confidence
  - bindings
- 当前支持的绑定来源：
  - `calculation_metric`
  - `evidence_card`
  - `laminate_result`
  - `manual_judgement`
- `reporting.py` 已把 structured report 写入 `report_json["structured_report"]`。
- Markdown 报告新增“结构化结论追踪”表，便于研发复核每条判断来自计算、证据还是规则判断。

### 9. 透明评分卡第一版

- 新增 `material_eval/scoring.py`。
- 接入 `Pydantic` 定义：
  - `Scorecard`
  - `ScoreDimension`
- 报告 JSON 新增 `report_json["scorecard"]`。
- Markdown 报告新增“透明评分卡”。
- 当前评分维度：
  - 数据可信度
  - 本征性能潜力
  - 结构适配度
  - 工况风险可控性
  - 工艺成熟度
  - 合规/准入风险
- 当前评分是 MVP 规则模型，目的是解释和排序，不是认证结论；后续需要材料、结构、法规负责人共同校准权重和阈值。

## 新发现

- 材料属性不能只存一个数字。不同牌号、工艺、方向、温湿度会导致巨大差异，因此 seed 数据必须标注为“典型工程参考/需复核”，不能包装成已认证事实。
- 当前知识库只有 4 个内部种子文档，RAG 默认问题集能命中，但数据量远低于 PRD 里提到的 50 条证据卡目标。
- 当前 CLT 已可用于铺层初筛，但还没有失效准则，如 Tsai-Hill/Tsai-Wu/Hashin。
- 当前报告已经进入 claim 级引用绑定第一版，但绑定粒度仍偏粗，后续要把“具体句子/具体证据片段/具体计算变量”绑定得更细。
- 单位系统已经覆盖核心三类物性，但几何尺寸、载荷、温湿度、疲劳/冲击等工况变量还需要继续结构化。
- 透明评分卡已经可读，但评分权重仍是工程默认值，需要业务专家用历史项目和真实实验结果校准。

## 下一步

1. 把 claim binding 从粗粒度来源升级为句子级/证据片段级/计算变量级。
2. 扩充知识库和材料属性库，逐步把 seed 替换为内部实验/供应商/标准来源。
3. 把几何尺寸、载荷、温度、湿度、疲劳/冲击等工况输入纳入单位/边界校验。
4. 增加复合材料失效准则，如 Tsai-Hill/Tsai-Wu/Hashin。
5. 用真实项目/实验结果校准透明评分卡的权重、阈值和解释文案。

## 交接验证命令

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m unittest tests.test_units tests.test_material_property_library -v
.venv/bin/python -m unittest tests.test_report_schema -v
.venv/bin/python -m unittest tests.test_scoring -v
.venv/bin/python -m compileall material_eval app.py tests
NO_PROXY='*' curl -I http://127.0.0.1:8501
```
