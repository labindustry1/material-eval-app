"""Lightweight MVP domain package for material feasibility evaluation."""

from material_eval.catalog import Catalog, PartTemplate
from material_eval.computation import CalculationResult, calculate_part
from material_eval.embeddings import BgeM3DenseEmbeddingProvider, EmbeddingConfig
from material_eval.evaluation import EvaluationDraft, EvaluationRequest, run_evaluation, save_evaluation
from material_eval.evidence_store import SqliteEvidenceRepository
from material_eval.ingestion import ParsedDocument, ingest_knowledge_base, parse_document
from material_eval.laminates import Lamina, LaminateStack, LaminateResult, analyze_laminate
from material_eval.material_property_library import MaterialPropertyLibrary
from material_eval.materials import MaterialCandidate
from material_eval.rag_eval import RetrievalQuestion, run_retrieval_evaluation
from material_eval.artifacts import write_markdown_report
from material_eval.report_schema import ClaimBinding, ReportClaim, StructuredReport
from material_eval.section_analysis import SectionProperties
from material_eval.scoring import ScoreDimension, Scorecard, build_scorecard
from material_eval.units import NormalizedMeasurement, normalize_material_property

__all__ = [
    "CalculationResult",
    "BgeM3DenseEmbeddingProvider",
    "Catalog",
    "ClaimBinding",
    "EmbeddingConfig",
    "EvaluationDraft",
    "EvaluationRequest",
    "Lamina",
    "LaminateResult",
    "LaminateStack",
    "MaterialCandidate",
    "MaterialPropertyLibrary",
    "NormalizedMeasurement",
    "ParsedDocument",
    "PartTemplate",
    "ReportClaim",
    "RetrievalQuestion",
    "SectionProperties",
    "ScoreDimension",
    "Scorecard",
    "SqliteEvidenceRepository",
    "StructuredReport",
    "analyze_laminate",
    "calculate_part",
    "build_scorecard",
    "ingest_knowledge_base",
    "parse_document",
    "normalize_material_property",
    "run_retrieval_evaluation",
    "run_evaluation",
    "save_evaluation",
    "write_markdown_report",
]
