"""ReasonScript Data Analysis Foundation v0.1 public API."""

from .backend import DataBackend
from .model import (
                    AggregationSpec,
                    CellValue,
                    Column,
                    DataError,
                    DatasetRef,
                    DataType,
                    Field,
                    Group,
                    GroupedTable,
                    Missing,
                    MissingValue,
                    ResourceLimits,
                    Row,
                    Schema,
                    Table,
                    canonical_json,
                    is_missing,
                    is_present,
                    stable_id,
)
from .result import TitanicAnalysisExecution, TitanicAnalysisResult
from .serialization import (
                    RESULT_SCHEMA_VERSION,
                    canonicalize_analysis_result,
                    serialize_analysis_result,
                    serialize_backend_metadata,
                    serialize_dataset_ref,
                    serialize_evidence,
                    serialize_knowledge,
                    serialize_table_summary,
                    validate_analysis_result,
)
from .titanic import TITANIC_SCHEMA, analyze_titanic, analyze_titanic_execution

__all__ = ["AggregationSpec", "CellValue", "Column", "DataBackend", "DataError", "DataType", "DatasetRef",
           "Field", "Group", "GroupedTable", "Missing", "MissingValue", "ResourceLimits", "Row", "Schema",
           "Table", "canonical_json", "is_missing", "is_present", "stable_id"]
__all__ += [
                    "RESULT_SCHEMA_VERSION",
                    "TITANIC_SCHEMA",
                    "TitanicAnalysisExecution",
                    "TitanicAnalysisResult",
                    "analyze_titanic",
                    "analyze_titanic_execution",
                    "canonicalize_analysis_result",
                    "serialize_analysis_result",
                    "serialize_backend_metadata",
                    "serialize_dataset_ref",
                    "serialize_evidence",
                    "serialize_knowledge",
                    "serialize_table_summary",
                    "validate_analysis_result",
]
