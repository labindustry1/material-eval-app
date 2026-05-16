# 材料评估 MVP 交接指南

本文档给下一位接手者使用。目标是让接手者不用翻聊天记录，也能在 30 分钟内理解项目现状、跑通应用、判断下一步怎么做。

## 1. 当前状态

- Git 分支：`main`
- 入口：`app.py`
- UI：`material_eval/ui_streamlit.py`
- 本地数据库：SQLite，默认 `data/mvp.sqlite3`
- 正式版数据库预案：Supabase migration 已在 `supabase/migrations/`
- 当前定位：内部研发材料可行性初筛 MVP，不是量产认证系统。

当前 MVP 已完成从旧 Streamlit 原型到分层工程项目的重构，包含：

- 行业/零部件 seed catalog
- 材料属性库、单位归一化、区间不确定度
- 工况包络校验和 refusal 路径
- 梁/板/带/管等确定性初筛计算
- Classical Laminate Theory 铺层初筛
- von Mises / Tsai-Wu 安全系数评估
- Docling + BM25 + 可选 BGE-M3 的证据检索
- 中文报告、结构化 claim、透明 scorecard
- SQLite 评估记录、复核记录、refusal log
- Supabase/pgvector 正式版 schema 草案

## 2. 接手后先读

建议阅读顺序：

1. `README.md`：项目入口、快速启动、技术栈。
2. `docs/implementation-log.md`：完整实施记录和 Phase 1/2 设计决策。
3. `docs/material-eval-refactor-prd.md`：最初的重构 PRD 和业务边界。
4. `docs/target-architecture-v1.md`：目标架构。
5. `docs/superpowers/specs/` 和 `docs/superpowers/plans/`：Phase 1/2 的详细设计与执行计划。

## 3. 本地启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

访问：

```text
http://127.0.0.1:8501
```

可选环境变量：

```bash
export MVP_ACCESS_CODE="your-code"
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4.1-mini"
export DEEPSEEK_API_KEY="..."
```

不配置云端 LLM key 时，核心评估、检索和本地中文报告仍可运行。

## 4. 验收命令

交接前至少跑：

```bash
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
.venv/bin/python -m compileall material_eval app.py tests
NO_PROXY='*' curl -I http://127.0.0.1:8501
```

如需快速验证核心链路：

```bash
.venv/bin/python -m unittest tests.test_phase1_smoke tests.test_phase2_smoke -v
```

## 5. 关键模块地图

```text
app.py
  -> material_eval/ui_streamlit.py
     -> evaluation.py
        -> catalog.py
        -> materials.py / material_property_library.py
        -> conditions.py / units.py / uncertainty.py
        -> computation.py / section_analysis.py
        -> laminates.py / stress_analysis.py / failure_criteria.py / strength.py
        -> evidence.py / evidence_store.py / ingestion.py / embeddings.py
        -> reporting.py / report_schema.py / scoring.py
        -> storage.py / artifacts.py
```

重要数据：

```text
data/seed/domain_config.json
data/seed/material_property_library.json
knowledge_base/
supabase/migrations/20260507145720_material_eval_core.sql
```

## 6. 当前不能误解的边界

- 当前是内部研发初筛，不给量产、认证、准入或客户承诺背书。
- 材料 seed 数据仍有“工程默认/需供应商确认”的占位属性。
- 透明评分卡权重是 MVP 默认值，需要真实项目数据和专家校准。
- Tsai-Wu 已接入，但 Hashin 分模式失效、面外弯矩、屈曲和疲劳还在 Phase 3 候选。
- Supabase schema 已有，但运行时仍以 SQLite 为主。
- RAG 当前知识库很小，不能当成完整行业知识库。

## 7. 下一步建议

优先做两件纯架构工作：

1. Hashin 分模式失效准则：让复材报告能说明 fiber/matrix 哪个模式先坏。
2. Claim binding 细化：把报告结论绑定到具体证据片段、计算变量和人工复核记录。

需要外部输入后再做：

1. 用真实实验数据校准 `CONFIDENCE_SPREAD`、scorecard 权重和安全系数阈值。
2. 扩充材料属性库，替换 seed 占位来源。
3. 扩充 `knowledge_base/`，补足供应商资料、内部需求文档、标准摘要和实验记录。

## 8. GitHub 交接

当前远端：

```bash
git remote -v
```

应指向：

```text
https://github.com/labindustry1/material-eval-app.git
```

提交前确认：

```bash
git status -sb
git log --oneline --decorate -5
```

推送：

```bash
git push origin main
```
