# Phase 1 设计：可信数字基础设施

- 日期：2026-05-12
- 范围：材料评估 MVP 的"科学严谨性"第一阶段
- 状态：设计已审核，待写实现 plan

## 1. 目标与非目标

### 目标

让现有评估在"它能算的范围内绝不撒谎"——所有数值结果带不确定度区间，所有计算前先校验工况是否在材料适用域内。

**完成定义（DoD）**：
1. 全量 `unittest` 绿；新模块测试覆盖率 ≥ 90%。
2. MVP 首测 3 个场景每个跑通 2 个 case（一个 in-envelope、一个 out-of-envelope），人工核对报告与预期一致。
3. 5–6 个核心材料的 `envelope` 和三点区间已 seed 完成并经过研发负责人 review。
4. `docs/implementation-log.md` 增加 Phase 1 完成记录。

### 非目标（Phase 1 不做，留到 Phase 2）

- 复合材料失效准则（Tsai-Hill / Tsai-Wu / Hashin）
- Claim 句子级 / 计算变量级细粒度绑定
- Monte Carlo 不确定度传播
- 评分卡权重的历史项目校准
- 知识库 / 材料库内容扩充（这是持续工作，不阻塞本期）
- CI / 部署 / 结构化日志（独立工程化迭代）

## 2. 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 不确定度表达 | 三点区间 `(low, typical, high)` | 工程报告习惯；不假设分布；与现有 `confidence` 字段自然衔接；MVP 复杂度合适 |
| 越界处理 | 硬拒绝出数 + 解释原因 | 工程类工具的可信度依赖"不撒谎"；带告警照常出数会让用户养成忽略告警的习惯 |
| 数据迁移 | 核心 5–6 材料完整升级，其余兼容占位 | 避免一次性改 ~150 字段卡住进度；UI 明示哪些材料是经过校准的 |
| 不引入新依赖 | 复用 Pint / Pydantic | 不上 Monte Carlo 就不上 numpy 增项；区间算术自实现 |

## 3. 模块设计

### 3.1 `material_eval/uncertainty.py`（新增）

#### `Interval` 值对象

```python
@dataclass(frozen=True)
class Interval:
    low: float
    typical: float
    high: float
    unit: str  # canonical unit string
```

- 不变量：`low <= typical <= high`，构造时校验，违反抛 `IntervalError`。
- 工厂方法：
  - `Interval.point(value, unit)` → 零宽区间，用于精确输入（如几何标称尺寸）。
  - `Interval.from_confidence(value, unit, confidence)` → 按 `confidence ∈ {high, medium, low}` 自动取 `±5% / ±15% / ±30%`。具体百分比写在常量 `CONFIDENCE_SPREAD`，标注"工程默认，待业务专家校准"。
- 算术：`__add__`, `__sub__`, `__mul__`, `__truediv__`, `__pow__(int)`（单调）。
- 非单调表达式走 `Interval.safe_eval(fn, *intervals)`：端点穷举 + 一阶导符号变化检测；检测到符号变化 → 退化为加宽区间，并设置 `widened: bool = True` 标记。
- 单位兼容：操作两个 Interval 时单位必须匹配（canonical 形式），否则抛 `UnitMismatchError`。
- 渲染：`format(precision_rule)` 按数量级自动选择精度（>1000 取整、0.1–1000 三位有效、<0.1 科学计数）。

#### `EnvelopeSpec` 值对象

```python
@dataclass(frozen=True)
class EnvelopeSpec:
    temperature_C:        tuple[float, float] | None = None
    humidity_pct:         tuple[float, float] | None = None
    stress_MPa:           tuple[float, float] | None = None
    strain_rate_1_per_s:  tuple[float, float] | None = None
    fatigue_cycles:       tuple[float, float] | None = None
    thickness_mm:         tuple[float, float] | None = None
    source: str | None = None  # "supplier datasheet" / "internal test" / "engineering default"
```

- `check(condition: Condition) -> EnvelopeReport`：对每个非 None 字段比对 condition 中对应输入；产生 `list[Violation]`，每条带 `(axis, input_value, allowed_range, source)`。
- 全部字段 None 时 `check` 永远 pass，但 `EnvelopeReport.has_declared_envelope = False`，UI/报告会显式提示"未声明适用域"。

#### 异常

- `IntervalError`（基类），子类：`NegativeWidthError`, `UnitMismatchError`。

