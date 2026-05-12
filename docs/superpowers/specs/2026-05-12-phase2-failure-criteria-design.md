# Phase 2 设计：失效准则 + Refusal 建设性出口

- 日期：2026-05-12
- 范围：在 Phase 1 可信数字基础设施之上，增加"给定载荷算安全系数"的失效分析能力，并把 Phase 1 的越界拒绝路径从断头路升级为带导航的拒绝。
- 状态：设计已审核，待写实现 plan

## 1. 目标与非目标

### 目标

让 MVP 评估闭环：从"能算多少"升级到"能不能用"。

**完成定义（DoD）**：
1. 全量 `unittest` 绿；新增 ~25–30 测试，总数 ≥ 180。
2. 3 个 MVP 场景每个可以输入"反向载荷"得到 SafetyReport，含安全系数区间、主导失效模式、pass/marginal/fail 标记。
3. 越界 refusal 自动给出"建议替代材料 ≥ 1 条"和"缺失数据清单 ≥ 1 条"。
4. `docs/implementation-log.md` 新增 Phase 2 完成记录。

### 非目标（Phase 2 不做，留到 Phase 3+）

- Hashin 分模式失效准则
- 屈曲、疲劳、热应力分析
- 用真实实验数据校准 `F12` 耦合 / `CONFIDENCE_SPREAD` / 评分卡权重
- 把 `strength_allowables` 推广到全部 12 个材料（本期只补 3 个 MVP 场景所需材料）
- 优化 `suggest_alternatives_for` 的排序算法

## 2. 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 失效覆盖材料类型 | 复合材料（Tsai-Wu）+ 各向同性金属/塑料（von Mises） | MVP 3 场景全覆盖（Ti-6Al-4V / PA66-GF30 / Kevlar）；Hashin 留 Phase 3 |
| 输入模型 | 反向：用户输入载荷，输出 SF 区间 | 工程师真使用场景是"知道设计载荷，验证安全"；正向只能给材料极限，不闭环 |
| 各向同性强度优先级 | `yield_mpa` 优先，回退到 `tensile_strength_mpa` | 工程默认；屈服比极限更保守 |
| Tsai-Wu 耦合 F12 | 工程默认 `-1/(2*sqrt(Xt*Xc*Yt*Yc))` | 文献保守做法；与 `CONFIDENCE_SPREAD` 一样性质，标注"待业务专家校准" |
| 区间算术 | 复用 Phase 1 `Interval` + 端点穷举 | Quadratic 求根 4 端点组合，SF 区间取 min/max |
| Refusal 替代材料策略 | 只查 envelope 覆盖，不算载荷可行性 | 避免循环逻辑；让用户自己做下一步 |
| Seed 升级范围 | 仅 3 材料：ti_6al_4v / pa66_gf30 / carbon_epoxy_quasi_iso | 覆盖 MVP；其余跳过失效分析（向后兼容） |

## 3. 模块设计

### 3.1 `material_eval/strength.py`（新增）

#### `StrengthAllowables` 值对象

```python
@dataclass(frozen=True)
class StrengthAllowables:
    """许用强度，每个材料可选填一组。"""
    # 各向同性
    yield_mpa: Interval | None = None

    # 正交各向异性（复合材料单层）
    Xt_mpa: Interval | None = None   # 纵向拉伸
    Xc_mpa: Interval | None = None   # 纵向压缩（取正值）
    Yt_mpa: Interval | None = None   # 横向拉伸
    Yc_mpa: Interval | None = None   # 横向压缩
    S_mpa:  Interval | None = None   # 面内剪切

    source: str | None = None        # "supplier datasheet" / "MMPDS handbook" / "engineering default"

    def has_isotropic(self) -> bool:
        return self.yield_mpa is not None

    def has_orthotropic(self) -> bool:
        return all(getattr(self, k) is not None for k in ("Xt_mpa", "Xc_mpa", "Yt_mpa", "Yc_mpa", "S_mpa"))
```

#### `SafetyFactor` 数据类

