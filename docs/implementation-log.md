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

### 10. Phase 1 可信数字基础设施（2026-05-12）

设计：`docs/superpowers/specs/2026-05-12-phase1-trustworthy-numbers-design.md`
实现 plan：`docs/superpowers/plans/2026-05-12-phase1-trustworthy-numbers.md`
分支：`feature/phase1-trustworthy-numbers`（18 个 commit，全套 TDD）

完成内容：

- 新增 `material_eval/uncertainty.py`：三点区间值对象 `Interval`（含 `__add/__sub/__mul/__truediv/__pow__` 区间算术、端点穷举、零穿越除法拒绝、混合符号偶数次幂归零修复）；异常类 `IntervalError`/`NegativeWidthError`/`UnitMismatchError`；常量 `CONFIDENCE_SPREAD`；适用域校验值对象 `EnvelopeSpec` / `EnvelopeReport` / `Violation` 覆盖 6 轴（temperature_C/humidity_pct/stress_MPa/strain_rate_1_per_s/fatigue_cycles/thickness_mm）。
- 新增 `material_eval/conditions.py`：`Quantity` / `Condition` Pydantic v2 模型，单位归一化统一入口，`envelope_axes()` 直接对接 `EnvelopeSpec.check()`。
- 扩展 `material_eval/units.py`：`normalize_quantity()` 入口覆盖长度/力/力矩/应力/温度/湿度/应变率。
- 升级 `material_property_library.py`：
  - `_build_observation` 同时解析单点 `"value": 1.8` 和三点 `"value": {"low":..., "typical":..., "high":...}`。
  - 单点经 confidence 自动展开（high=±5%, medium=±15%, low=±30%）。
  - 多观察聚合：low=min, high=max, typical=highest-confidence。
  - 新增 `property_interval()` / `envelope_for()` API。
- 升级 `materials.py`：`MaterialCandidate` 三个属性字段 `float → Interval`，`specific_strength/modulus` 重命名为 `_typical` 系列。
- 升级 `computation.py` / `section_analysis.py` / `laminates.py`：5 个 `_calculate_*` 函数全部用区间算术；`Metric.value` 和 `SectionProperties` 字段升级为 Interval；`LaminateResult` 字段类型对齐 Interval（Phase 1 输出零宽，Phase 2 失效准则会赋予真实区间）。
- 升级 `scoring.py`：新增 `score_data_confidence(intervals)` 用相对宽度驱动数据可信度；`score_condition_risk(envelope, condition)` 用 envelope 余量驱动工况风险。
- 升级 `report_schema.py`：新增 `IntervalPayload` / `ViolationPayload` / `EnvelopeReportPayload`，扩展 `ClaimBinding` 和 `StructuredReport`。
- 升级 `evaluation.py`：`EvaluationRequest` 新增 `condition` / `material_envelope` 两个可选字段，`run_evaluation` 短路返回 `EnvelopeRefusal`（材料适用域越界时不出数）。
- 升级 `reporting.py`：所有指标渲染从 `value.typical:.4g` 切换到 `value.format()`（三档精度自动）；Markdown 新增 "工况包络校验" 章节（列出每条轴 ✓/✗）和 "不确定度说明" 静态文案；新增 `build_refusal_report()` 输出独立的拒绝报告 markdown。
- 升级 `storage.py`：新增 `append_refusal_log()` 写 `data/refusal_log.jsonl`（refusal 不污染主 evaluation_runs 表）。
- 升级 `ui_streamlit.py`：`run_app()` 处理 `EnvelopeRefusal` 路径（红底 banner + refusal markdown + 不展示任何图表/评分）；`render_material_summary` 显示材料的"适用域声明状态"和"区间数据状态"徽标；`render_sidebar` 自动注入材料 envelope 到 EvaluationRequest。
- 升级 5 核心材料 seed（`aluminum_7075_t6` / `ti_6al_4v` / `peek_cf30` / `pa66_gf30` / `kevlar_aramid_fiber`）：每个材料 3 条核心属性观察从单点改三点（±5% 或 ±10% 按 confidence）；每个材料加 `envelope`（temperature/humidity/stress/thickness 4 轴，源标注"engineering default, needs supplier confirmation"）；其他 7 个材料保持单点占位。
- 新增 `tests/test_phase1_smoke.py`：MVP 3 真实场景 × in/out-of-envelope 端到端 6 个 case 全绿。