#### 测试（`tests/test_uncertainty.py`）

- 构造校验（合法 / `low > typical` / `typical > high`）。
- 各运算符的单调与非单调样例（含 `safe_eval` 退化路径）。
- `from_confidence` 三档比例。
- `EnvelopeSpec.check`：6 个字段每个的 in/边界等于/越界三种情况；空 envelope 行为。

### 3.2 `material_eval/units.py`（扩展）

- Pint 注册表扩展到下列维度，均提供常用单位别名：
  - 长度（m, mm, cm, in）
  - 力（N, kN, lbf）
  - 力矩（N·m）
  - 压强 / 应力（Pa, kPa, MPa, GPa, psi, N/mm²）
  - 温度（°C, K）—— 注意温度是仿射单位，不能与其他量纲互乘
  - 湿度（%RH，dimensionless 标签）
  - 应变率（1/s）
  - 循环数（dimensionless，含千/兆后缀）
- 统一入口 `normalize_quantity(value, unit, target_dimension) -> (canonical_value, canonical_unit)`。
- 现有材料属性归一化函数重构为复用该入口（不改变行为）。

#### 测试（`tests/test_units.py` 扩展）

- 每个新维度的至少 2 个跨单位等价 case。
- 温度仿射性的边界行为（不允许 `°C * 2` 直接运算）。

### 3.3 `material_eval/conditions.py`（新增）

#### `Condition` Pydantic 模型

```python
class Condition(BaseModel):
    # 几何
    length:     Quantity | None = None
    width:      Quantity | None = None
    thickness:  Quantity | None = None
    outer_diameter: Quantity | None = None
    inner_diameter: Quantity | None = None
    # 载荷
    axial_force:    Quantity | None = None
    bending_moment: Quantity | None = None
    pressure:       Quantity | None = None
    # 环境
    temperature: Quantity | None = None
    humidity:    Quantity | None = None
    # 寿命
    fatigue_cycles:   float | None = None
    strain_rate:      Quantity | None = None
```

- 构造时即调用 `units.normalize_quantity()` 把每个字段转 canonical。
- `Quantity` 是 `(value: float, unit: str)` 的 Pydantic 包装，序列化/反序列化稳定。
- 取代当前 `dimensions: dict[str, float]` 这种"裸 dict + 隐式单位"用法；旧调用点改造列在 §5。

#### 测试（`tests/test_conditions.py`）

- 多单位输入归一化后等价。
- 缺失字段（None）传递行为。
- 非法单位 / 量纲不匹配抛清晰错误。

### 3.4 `material_eval/material_property_library.py`（改造）

- Seed JSON 升级：每条属性观察 `value` 字段从单点 → `{low, typical, high}`，单位字段不变；读取时优先解析新结构，遇到旧单点值自动转 `low=typical=high`（**向后兼容**）。
- 新增可选顶层字段 `envelope`，结构对应 `EnvelopeSpec`。
- `build_candidate()` 输出的材料属性已是 `Interval`（不再是 float）。
- 调用方（`materials.py`, `computation.py`）需要同步改造，见 §3.5。

#### 测试（`tests/test_material_property_library.py` 扩展）

- 旧单点 seed 与新区间 seed 均正确解析。
- `envelope` 缺省解析为 `None`，且 `EnvelopeReport.has_declared_envelope = False`。

### 3.5 `material_eval/computation.py` / `laminates.py`（改造）

- `CalculationResult` / `LaminateResult` 的每个标量数值字段类型从 `float` → `Interval`。
- 计算函数内部使用 Interval 算术；当输入是零宽区间时输出仍是零宽，行为与现版一致 → 现有非区间用例不需要改测试期望。
- 函数签名稳定，外部调用方不需要改。
- 截面分析适配器 `section_analysis.py`：`sectionproperties` 返回单点数值，包装为零宽 Interval。

#### 测试（`tests/test_computation.py`, `test_laminates.py` 扩展）

- 现有用例：把材料属性改为 `Interval.point(...)`，期望值不变。
- 新增：材料属性带宽度时，输出区间宽度符合预期（手算可验证的简单 case，如纯拉伸应力 = F/A）。

### 3.6 `material_eval/evaluation.py`（改造）

`run_evaluation` 流程改为：