```python
@dataclass(frozen=True)
class SafetyFactor:
    value: Interval                  # >1 安全，<1 失效
    pass_at_typical: bool            # value.typical >= 1.0
    dominant_mode: str               # e.g. "yield" / "tsai_wu_combined" / "fiber_tensile"
    criterion: str                   # "von_mises" / "tsai_wu"
    location: str                    # e.g. "BEAM/root_top" / "ply_0_at_+t/2"
    notes: tuple[str, ...] = ()
```

#### `SafetyReport` 聚合

```python
@dataclass(frozen=True)
class SafetyReport:
    factors: tuple[SafetyFactor, ...]
    governing_index: int             # factors 中 SF.value.typical 最低的索引
    method: str                      # 方法标签

    @property
    def governing(self) -> SafetyFactor:
        return self.factors[self.governing_index]

    @property
    def passed(self) -> bool:
        return self.governing.pass_at_typical and self.governing.value.low >= 1.0
```

`passed` 严格要求"典型通过 + 区间下界仍通过"——任一不满足就 marginal/fail。

### 3.2 `material_eval/stress_analysis.py`（新增）

#### 各向同性反向应力

```python
def isotropic_stress_field(
    part: PartTemplate,
    material: MaterialCandidate,
    condition: Condition,
) -> dict[str, Interval]:
    """根据 part topology + 施加载荷返回评估点应力 Interval（MPa）。

    BEAM:
        axial = F / A
        bending_top    = M * (d/2) / I
        bending_bottom = -M * (d/2) / I
        von_mises_root = sqrt(axial^2 + 3*tau^2) 等价化简
    PLATE:
        membrane = F / (w * t)
        bending  = 6 * M / (w * t^2)
    STRAP:
        tensile = F / A
    I_BEAM: 类似 BEAM
    """
```

返回 dict 键命名规则：`"位置/类型"`，方便 SafetyFactor.location 直接引用。

#### CLT 反向应力（复合材料）

```python
@dataclass(frozen=True)
class PlyStress:
    ply_index: int
    sigma_11: Interval   # 沿纤维主轴
    sigma_22: Interval   # 垂直纤维
    tau_12:   Interval   # 面内剪切

def ply_stress_field(
    stack: LaminateStack,
    condition: Condition,
) -> tuple[PlyStress, ...]:
    """CLT 反算每层主轴应力。

    流程：
      1. 将 axial_force / bending_moment / pressure 折算为面内合力 N_x/N_y/N_xy
         （Phase 2 简化：仅处理面内拉伸，N_y=N_xy=0；二次扩展再加 bending 引起的 M_x）
      2. 中面应变 ε⁰ = A^-1 · N
      3. 每层主轴应变 ε_local = T_strain · ε⁰
      4. 每层主轴应力 σ_local = Q · ε_local
    Q 复用 laminates._reduced_stiffness（已存在，输入是 float，输出包装 Interval.point）
    A 矩阵已是 float（laminates 内部计算）；本期 Phase 2 不引入区间 A 矩阵
      —— SF 区间宽度由 strength_allowables 主导，应力计算保持零宽
    """
```

### 3.3 `material_eval/failure_criteria.py`（新增）

#### von Mises

```python
def von_mises_safety_factor(
    stresses: dict[str, Interval],
    material: MaterialCandidate,
    allowables: StrengthAllowables,
    *,
    location_label: str | None = None,
) -> SafetyFactor:
    """SF = allowable / sigma_vm。

    每个评估点先把该点的应力组分（axial / bending / shear）合成等效 von Mises 应力 sigma_vm_i,
    再在所有评估点中取 sigma_vm_typical 最大的那个作为最危险点；该点的 Interval 用于 SF 区间计算。
    BEAM/I_BEAM 评估点 = {"root_top", "root_bottom"}（axial±bending 组合）
    PLATE 评估点 = {"center"}（membrane + bending）
    STRAP 评估点 = {"section"}
    allowable 优先用 allowables.yield_mpa，缺失则用 material.tensile_strength_mpa。
    Interval 除法用 Phase 1 的 __truediv__；要求 sigma_vm 区间不穿零（零应力情况下 SF=Inf，返回 SafetyFactor(value=Interval.point(999, ""), dominant_mode="no_load", ...) 兜底）。
    """
```