**测试基线**：155 unittest 全绿（原 50 + 新增 105）。验收命令：
```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python -m compileall material_eval app.py tests
```

### 11. Phase 2 失效准则 + Refusal 导航（2026-05-12）

设计：`docs/superpowers/specs/2026-05-12-phase2-failure-criteria-design.md`
实现 plan：`docs/superpowers/plans/2026-05-12-phase2-failure-criteria.md`
分支：`feature/phase2-failure-criteria`（13 个 commit）

让 MVP 评估闭环：从"能算多少"升级到"能不能用"。

**Track A — 失效准则**：
- 新增 `material_eval/strength.py`：`StrengthAllowables`（含 yield_mpa / Xt/Xc/Yt/Yc/S/f12_star）、`SafetyFactor`、`SafetyReport`（三档 status：pass≥1.5 / marginal≥1.0 / fail<1.0）
- 新增 `material_eval/stress_analysis.py`：`isotropic_stress_field`（BEAM/I_BEAM/PLATE/STRAP 反向算应力）+ `ply_stress_field`（CLT 反算每层主轴应力）
- 新增 `material_eval/failure_criteria.py`：`von_mises_safety_factor`（金属/塑料）+ `tsai_wu_safety_factor`（复合材料，f12_star 可在 seed override）+ `laminate_safety_factor`
- 升级 `material_property_library.py`：解析 `strength_allowables` 顶层字段，新增 `allowables_for()` API；保留向后兼容（旧 seed 仍可读）

**Track B — Refusal 建设性出口**：
- 新增 `material_eval/alternatives.py`：`suggest_alternatives_for()` 从库反查 envelope 覆盖当前工况的材料；`missing_data_hints()` 生成中文缺失数据清单
- 升级 `evaluation.py`：refusal 分支自动注入替代材料 + 缺失数据提示
- 升级 `reporting.py`：`build_refusal_report` 已在 Phase 1 实现，Phase 2 复用并自动接 alternatives

**集成**：
- `EvaluationRequest` 新增 `strength_allowables` / `material_id`；`EvaluationDraft` 新增 `safety_report`
- `run_evaluation` 在 calculate_part 之后自动分发 Tsai-Wu（laminate + orthotropic）或 von Mises（其他）；无 allowables 时跳过（向后兼容）
- `reporting.build_internal_report` 新增 "安全性评估" markdown 章节，含 SF 区间表格、pass/marginal/fail 图标、Tsai-Wu 时 f12_star 备注
- `ui_streamlit.py` 工况输入区加 axial_force / bending_moment 两组数值 + 单位下拉，新增 "安全性评估" tab 渲染 SafetyReport
- Seed 升级 3 材料：`ti_6al_4v`（yield_mpa）/ `pa66_gf30`（yield_mpa）/ `carbon_epoxy_quasi_iso`（Xt/Xc/Yt/Yc/S/f12_star=0）

**端到端验证**：`tests/test_phase2_smoke.py` 4 个场景全过：
1. Ti-6Al-4V 骨架 BEAM + 10kN axial + 50 N·m bending → von Mises pass（SF ~19.4）
2. PA66-GF30 外壳 PLATE + 2kN + 10 N·m → von Mises（SF ~1.09，marginal）
3. Kevlar 助力带 STRAP + 5kN（无 allowables）→ safety_report=None 优雅降级
4. Carbon-Epoxy 4 层 [0/90/90/0] laminate + 1kN axial → Tsai-Wu method，4 个 PlyStress factors

**关键工程决策（专家判断锁定）**：
- F12 默认 `f12_star = 0`（即 Tsai-Hill 退化），seed 可 override 到 [-1, +1]——经典 F12 公式对未知体系可能非物理，保守取 0
- CLT 仅处理面内拉伸（M_x 弯矩留 Phase 3）
- SF 阈值：pass ≥ 1.5（含不确定度下界仍有 50% 安全余量）/ marginal ∈ [1.0, 1.5) / fail < 1.0
- Kevlar 不需要单独 allowables，复用 Phase 1 已有的 `material.tensile_strength_mpa` 自动 fallback

**测试基线**：218 unittest 全绿（Phase 1 的 155 + 新增 63）。

### 12. GitHub 交接整理（2026-05-16）

