# Phase 2 失效准则 + Refusal 导航 — 轻量实现计划

> **For agentic workers:** Spec at `docs/superpowers/specs/2026-05-12-phase2-failure-criteria-design.md` is the source of truth for code-level details. This plan is a task decomposition with parallelism map. Each task uses TDD (test → red → impl → green → commit).

**Goal:** 让 MVP 评估闭环——给定载荷算安全系数区间 + 越界拒绝时给替代材料和缺失数据出口。

**Architecture:** 在 Phase 1 的 Interval / Condition / EnvelopeSpec 之上加 4 个新模块（strength / stress_analysis / failure_criteria / alternatives），改造 evaluation 流程，扩 3 个材料 seed，加 1 个 UI tab。

**Tech Stack:** Python 3.12 / Pint / Pydantic v2 / stdlib unittest / Streamlit。

---

## File Structure

### 新增

- `material_eval/strength.py` — `StrengthAllowables`, `SafetyFactor`, `SafetyReport`
- `material_eval/stress_analysis.py` — `isotropic_stress_field`, `PlyStress`, `ply_stress_field`
- `material_eval/failure_criteria.py` — `von_mises_safety_factor`, `tsai_wu_safety_factor`, `laminate_safety_factor`
- `material_eval/alternatives.py` — `AlternativeSuggestion`, `suggest_alternatives_for`, `missing_data_hints`
- 测试：`tests/test_strength.py`, `tests/test_stress_analysis.py`, `tests/test_failure_criteria.py`, `tests/test_alternatives.py`, `tests/test_phase2_smoke.py`

### 修改

- `material_eval/material_property_library.py` — 解析 `strength_allowables` 顶层字段，新增 `allowables_for(material_id)`
- `material_eval/evaluation.py` — `EvaluationRequest.strength_allowables` 字段；`run_evaluation` 加 safety 分支；refusal 分支注入 alternatives + hints
- `material_eval/reporting.py` — `build_internal_report` 接 `safety_report` 渲染 "安全性评估" 章节
- `material_eval/ui_streamlit.py` — `axial_force` + `bending_moment` 工况输入；"安全性评估" tab
- `data/seed/material_property_library.json` — `ti_6al_4v` / `pa66_gf30` / `carbon_epoxy_quasi_iso` 三个材料加 `strength_allowables`
- `docs/implementation-log.md` — Phase 2 完成记录

---

## 类型契约（贯穿全 plan）

参 spec §3.1。关键签名（type-only excerpt）：

```python
# strength.py
@dataclass(frozen=True)
class StrengthAllowables:
    yield_mpa: Interval | None = None
    Xt_mpa: Interval | None = None
    Xc_mpa: Interval | None = None
    Yt_mpa: Interval | None = None
    Yc_mpa: Interval | None = None
    S_mpa:  Interval | None = None
    f12_star: float = 0.0
    source: str | None = None
    def has_isotropic(self) -> bool: ...
    def has_orthotropic(self) -> bool: ...

@dataclass(frozen=True)
class SafetyFactor:
    value: Interval
    pass_at_typical: bool
    dominant_mode: str
    criterion: str
    location: str
    notes: tuple[str, ...] = ()

@dataclass(frozen=True)
class SafetyReport:
    factors: tuple[SafetyFactor, ...]
    governing_index: int
    method: str
    @property
    def governing(self) -> SafetyFactor: ...
    @property
    def status(self) -> str: "pass" / "marginal" / "fail"
    @property
    def passed(self) -> bool: ...

# stress_analysis.py
def isotropic_stress_field(part, material, condition) -> dict[str, Interval]: ...

@dataclass(frozen=True)
class PlyStress:
    ply_index: int
    sigma_11: Interval
    sigma_22: Interval
    tau_12: Interval

def ply_stress_field(stack, condition) -> tuple[PlyStress, ...]: ...

# failure_criteria.py
def von_mises_safety_factor(stresses, material, allowables, *, location_label=None) -> SafetyFactor: ...
def tsai_wu_safety_factor(ply_stress, allowables) -> SafetyFactor: ...
def laminate_safety_factor(stack, condition, allowables) -> tuple[SafetyFactor, ...]: ...

# alternatives.py
@dataclass(frozen=True)
class AlternativeSuggestion:
    material_id: str
    material_name: str
    category: str
    envelope_source: str | None

def suggest_alternatives_for(condition, part, library, *, limit=5) -> tuple[AlternativeSuggestion, ...]: ...
def missing_data_hints(material_entry, envelope_report, condition) -> tuple[str, ...]: ...
```