#### Tsai-Wu

```python
def tsai_wu_safety_factor(
    ply_stress: PlyStress,
    allowables: StrengthAllowables,
) -> SafetyFactor:
    """Tsai-Wu 二次型: F1·s1 + F2·s2 + F11·s1² + F22·s2² + F66·tau12² + 2·F12·s1·s2 ≤ 1

    系数：
        F1 = 1/Xt - 1/Xc
        F2 = 1/Yt - 1/Yc
        F11 = 1/(Xt·Xc)
        F22 = 1/(Yt·Yc)
        F66 = 1/S²
        F12 = -1/(2·sqrt(Xt·Xc·Yt·Yc))   # 工程默认耦合，待校准

    SF 通过解 a·SF² + b·SF − 1 = 0 求得：
        a = F11·s1² + F22·s2² + F66·tau12² + 2·F12·s1·s2
        b = F1·s1 + F2·s2
        SF = (-b + sqrt(b² + 4a)) / (2a)   # 取正根
    端点穷举：a 和 b 都是 Interval，对 4 端点组合分别求 SF，取 min/max。
    """

def laminate_safety_factor(
    stack: LaminateStack,
    condition: Condition,
    allowables: StrengthAllowables,
) -> tuple[SafetyFactor, ...]:
    """对每层算 Tsai-Wu，返回 tuple；governing 由调用方根据 SF.value.typical 最小定位。"""
```

### 3.4 `material_eval/alternatives.py`（新增）

#### 替代材料反查

```python
@dataclass(frozen=True)
class AlternativeSuggestion:
    material_id: str
    material_name: str
    category: str
    envelope_source: str | None      # 替代材料 envelope 的数据来源标签

def suggest_alternatives_for(
    condition: Condition,
    part: PartTemplate,
    library: MaterialPropertyLibrary,
    *,
    limit: int = 5,
) -> tuple[AlternativeSuggestion, ...]:
    """从材料库反查 envelope 覆盖当前 condition 的材料。

    规则：
      - 跳过 envelope=None 的材料（未声明）
      - 跳过原材料本身
      - 按 (envelope.source != engineering default) 优先 + category 与 part.topology 匹配粗排
      - 截断到 limit
    """
```

#### 缺失数据提示

```python
def missing_data_hints(
    material_entry: MaterialEntry,
    envelope_report: EnvelopeReport,
    condition: Condition,
) -> tuple[str, ...]:
    """生成"如要继续评估需要补充的数据"清单（中文）。

    模板：
      - 每条 violation: "在 [input_value] [unit] [axis] 下，需要补充该材料对应工况的实验/标准数据"
      - 若 strength_allowables 缺失且 condition 含载荷:
          "需要补充 yield_mpa / Xt/Xc/Yt/Yc/S 强度许用值以启用失效分析"
      - 去重 + 中文化
    """
```

### 3.5 `material_eval/material_property_library.py`（扩展）

- `MaterialEntry` 加字段 `strength_allowables: StrengthAllowables | None = None`
- `_build_allowables(payload)` 解析顶层 `strength_allowables` JSON，每个字段单点或三点区间，单点按 confidence=0.5 自动展开（与 Phase 1 一致）
- 新增方法 `library.allowables_for(material_id) -> StrengthAllowables | None`

### 3.6 `material_eval/evaluation.py`（改造）

`EvaluationRequest` 新增可选字段：

```python
@dataclass(frozen=True)
class EvaluationRequest:
    ...（Phase 1 字段）
    strength_allowables: StrengthAllowables | None = None
```

`EvaluationDraft` 新增：

```python
safety_report: SafetyReport | None = None
```

`run_evaluation` 在 calculation 后插入：