- 新增 `docs/HANDOFF.md`，作为下一位接手者的 30 分钟交接指南。
- 更新 `README.md`：
  - 增加“给接手者的入口”。
  - 补齐 Phase 1/2 后新增模块地图。
  - 修正当前边界：CLT/Tsai-Wu 已接入，但 Hashin、面外弯矩、屈曲、疲劳、真实 CAE 仍待做。
  - 补充 refusal、安全性评估、scorecard 等已接入能力。
- 交接发布前应确认 `main` 分支 clean、测试通过，并推送到 GitHub `origin/main`。

## 新发现

- 材料属性不能只存一个数字。不同牌号、工艺、方向、温湿度会导致巨大差异，因此 seed 数据必须标注为"典型工程参考/需复核"，不能包装成已认证事实。
- 当前知识库只有 4 个内部种子文档，RAG 默认问题集能命中，但数据量远低于 PRD 里提到的 50 条证据卡目标。
- 当前 CLT 已可用于铺层初筛，但还没有失效准则，如 Tsai-Hill/Tsai-Wu/Hashin。
- 当前报告已经进入 claim 级引用绑定第一版，但绑定粒度仍偏粗，后续要把"具体句子/具体证据片段/具体计算变量"绑定得更细。
- Phase 1 新发现：
  - 区间宽度对评分影响显著。`CONFIDENCE_SPREAD = (0.7→5%, 0.5→15%, 0→30%)` 是工程默认占位，**需要业务专家用真实实验数据校准**——否则"数据可信度"分数会受这个常量主导。
  - 越界硬拒绝（refusal 路径）在 6 个 smoke case 上行为良好。但 refusal 当前只列违规轴；plan 中的"建议替代材料 / 缺失数据清单"两个建设性出口还没填充，后续按真实评估积累 refusal_log 后补。
  - 5 核心材料的 envelope 全部标 `source = "engineering default, needs supplier confirmation"`——MVP 上线前业务方必须复核。
  - `LaminateResult` 字段虽然类型升级为 `Interval`，但因 Lamina 输入是 float，所有铺层结果当前都是零宽区间。Phase 2 引入失效准则时才会获得真实区间。
- 单位系统已经覆盖几何/载荷/温度/湿度/应变率（Phase 1 完成），但疲劳/冲击工况仍未纳入。
- 透明评分卡已经可读，但评分权重仍是工程默认值，需要业务专家用历史项目和真实实验结果校准。

## 下一步（Phase 3 候选）

**Phase 1 + Phase 2 已完成纯架构性优化**。剩余候选大多需要外部输入（真实数据、业务专家）或属于持续运营工作：

1. **Hashin 分模式失效准则** —— Tsai-Wu 给一个总判定，Hashin 区分 fiber tensile / fiber compressive / matrix tensile / matrix compressive，让报告能讲清楚"谁先坏"。依赖 Phase 2 的 PlyStress 和 strength_allowables。**纯架构**。
2. **CLT 面外弯矩 M_x** —— Phase 2 红线限定面内拉伸；扩展到 M_x 让 CLT 支持完整 [N, M] 工况。需要 D 矩阵（弯曲刚度）实现。**纯架构**。
3. **屈曲分析** —— 柱屈曲（欧拉公式）和板屈曲（薄板临界载荷）。**纯架构**。
4. **疲劳分析** —— S-N 曲线 + Miner 损伤累积；需要工况里的循环数（Phase 1 已有 fatigue_cycles 字段）。**需要材料 S-N 数据**。
5. **F12 / CONFIDENCE_SPREAD / 评分卡权重的实验校准** —— **需要真实实验数据或业务专家输入**，不能纯架构推。
6. **Claim binding 句子级 / 计算变量级** —— 报告每条结论绑定到具体证据片段或计算变量。**纯架构**。
7. **扩充知识库 / 材料属性库** —— 把 seed 占位逐步替换为内部实验/供应商/标准来源数据。**持续运营工作**。

**推荐 Phase 3 优先级**（如果继续）：Hashin（1）+ Claim binding（6）—— 都是纯架构推动 + 真正提升科学严谨度的可追溯性。其余建议等真实使用反馈再决定。

## 交接验证命令

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m unittest tests.test_units tests.test_material_property_library -v
.venv/bin/python -m unittest tests.test_report_schema -v
.venv/bin/python -m unittest tests.test_scoring -v
.venv/bin/python -m compileall material_eval app.py tests
NO_PROXY='*' curl -I http://127.0.0.1:8501
```