---

## 并行波次

```
Wave 1 (并行 2 个):  Task 1 (strength.py)     |  Task 8 (alternatives.py)
Wave 2 (单个):       Task 2 (material_lib parse strength_allowables)
Wave 3 (并行 2 个):  Task 3 (isotropic_stress) | Task 4 (ply_stress)
Wave 4 (并行 2 个):  Task 5 (von_mises)        | Task 6 (tsai_wu + laminate)
Wave 5 (并行 2 个):  Task 7 (evaluation safety) | Task 9 (evaluation refusal wiring)
Wave 6 (并行 2 个):  Task 10 (reporting safety) | Task 11 (ui_streamlit)
Wave 7 (单个):       Task 12 (seed 3 材料升级)
Wave 8 (单个):       Task 13 (phase2 smoke)
Wave 9 (单个):       Task 14 (docs)
```

冲突规避：每个 wave 内的并行 task 改的**文件集不相交**（见每个 task 的 Files 列表）。

---

## Tasks

### Task 1: `strength.py`

**Files:** Create `material_eval/strength.py` + `tests/test_strength.py`

- [ ] Step 1 — 写 `tests/test_strength.py` 含：构造 `StrengthAllowables(yield_mpa=Interval.point(880, "MPa"))` 测 `has_isotropic`/`has_orthotropic`；构造 `SafetyFactor(value=Interval(1.2, 1.8, 2.4, "")` 测 `pass_at_typical`；构造 `SafetyReport(factors=(...), governing_index=0, method="von_mises")` 测 `governing` / `status` 三档（pass/marginal/fail 边界）+ `passed`。共 ~8 测试。
- [ ] Step 2 — 跑测试看 ImportError fail
- [ ] Step 3 — 实现 `material_eval/strength.py` 按 spec §3.1 给的完整签名。`SafetyReport.status` 严格用阈值：`sf.low >= 1.5 → pass`，`sf.typical >= 1.0 → marginal`，else `fail`。
- [ ] Step 4 — 跑测试看 8/8 pass
- [ ] Step 5 — 全量回归 `python -m unittest discover -s tests`，预期 155 + 8 = 163 全绿
- [ ] Step 6 — Commit: `feat(strength): add StrengthAllowables, SafetyFactor, SafetyReport types`

---

### Task 2: `material_property_library.py` 解析 `strength_allowables`

**Files:** Modify `material_eval/material_property_library.py` + `tests/test_material_property_library.py`

- [ ] Step 1 — 在测试文件追加 `StrengthAllowablesLoadingTest`：构造临时 JSON 含 `strength_allowables: {"yield_mpa": {"low": 800, "typical": 880, "high": 930}, "source": "test"}`；断言 `library.allowables_for("test_id").yield_mpa.typical == 880`；缺省 `allowables_for` 返回 None；orthotropic 五项（Xt/Xc/Yt/Yc/S）+ `f12_star: 0.5` 全部正确解析。
- [ ] Step 2 — 跑测试看 fail（`allowables_for` 不存在）
- [ ] Step 3 — 给 `MaterialEntry` 加 `strength_allowables: StrengthAllowables | None = None`；新增私有 `_build_allowables(payload) -> StrengthAllowables | None`，解析单点或三点区间字段（复用 Phase 1 的 confidence-spread 逻辑：若是三点字典就直接构造 Interval，单点则按 `confidence=0.5 → ±15%` 包装）；新增 `MaterialPropertyLibrary.allowables_for(material_id) -> StrengthAllowables | None`
- [ ] Step 4 — 测试通过
- [ ] Step 5 — 全量回归 163 + N = ~168 全绿
- [ ] Step 6 — Commit: `feat(material-lib): parse strength_allowables seed field, add allowables_for API`