```python
safety_report = None
allowables = request.strength_allowables
if allowables is not None and (allowables.has_isotropic() or allowables.has_orthotropic()):
    if request.laminate_stack is not None and allowables.has_orthotropic():
        factors = laminate_safety_factor(request.laminate_stack, condition, allowables)
        method = "tsai_wu"
    elif allowables.has_isotropic():
        stresses = isotropic_stress_field(request.part, request.material, condition)
        factors = (von_mises_safety_factor(stresses, request.material, allowables),)
        method = "von_mises"
    else:
        factors = ()
        method = "skipped_no_matching_allowables"
    if factors:
        governing_idx = min(range(len(factors)), key=lambda i: factors[i].value.typical)
        safety_report = SafetyReport(factors=factors, governing_index=governing_idx, method=method)
```

Refusal 分支调用：

```python
suggestions = suggest_alternatives_for(condition, request.part, MaterialPropertyLibrary())
hints = missing_data_hints(material_entry, envelope_report, condition)
refusal = build_refusal_report(
    material=..., part=..., condition=condition,
    envelope_report=envelope_report,
    suggested_alternatives=tuple(s.material_name for s in suggestions),
    missing_data_hints=hints,
)
```

### 3.7 `material_eval/reporting.py`（扩展）

`build_internal_report` 接受新参数 `safety_report: SafetyReport | None = None`；非 None 时插入章节：

```
## 安全性评估（方法：[criterion]）

| 评估位置 | 安全系数（low / typical / high） | 主导模式 | 状态 |
| --- | --- | --- | --- |
| BEAM/root_top | 1.8 / 2.1 / 2.4 | yield | ✓ pass |
| BEAM/root_bot | 1.2 / 1.4 / 1.6 | yield | ⚠ marginal |

控制层：[governing.location]，最低 SF.value.low = 1.2  
*Tsai-Wu F12 耦合系数采用工程默认 -1/(2·sqrt(Xt·Xc·Yt·Yc))，待业务专家校准。*
```

状态判定：`SF.value.low >= 1.0 → ✓ pass`，`SF.value.typical >= 1.0 > SF.value.low → ⚠ marginal`，否则 `✗ fail`。

### 3.8 `material_eval/ui_streamlit.py`（扩展）

工况输入区新增 2 个数值字段 + 单位下拉：
- `axial_force`（默认 0，单位 `["N", "kN", "lbf"]`）
- `bending_moment`（默认 0，单位 `["N·m", "kN·m"]`）

`render_sidebar` 从材料库读 `library.allowables_for(material_id)`，注入 EvaluationRequest。

结果页新增 tab "安全性评估"：渲染 SafetyReport 表格，pass=绿、marginal=黄、fail=红的 `st.metric` 或带颜色的 markdown。

越界拒绝页：现在 refusal_report 已含 suggested_alternatives 和 missing_data_hints，UI 不需要额外处理（由 reporting 渲染）。

### 3.9 Seed 升级

`data/seed/material_property_library.json` 加 3 个材料的 `strength_allowables`：

| material | 字段 | 区间（low / typical / high）单位 MPa | source |
|---|---|---|---|
| `ti_6al_4v` | yield_mpa | 830 / 880 / 930 | MMPDS-typ, engineering default, needs lot-specific test |
| `pa66_gf30` | yield_mpa | 80 / 100 / 120 | datasheet typ, depends on moisture and orientation, needs supplier confirmation |
| `carbon_epoxy_quasi_iso` | Xt / Xc / Yt / Yc / S | （5 项区间，按典型 T700/epoxy 系统 ±15%） | textbook typical, needs layup/cure/test confirmation |

## 4. 数据流（端到端）