```python
def run_evaluation(request: EvaluationRequest) -> EvaluationDraft | EnvelopeRefusal:
    envelope_report = validate_envelope(request.material, request.condition)
    if envelope_report.violations:
        return EnvelopeRefusal(
            material=request.material,
            part=request.part,
            condition=request.condition,
            envelope_report=envelope_report,
            alternative_materials=suggest_alternatives(request.part, request.condition),
            missing_data=missing_data_hints(request.material, envelope_report),
        )
    calculation     = calculate_part(request.part, request.material, request.condition)
    laminate_result = analyze_laminate(request.laminate_stack) if request.laminate_stack else None
    evidence_cards  = search_evidence(...)
    report          = build_internal_report(...)
    save_run(...)  # 仅 in-envelope case 写主记录；refusal 只记录尝试，不存评估结果
    return EvaluationDraft(...)
```

- `EnvelopeRefusal` 是新数据类型，UI/Storage 分别处理。
- `EvaluationRequest.dimensions: dict[str, float]` 替换为 `condition: Condition`；调用方（UI、tests）需要同步改造。
- `suggest_alternatives()`：从 catalog 按 `envelope.check(condition).violations==[]` 反查同类零部件可用材料，取前 3。
- `missing_data_hints()`：列出该材料中"如果想覆盖此工况需要补的属性"。

### 3.7 `material_eval/scoring.py`（改造）

- "数据可信度"维度：自动消费各关键结果的 Interval 相对宽度 `w = (high-low) / |typical|`。映射：`w<0.1 → 1.0`, `0.1≤w<0.3 → 0.7`, `0.3≤w<0.6 → 0.4`, `w≥0.6 → 0.1`。
- "工况风险可控性"维度：消费"距离 envelope 边界的最小余量比"。映射阈值同上反向。
- 其他维度暂保持现状。

#### 测试（`tests/test_scoring.py` 扩展）

- 不同区间宽度对应分数变化。
- 越界场景（refusal 路径）不进 scoring（短路前已返回）。

### 3.8 `material_eval/report_schema.py`（扩展）

- `ClaimBinding` 新增可选字段 `interval: IntervalPayload | None`，`IntervalPayload = {low, typical, high, unit}`。
- 新增 `EnvelopeViolationPayload` 和 `StructuredReport.envelope_report: EnvelopeReportPayload | None`。

### 3.9 `material_eval/reporting.py`（改造）

- 数值渲染从 `f"{x:.1f}"` 全面切到 `interval.format(precision_rule)`。
- 新增章节"工况包络校验"：每条轴 `输入值 / 允许范围 / 数据来源 / 状态`。
- 新增章节"不确定度说明"：列出主导每个关键结果区间宽度的输入属性，提示"想收窄区间该补哪个数据"。
- 越界路径：`build_refusal_report(refusal: EnvelopeRefusal) -> RefusalReport`，主体为
  - 明确句"**未出具评估**：因 [轴] 在 [输入值] 超出 [材料] 适用域 [允许范围]"
  - "已知适用该工况的同类材料"表
  - "如要继续评估需要补充的数据"清单

#### 测试（新增 `tests/test_reporting.py`）

- 区间渲染格式快照（>1000 / 0.1–1000 / <0.1 三档）。
- RefusalReport 渲染包含所有必填字段。

### 3.10 `material_eval/ui_streamlit.py`（改造）

- 工况输入区：每个字段一个数值输入 + 一个单位下拉（合法单位列表从 Pint 自动生成）。
- 实时软校验：用户改输入 → 若超出当前选定材料的 envelope → 输入框下方橙色提示。
- 提交后 RefusalReport：页面顶部红底 banner 渲染 refusal 主体，**不展示任何计算图表**。
- 材料库详情：每个材料卡片标注"适用域声明状态"（已声明 / 部分声明 / 未声明）和"区间数据状态"（三点区间 / 单点）。

### 3.11 `material_eval/storage.py`（最小改造）

- `evaluation_runs.payload` JSON 增加 `envelope_report` 段；旧记录读取时缺省解析为 `None`，渲染时显示"该次评估早于 Phase 1，无适用域校验记录"。
- 不引入新表；refusal 不写主表（只记录在审计日志，详情见 §5）。

## 4. 数据流（端到端）