---

### Task 3: `stress_analysis.isotropic_stress_field`

**Files:** Create `material_eval/stress_analysis.py` + `tests/test_stress_analysis.py`

实现 spec §3.2 各向同性反向应力。覆盖 BEAM / I_BEAM / PLATE / STRAP。注意：

- BEAM：评估点 `"root_top"`（axial + bending）和 `"root_bottom"`（axial - bending）。axial = F/A，bending = M·(d/2)/I。A 和 I 取自 `section.area_mm2` 和 `section.inertia_x_mm4`（已是 Interval）。
- PLATE：评估点 `"center"`，membrane = F/(w·t)，bending = 6·M/(w·t²)，合成等效正应力。
- STRAP：评估点 `"section"`，tensile = F/A。
- I_BEAM：参 BEAM 但用 height/2 作 c。
- CORRUGATED 暂不实现（spec 未明确），调用时返回 `{}`。

- [ ] Step 1 — 写 5 个测试：BEAM 手算（F=1000 N, M=10 N·m, d=20 mm, t=2 mm，验证 root_top 数值）；STRAP 手算（F=500 N, w=30, t=2 → 8.33 MPa）；PLATE membrane 手算；零载荷情况下 stresses 是零宽 Interval(0,0,0)；不支持的拓扑返回空 dict。
- [ ] Step 2 — 跑测试看 fail
- [ ] Step 3 — 实现，需要 import `Condition`, `Interval`, `analyze_*_section`。从 condition 取 `axial_force` 和 `bending_moment`（Pint normalize 后单位 N 和 N·m）。
- [ ] Step 4 — 测试通过
- [ ] Step 5 — 全量回归 ~173 全绿
- [ ] Step 6 — Commit: `feat(stress-analysis): isotropic_stress_field for BEAM/I_BEAM/PLATE/STRAP`

---

### Task 4: `stress_analysis.ply_stress_field` (CLT 反算)

**Files:** Modify `material_eval/stress_analysis.py` + `tests/test_stress_analysis.py`

实现 spec §3.2 复合材料 CLT 反算。步骤：

1. 把 `condition.axial_force` 折算为 N_x（线力 = F / 板宽；本期简化假设 condition.width 是承载宽度）
2. 求中面应变 `ε_xy = A_inv · N`（A 矩阵来自 `analyze_laminate(stack).a_matrix`，是 float tuple）
3. 每层把全局应变转主轴应变（旋转矩阵 T_strain，角度 ply.angle_deg）
4. 每层主轴应力 σ_local = Q · ε_local（Q 来自 `laminates._reduced_stiffness(ply)`，是 float 元组）

输出：`tuple[PlyStress, ...]`，每个 PlyStress 的三个应力分量都包装成零宽 Interval（spec §3.2 明确"应力计算保持零宽，SF 区间宽度由 strength_allowables 主导"）。

- [ ] Step 1 — 写 3 测试：4 层 [0/90/90/0] 准对称 + axial_force 沿 x 方向，断言 0° 层 sigma_11 > sigma_22 / 90° 层反之 / tau_12 ~ 0；零载荷 → 所有应力 0；返回元素数 = stack.plies 长度
- [ ] Step 2 — 跑测试看 fail
- [ ] Step 3 — 实现 `ply_stress_field`。注意 `_reduced_stiffness` 已在 `material_eval/laminates.py` 中，import 使用即可
- [ ] Step 4 — 测试通过
- [ ] Step 5 — 全量回归 ~176 全绿
- [ ] Step 6 — Commit: `feat(stress-analysis): ply_stress_field for laminate CLT back-calculation`

---

### Task 5: `failure_criteria.von_mises_safety_factor`

