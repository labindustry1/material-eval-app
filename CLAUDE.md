# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Internal MVP for material feasibility screening (材料应用可行性初筛). Streamlit UI, deterministic engineering calculations, BM25/optional BGE-M3 retrieval over an internal knowledge base, local Markdown report generation with optional OpenAI polish.

The active app entrypoint is `app.py` → `material_eval.ui_streamlit:run_app`. The legacy Streamlit prototype and old RAG/SQLite demo connectors live in `legacy/` and are not used by the current MVP.

## Commands

```bash
# setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# run
streamlit run app.py

# tests (all)
python3 -m unittest discover -s tests -p 'test_*.py' -v

# single test file / single test
python3 -m unittest tests.test_evaluation_workflow -v
python3 -m unittest tests.test_evaluation_workflow.TestEvaluationWorkflow.test_<name> -v

# optional BGE-M3 dense retrieval
pip install FlagEmbedding   # or: uv pip install '.[bge]'
```

Relevant env vars (see `.env.example`): `MVP_ACCESS_CODE`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `BGE_M3_*`. Without `OPENAI_API_KEY` the system falls back to a deterministic local Chinese report — this is the expected default for the MVP.

Requires Python ≥ 3.12.

## Architecture

The `material_eval/` package is structured so calculation, retrieval, reporting, scoring, and storage stay decoupled. The big-picture flow (orchestrated in `evaluation.py::run_evaluation`):

1. **Catalog + materials** (`catalog.py`, `materials.py`, `material_property_library.py`) — seed-driven domain/part templates from `data/seed/domain_config.json` and a basis material library from `data/seed/material_property_library.json`. Material properties carry source, condition, and confidence metadata.
2. **Units** (`units.py`) — Pint-based normalization and dimensional checks. All engineering inputs are converted to canonical SI before any calculation. Don't bypass this when adding new properties or formulas.
3. **Deterministic calculation** (`computation.py`, `section_analysis.py`, `laminates.py`) — closed-form BEAM/PLATE/STRAP modules; `sectionproperties` adapter for tube/I-beam/plate cross-sections with closed-form fallback; Classical Laminate Theory A-matrix for composites. There is no real CAE/FEA — visualizations are just deterministic calc results.
4. **Evidence / retrieval** (`ingestion.py`, `evidence_store.py`, `embeddings.py`, `evidence.py`, `rag_eval.py`) — Docling parses md/html/pdf/docx/pptx from `knowledge_base/`; chunks + optional BGE-M3 embeddings are cached in SQLite (`documents`, `document_chunks`, `chunk_embeddings`). Default retrieval is `rank-bm25`; dense is optional and lazy-loaded. `rag_eval.py` runs a fixed question set against retrieval.
5. **Report + schema** (`reporting.py`, `report_schema.py`) — local Chinese Markdown report; `report_schema.py` defines Pydantic models for the structured report, claims, and source bindings (each claim binds to a calc metric, evidence card, laminate result, or manual rule).
6. **Scoring** (`scoring.py`) — transparent rule-based scorecard across data confidence, intrinsic performance, structural fit, condition risk, process maturity, compliance.
7. **Storage** (`storage.py`) — SQLite repository at `data/mvp.sqlite3` for evaluation runs + review state. Optional OpenAI polish via `openai_provider.py`.
8. **UI** (`ui_streamlit.py`) — the only place that touches Streamlit; keep widgets/rendering out of the other modules.

### Storage boundary (important)

The MVP is locked to SQLite to keep deployment trivial. A Supabase/Postgres+pgvector schema is already drafted at `supabase/migrations/20260507145720_material_eval_core.sql` (see `docs/supabase-production-schema.md`). When adding persistence, keep the abstraction at `material_eval/storage.py` clean — do not leak Supabase- or SQLite-specific logic into calculation, report, or UI modules. The future Supabase adapter will plug in here.

### What this MVP is not

- Not production / certification / customer-facing — results are internal R&D screening only.
- No real CAE simulation.
- Composite estimates use linear rule-of-mixtures + CLT A-matrix only; no ply-level failure, interface, voids, fatigue, or environmental degradation modeling.

## Conventions

- Seed data lives in `data/seed/`. Adding a new industry/part means extending `domain_config.json` and (if it introduces a new topology) wiring a calculator in `computation.py`.
- New material properties must declare unit, condition, source, confidence and round-trip through `units.py` to produce canonical values before reaching calculation code.
- Tests use stdlib `unittest` (despite `pytest` config in `pyproject.toml`); follow that pattern for new tests.
- See `docs/target-architecture-v1.md` and `docs/material-eval-refactor-prd.md` for the intended architecture and refactor scope; `docs/implementation-log.md` tracks progress.