```
UI (Streamlit form, 含 axial_force + bending_moment)
   ↓ 构造 Condition (载荷已归一化到 N / N·m)
   ↓ library.allowables_for(material_id) → StrengthAllowables
EvaluationRequest (material, part, condition, material_envelope, strength_allowables)
   ↓
evaluation.run_evaluation
   ├─ envelope.check(condition).violations? → EnvelopeRefusal
   │       ↓ suggest_alternatives_for + missing_data_hints
   │       ↓ build_refusal_report（已含建议替代材料 / 缺失数据清单）
   │       ↓ UI 红底 banner（含导航出口）
   │
   └─ pass →
       ├─ calculate_part (Phase 1，区间算术不变)
       ├─ analyze_laminate (Phase 1 若有 stack)
       ├─ stress_analysis.isotropic_stress_field / ply_stress_field (Phase 2 新增)
       ├─ failure_criteria.von_mises_safety_factor / tsai_wu / laminate_safety_factor (Phase 2 新增)
       ├─ SafetyReport 聚合（governing + passed）
       ├─ scoring (Phase 1 不变；Phase 3 再让"工况风险"消费 SF)
       ├─ build_internal_report (新增 "安全性评估" 章节)
       └─ storage.save_run
            ↓
UI tabs: 工程初筛 / 证据卡 / 中文报告 / 安全性评估（Phase 2 新）/ 评估记录 / 检索评估
```

## 5. 迁移与兼容

### 5.1 破坏性变更

无强制破坏性变更。所有新参数（`strength_allowables` / `safety_report`）默认 None；旧调用代码继续工作。

### 5.2 旧 evaluation 记录

`evaluation_runs.payload` JSON 增加可选 `safety_report` 段；旧记录读取时缺该字段默认 None，UI 显示"该次评估未包含失效分析"。

### 5.3 Seed 兼容

`strength_allowables` 是顶层可选字段；缺失 → `library.allowables_for(...)` 返回 None → 评估跳过失效分析。

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| `F12` 工程默认在某些复合体系下过保守（甚至非物理） | 报告每条 Tsai-Wu SF 标注 "F12 采用工程默认"；UI 提供说明气泡；后续 Phase 3 允许 seed 显式指定 F12 |
| CLT 反算只处理面内拉伸（不含弯矩 M_x） | 文档明确"Phase 2 仅支持面内载荷输入"；报告章节标注"未考虑面外弯曲" |
| `strength_allowables` seed 数据不准 | 与 envelope 一样标 `source = "engineering default, needs supplier confirmation"`，UI 显式渲染 |
| 反向应力穿零（Interval 除法异常） | failure_criteria 模块捕获 IntervalError → 返回 SafetyFactor(value=Interval.point(0, ""), dominant_mode="indeterminate", notes=("应力区间穿零，无法判定安全系数",)) |
| Tsai-Wu 二次方程判别式 < 0（理论上不该发生） | 抛 `FailureCriterionError`；单测覆盖；触发时报告 fall-back 到 "极限应力法" |
| 替代材料反查给出 0 条（envelope 都不覆盖） | refusal report 显式说"当前工况无库内材料可覆盖"+ 列 missing_data_hints |

## 7. 验收清单

- [ ] 全量 `python3 -m unittest discover -s tests -p 'test_*.py' -v` 全绿
- [ ] 新模块测试覆盖率 ≥ 90%（`strength`, `stress_analysis`, `failure_criteria`, `alternatives`）
- [ ] 3 MVP 场景每个跑通"反向载荷 → SafetyReport"
- [ ] Out-of-envelope refusal 至少给出 1 条替代材料 + 1 条缺失数据提示
- [ ] 3 个材料 seed 升级完成（ti_6al_4v / pa66_gf30 / carbon_epoxy_quasi_iso）
- [ ] `docs/implementation-log.md` 增加 Phase 2 完成记录

## 8. Phase 3 候选

- Hashin 分模式失效准则（fiber tensile / fiber compressive / matrix tensile / matrix compressive）
- 屈曲分析（柱屈曲 / 板屈曲）
- 疲劳分析（S-N 曲线 + Miner 损伤累积）
- `F12` / `CONFIDENCE_SPREAD` / 评分卡权重的实验校准
- claim binding 句子级/计算变量级
- 知识库扩充与材料库扩充