**Files:** Create `material_eval/failure_criteria.py` + `tests/test_failure_criteria.py`

按 spec §3.3 实现：

```python
def von_mises_safety_factor(stresses, material, allowables, *, location_label=None) -> SafetyFactor:
    # 1. 在 stresses dict 中找 typical 绝对值最大的项作为 governing
    # 2. sigma = stresses[governing_key]  # Interval
    # 3. allowable = allowables.yield_mpa if allowables.yield_mpa is not None else material.tensile_strength_mpa
    # 4. SF = allowable / sigma  # Interval division
    # 5. pass_at_typical = SF.typical >= 1.0
    # 6. dominant_mode = "yield" if allowables.yield_mpa else "ultimate"
    # 7. 零应力 case: 若 sigma.typical == 0, 返回 SF=Interval.point(999, ""), mode="no_load"
```

- [ ] Step 1 — 写 5 测试：(a) 典型 case sigma=Interval(80,100,120, MPa), yield=Interval(800,880,930) → SF.typical 约 8.8 → pass; (b) sigma 接近 yield → marginal; (c) sigma 超过 yield → fail; (d) 零应力 → SF.typical=999; (e) yield_mpa=None → fallback to material.tensile_strength_mpa
- [ ] Step 2 — fail
- [ ] Step 3 — 实现
- [ ] Step 4 — pass
- [ ] Step 5 — 全量回归
- [ ] Step 6 — Commit: `feat(failure-criteria): von_mises_safety_factor`

---

### Task 6: `failure_criteria.tsai_wu_safety_factor` + `laminate_safety_factor`

**Files:** Modify `material_eval/failure_criteria.py` + `tests/test_failure_criteria.py`

按 spec §3.3 实现：

```python
def tsai_wu_safety_factor(ply_stress, allowables) -> SafetyFactor:
    # 系数（每个都是 Interval-aware，但 X/Y/S 是 Interval, ply_stress 也是 Interval）:
    # F1 = 1/Xt - 1/Xc; F2 = 1/Yt - 1/Yc; F11 = 1/(Xt*Xc); F22 = 1/(Yt*Yc); F66 = 1/(S*S)
    # F12 = allowables.f12_star / (2 * sqrt(Xt*Xc*Yt*Yc))  # f12_star 默认 0
    # a = F11*s1**2 + F22*s2**2 + F66*tau12**2 + 2*F12*s1*s2
    # b = F1*s1 + F2*s2
    # 求解 a*SF^2 + b*SF - 1 = 0:
    #   SF = (-b + sqrt(b**2 + 4*a)) / (2*a)
    # 端点穷举: 对 (a, b) 各取 (low, typical, high)，9 组合算 SF，min/max 构造 SF Interval
    # 零应力: 若 max(|s1|, |s2|, |tau12|).typical < 1e-9, 返回 SF=999

def laminate_safety_factor(stack, condition, allowables) -> tuple[SafetyFactor, ...]:
    ply_stresses = ply_stress_field(stack, condition)
    return tuple(tsai_wu_safety_factor(ps, allowables) for ps in ply_stresses)
```

注意：`sqrt(Interval)` 需要扩展。简化：`sqrt` 是单调函数，对正区间直接逐点开方：`Interval(sqrt(low), sqrt(typ), sqrt(high), ...)`。若区间含负，抛错（在 Tsai-Wu 上下文这意味着 X/Y 输入错）。

- [ ] Step 1 — 写 4 测试：(a) 单层沿纤维拉伸 sigma_11=1000 MPa, Xt=2000 → SF≈2.0 pass; (b) sigma_11 超过 Xt → fail; (c) f12_star=0 与 f12_star=-1 应该给不同 SF（验证耦合参数生效）; (d) `laminate_safety_factor` 返回 tuple 长度 = 层数；
- [ ] Step 2 — fail
- [ ] Step 3 — 实现（含 `_sqrt_interval` 辅助函数）
- [ ] Step 4 — pass
- [ ] Step 5 — 全量回归
- [ ] Step 6 — Commit: `feat(failure-criteria): tsai_wu and laminate_safety_factor with f12_star override`