```
UI (Streamlit form, units-aware)
   ↓ 构造 Condition (Pint normalized) + 选择 Material (含 EnvelopeSpec)
EvaluationRequest
   ↓
evaluation.run_evaluation
   ├─ validate_envelope(material, condition)
   │     │
   │     ├─ violations 非空 → EnvelopeRefusal
   │     │        ↓
   │     │   reporting.build_refusal_report → RefusalReport
   │     │        ↓
   │     │   UI 红底 banner（不出图，不写主表）
   │     │
   │     └─ pass →
   │
   ├─ calculate_part (Interval 算术)        →  CalculationResult(Interval)
   ├─ analyze_laminate (Interval 算术)      →  LaminateResult(Interval) | None
   ├─ search_evidence (现状不动)            →  EvidenceCard[]
   ├─ scoring (消费 Interval 宽度)          →  Scorecard
   ├─ build_internal_report (渲染区间+envelope) → ReportDraft
   └─ storage.save_run                     → SQLite
        ↓
UI 完整报告页面
```

## 5. 迁移与兼容

### 5.1 代码层面的破坏性变更

- `EvaluationRequest.dimensions: dict[str, float]` → `condition: Condition`
  - 调用点：`ui_streamlit.py`, `tests/test_evaluation_workflow.py`，可能还有 `legacy/` 下的旧入口（保持旧入口不动，legacy 不在 Phase 1 范围内）
- `CalculationResult` / `LaminateResult` 字段类型变化
  - 任何直接读这些字段做断言的测试都要更新

### 5.2 Seed 数据迁移

- `data/seed/material_property_library.json`：核心 5–6 材料完整升级为三点区间 + envelope；其余材料 `low=typical=high=原值`、`envelope=null`。
- 核心材料的确定由 MVP 首测 3 个场景驱动，待写实现 plan 时具体确认（候选：6061-T6 铝、Ti-6Al-4V、PA66-GF30、PEEK 等典型机器人骨架/穿戴外壳材料）。

### 5.3 SQLite 兼容

- 旧 `evaluation_runs.payload` 缺少 `envelope_report` 段 → 读取时显式默认值，UI 标注"早于 Phase 1"。
- 不需要数据库 migration 脚本。

### 5.4 Refusal 记录

- Phase 1 暂不把 refusal 写入主 evaluation_runs 表，避免污染历史评估查询。
- 新增 `data/refusal_log.jsonl`（追加式 JSON Lines）记录所有 refusal，字段：时间、材料、part、condition、violations。用于后续校准 envelope 阈值。

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 区间算术在复杂复合公式下"爆炸"出过宽区间 | 单测专门覆盖 `safe_eval` 退化路径；报告明确标注 `widened=True` 的指标 |
| 核心 5–6 材料的 envelope 数据本身就缺失 / 不准 | seed 文件中 `source` 字段强制声明（"supplier datasheet" / "internal test" / "engineering default"），UI 显式渲染来源 |
| `confidence → spread` 的百分比是工程默认，可能误导 | 报告"不确定度说明"章节明确标注"区间宽度由 confidence 标签生成，待与业务专家校准"；常量集中在 `CONFIDENCE_SPREAD` 便于将来调整 |
| Streamlit 单位下拉太多选项导致 UI 笨重 | 每个字段只暴露 2–4 个常用单位别名；高级用户可手动键入其他 Pint 合法单位 |
| 越界硬拒绝可能让用户觉得"工具不好用" | UI Refusal 报告必须给出"替代材料 + 缺失数据"两个建设性出口，而不只是说"不行" |

## 7. 验收清单（实现 plan 收尾时逐项核对）

- [ ] 全量 `python3 -m unittest discover -s tests -p 'test_*.py' -v` 全绿
- [ ] 新模块测试覆盖率 ≥ 90%（`uncertainty`, `conditions`, `envelope` 校验）
- [ ] MVP 首测 3 场景 × 2 case（in / out of envelope）人工 review 通过
- [ ] 核心 5–6 材料的 seed 升级完成并经业务方 review
- [ ] `docs/implementation-log.md` 增加 Phase 1 完成记录
- [ ] `legacy/` 与现状一致（不被影响）

## 8. Phase 2 预告（不在本期）

- 复合材料失效准则（Tsai-Hill / Tsai-Wu / Hashin）—— 依赖 Phase 1 的 Interval 与 envelope
- Claim 句子级 / 计算变量级细粒度绑定 —— 依赖 Phase 1 已稳定的计算变量集合
- 评分卡权重的历史项目校准 —— 依赖 Phase 1 落地后积累若干 refusal/run 记录