---

### Task 7: `evaluation.run_evaluation` 集成 safety 分支

**Files:** Modify `material_eval/evaluation.py` + `tests/test_evaluation_workflow.py`

按 spec §3.6：

- `EvaluationRequest` 加字段 `strength_allowables: StrengthAllowables | None = None`
- `EvaluationDraft` 加字段 `safety_report: SafetyReport | None = None`
- `run_evaluation` 在 calculate_part 之后加 safety 分支（参 spec §3.6 完整代码块）

- [ ] Step 1 — 写 2 测试：(a) 不传 strength_allowables → safety_report=None（向后兼容）；(b) 传 yield_mpa 的 isotropic case → safety_report 不为 None，含 factors 元组，governing 指向最低 SF
- [ ] Step 2 — fail
- [ ] Step 3 — 实现
- [ ] Step 4 — pass
- [ ] Step 5 — 全量回归
- [ ] Step 6 — Commit: `feat(evaluation): run_evaluation safety analysis branch`

---

### Task 8: `alternatives.py`

**Files:** Create `material_eval/alternatives.py` + `tests/test_alternatives.py`

按 spec §3.4 实现 `suggest_alternatives_for` 和 `missing_data_hints`：

```python
def suggest_alternatives_for(condition, part, library, *, limit=5):
    suggestions = []
    for material_id, material_record in library.materials.items():
        envelope = library.envelope_for(material_id)
        if envelope is None or not envelope.has_any_axis():
            continue
        report = envelope.check(condition)
        if report.violations:
            continue
        suggestions.append(AlternativeSuggestion(
            material_id=material_id,
            material_name=material_record.name,
            category=material_record.category,
            envelope_source=envelope.source,
        ))
    # 排序：非 engineering-default 优先
    suggestions.sort(key=lambda s: (
        s.envelope_source is None or "engineering default" in (s.envelope_source or "").lower(),
    ))
    return tuple(suggestions[:limit])

def missing_data_hints(material_entry, envelope_report, condition):
    hints = []
    for v in envelope_report.violations:
        axis_label = {"temperature_C": "温度", "humidity_pct": "湿度", "stress_MPa": "应力",
                      "strain_rate_1_per_s": "应变率", "fatigue_cycles": "疲劳循环数",
                      "thickness_mm": "厚度"}.get(v.axis, v.axis)
        hints.append(f"补充 {material_entry.name} 在 {v.input_value} ({axis_label}) 下的实验/标准数据")
    if material_entry.strength_allowables is None:
        if condition.axial_force is not None or condition.bending_moment is not None:
            hints.append(f"补充 {material_entry.name} 的强度许用值 (yield/Xt/Xc/Yt/Yc/S) 以启用失效分析")
    return tuple(hints)
```

- [ ] Step 1 — 写 4 测试：(a) Phase 1 seed 反查温度 25°C / 厚度 5mm 的载荷场景，应该至少返回 1-2 个材料（pa66_gf30 / kevlar）; (b) 越界场景（温度 500°C）应返回空 tuple; (c) missing_data_hints 含 temperature_C violation → 中文 hint; (d) 无 strength_allowables + 有 axial_force → hint 提示补强度数据
- [ ] Step 2 — fail
- [ ] Step 3 — 实现
- [ ] Step 4 — pass
- [ ] Step 5 — 全量回归
- [ ] Step 6 — Commit: `feat(alternatives): suggest_alternatives_for + missing_data_hints`

---

### Task 9: evaluation refusal wiring + reporting integration

**Files:** Modify `material_eval/evaluation.py`, `material_eval/reporting.py` + 扩展 `tests/test_phase2_smoke.py`（先建空 case 准备）

在 `evaluation.run_evaluation` 的 refusal 分支：

```python
library = MaterialPropertyLibrary()
suggestions = suggest_alternatives_for(condition, request.part, library)
# 找当前 material 对应的 MaterialEntry
material_entry = library.materials.get(request.material_id) if hasattr(request, 'material_id') else None
hints = missing_data_hints(material_entry, envelope_report, condition) if material_entry else ()
refusal = build_refusal_report(
    material=request.material, part=request.part, condition=condition,
    envelope_report=envelope_report,
    suggested_alternatives=tuple(s.material_name for s in suggestions),
    missing_data_hints=hints,
)
```

**注意**：当前 `EvaluationRequest` 没有 `material_id` 字段（只有 `material: MaterialCandidate`）。本 Task 给 `EvaluationRequest` 加可选 `material_id: str | None = None`（向后兼容）；UI 在调用时传入。

- [ ] Step 1 — 在 `test_evaluation_workflow.py` 追加 `test_refusal_includes_alternatives_and_hints`：构造 PA66-GF30 + 温度 150°C → refusal，断言 `result.refusal_markdown` 含至少 1 条 "替代材料" 标记 + 至少 1 条 "补充数据" 提示
- [ ] Step 2 — fail
- [ ] Step 3 — 实现 evaluation 改造 + 验证 `build_refusal_report` 已能消费这两个参数（Phase 1 已实现）
- [ ] Step 4 — pass
- [ ] Step 5 — 全量回归
- [ ] Step 6 — Commit: `feat(evaluation): wire alternatives + missing_data_hints into refusal`

---

### Task 10: reporting "安全性评估" 章节

**Files:** Modify `material_eval/reporting.py` + `tests/test_reporting.py`

按 spec §3.7 在 `build_internal_report` 接 `safety_report: SafetyReport | None = None` 参数；非 None 时插入章节：

```markdown
## 安全性评估（方法：{method}）

| 评估位置 | 安全系数（low / typical / high） | 主导模式 | 状态 |
| --- | --- | --- | --- |
| {location} | {sf.value.format()} | {dominant_mode} | {status_icon} |

控制层：**{governing.location}**，最低 SF.value.low = {governing.value.low:.2f}

*Tsai-Wu F12 耦合系数：f12_star = {f12_star}（0 表示退化为 Tsai-Hill，工程默认）*
```

状态图标：pass=`✓ pass`，marginal=`⚠ marginal`，fail=`✗ fail`。

- [ ] Step 1 — 写 3 测试：(a) safety_report=None → markdown 不含 "安全性评估"; (b) 含一条 pass SF → markdown 含 "✓ pass" 和 location; (c) marginal/fail 显示正确
- [ ] Step 2-4 — TDD
- [ ] Step 5 — 全量回归
- [ ] Step 6 — Commit: `feat(reporting): add 安全性评估 markdown section`

---

### Task 11: Streamlit UI 反向载荷 + safety tab

**Files:** Modify `material_eval/ui_streamlit.py`

按 spec §3.8：

- 工况输入区追加两个 `st.number_input` + `st.selectbox` 配对：`axial_force`（默认 0 N，单位 `["N", "kN"]`）、`bending_moment`（默认 0 N·m，单位 `["N·m", "kN·m"]`）。把它们构造为 `Quantity(...)` 放进 `Condition`。
- `render_sidebar` 现在拿 `material_id` 时，新增一行 `allowables = library.allowables_for(material_id)`，注入 `EvaluationRequest.strength_allowables`
- 新增结果 tab "安全性评估"：调用 `render_safety_report(draft.safety_report)`，遍历 `factors`，每条用 `st.metric` 显示 SF 区间和状态（pass=绿、marginal=黄、fail=红）。如果 `safety_report` is None，显示提示"未启用失效分析（材料未声明 strength_allowables 或未输入载荷）"

无单测（UI），只跑 compileall。

- [ ] Step 1 — 修改 ui_streamlit.py
- [ ] Step 2 — `python -m compileall material_eval app.py` 无错
- [ ] Step 3 — 全量回归 unittest 全绿
- [ ] Step 4 — Commit: `feat(ui): add reverse-load inputs and safety evaluation tab`

---

### Task 12: Seed 升级 3 材料 strength_allowables

**Files:** Modify `data/seed/material_property_library.json` + `tests/test_material_property_library.py`

按 spec §3.9 三个材料补 `strength_allowables`：

```json
"ti_6al_4v": {
  ...,
  "strength_allowables": {
    "yield_mpa": {"low": 830, "typical": 880, "high": 930},
    "source": "MMPDS-typ, engineering default, needs lot-specific test"
  }
},
"pa66_gf30": {
  ...,
  "strength_allowables": {
    "yield_mpa": {"low": 80, "typical": 100, "high": 120},
    "source": "datasheet typ, depends on moisture and orientation, needs supplier confirmation"
  }
},
"carbon_epoxy_quasi_iso": {
  ...,
  "strength_allowables": {
    "Xt_mpa": {"low": 1700, "typical": 2000, "high": 2300},
    "Xc_mpa": {"low": 1100, "typical": 1400, "high": 1700},
    "Yt_mpa": {"low": 50,   "typical": 65,   "high": 80},
    "Yc_mpa": {"low": 180,  "typical": 220,  "high": 260},
    "S_mpa":  {"low": 80,   "typical": 100,  "high": 120},
    "f12_star": 0.0,
    "source": "textbook typical (Tsai 1980), needs layup/cure/test confirmation"
  }
}
```

- [ ] Step 1 — 改 seed JSON
- [ ] Step 2 — 在 `SeedIntegrityTest` 追加：`test_3_materials_have_strength_allowables` 断言 `library.allowables_for("ti_6al_4v").yield_mpa.typical == 880` 等
- [ ] Step 3 — 跑测试 + 全量回归
- [ ] Step 4 — Commit: `data(seed): add strength_allowables for ti_6al_4v, pa66_gf30, carbon_epoxy_quasi_iso`

---

### Task 13: Phase 2 端到端 smoke

**Files:** Create `tests/test_phase2_smoke.py`

4 个端到端 case：

1. **Ti-6Al-4V 骨架 BEAM + axial 10kN + bending 50 N·m** → SafetyReport 非空，status="pass"
2. **PA66-GF30 外壳 PLATE + axial 2kN + bending 10 N·m** → SafetyReport 非空，status 任意但 factors 存在
3. **Kevlar 助力带 STRAP + axial 5kN**（**fallback 到 material.tensile_strength_mpa**）→ SafetyReport 非空（Kevlar 没有 strength_allowables，验证 fallback）
4. **Carbon-Epoxy 准各向同性 + 4 层 [0/90/90/0] + axial 1kN** → SafetyReport.method == "tsai_wu"，factors 长度 = 4

- [ ] Step 1 — 写 4 测试
- [ ] Step 2-4 — 跑测试逐个修
- [ ] Step 5 — Commit: `test(phase2): end-to-end smoke for 3 MVP scenarios + Tsai-Wu laminate`

---

### Task 14: 文档

**Files:** Modify `docs/implementation-log.md`

追加 "11. Phase 2 失效准则 + Refusal 导航（2026-05-12）" 章节，列出本期模块、关键决策、验证测试数。

- [ ] Step 1 — Edit doc
- [ ] Step 2 — Commit: `docs: log Phase 2 completion`

---

## DoD

- [ ] 全量 unittest 全绿（155 → ~185+）
- [ ] 3 MVP 场景 + 1 复合 case 端到端通过
- [ ] Out-of-envelope refusal 自动含替代材料 + 缺失数据提示
- [ ] Streamlit UI 启动无错，含"安全性评估" tab

## Self-Review

- Spec §3.1-3.9 全覆盖：Task 1 (§3.1), 2 (§3.5 + seed parse), 3+4 (§3.2), 5+6 (§3.3), 8 (§3.4), 7+9 (§3.6), 10 (§3.7), 11 (§3.8), 12 (§3.9). ✓
- 无 TBD/placeholder。每个 Task 给出测试断言和实现 hint。
- 类型契约统一在头部，14 个 task 严格按头部签名。
