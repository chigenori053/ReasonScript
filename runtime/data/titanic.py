"""DAF-8 direct Titanic CSV regression implemented entirely through DataBackend."""
from pathlib import Path
from typing import Any
from .backend import DataBackend
from .model import Field, Schema
from .result import TitanicAnalysisExecution, TitanicAnalysisResult
from .serialization import serialize_analysis_result

TITANIC_SCHEMA = Schema(tuple(Field(name, dtype, nullable) for name, dtype, nullable in (
    ("PassengerId", "int", False), ("Survived", "int", False), ("Pclass", "int", False),
    ("Name", "string", False), ("Sex", "string", False), ("Age", "float", True),
    ("SibSp", "int", False), ("Parch", "int", False), ("Ticket", "string", False),
    ("Fare", "float", True), ("Cabin", "string", True), ("Embarked", "string", True))))

def analyze_titanic_execution(path: str | Path, *, project_root: str | Path | None = None) -> TitanicAnalysisExecution:
    path = Path(path); backend = DataBackend(project_root=project_root or path.parent)
    table = backend.load_csv(path.name if project_root is None else path, TITANIC_SCHEMA)
    table = backend.derive_column(table, "FamilySize", "int", False, lambda r: r["SibSp"] + r["Parch"] + 1,
        referenced_columns=("SibSp", "Parch"), expression="SibSp + Parch + 1")
    table = backend.derive_column(table, "IsAlone", "bool", False, lambda r: r["FamilySize"] == 1,
        referenced_columns=("FamilySize",), expression="FamilySize == 1")
    female = backend.filter(table, lambda r: r["Sex"] == "female", name="IsFemale", referenced_columns=("Sex",))
    male = backend.filter(table, lambda r: r["Sex"] == "male", name="IsMale", referenced_columns=("Sex",))
    alone = backend.filter(table, lambda r: r["IsAlone"], name="IsAlone", referenced_columns=("IsAlone",))
    not_alone = backend.filter(table, lambda r: not r["IsAlone"], name="NotAlone", referenced_columns=("IsAlone",))
    metrics = {"row_count": table.row_count, "column_count": 12, "overall_survival_rate": backend.mean(table, "Survived"),
        "female_survival_rate": backend.mean(female, "Survived"), "male_survival_rate": backend.mean(male, "Survived"),
        "age_missing_count": backend.count_missing(table, "Age"), "cabin_missing_count": backend.count_missing(table, "Cabin"),
        "embarked_missing_count": backend.count_missing(table, "Embarked"), "fare_missing_count": backend.count_missing(table, "Fare"),
        "mean_age": backend.mean(table, "Age"), "median_age": backend.median(table, "Age"),
        "min_age": backend.min(table, "Age"), "max_age": backend.max(table, "Age"),
        "mean_fare": backend.mean(table, "Fare"), "median_fare": backend.median(table, "Fare"),
        "min_fare": backend.min(table, "Fare"), "max_fare": backend.max(table, "Fare"),
        "is_alone_count": alone.row_count, "not_alone_count": not_alone.row_count,
        "alone_survival_rate": backend.mean(alone, "Survived"), "not_alone_survival_rate": backend.mean(not_alone, "Survived")}
    for pclass in (1, 2, 3):
        subset = backend.filter(table, lambda r, p=pclass: r["Pclass"] == p, name=f"Pclass{pclass}", referenced_columns=("Pclass",))
        metrics[f"pclass_{pclass}_survival_rate"] = backend.mean(subset, "Survived")
    definitions = (("KDA-K001", "Dataset Profile", {"rows": table.row_count, "columns": 12}),
        ("KDA-K002", "Overall Survival", metrics["overall_survival_rate"]),
        ("KDA-K003", "Sex Survival Difference", metrics["female_survival_rate"] - metrics["male_survival_rate"]),
        ("KDA-K004", "Passenger Class Difference", [metrics[f"pclass_{p}_survival_rate"] for p in (1, 2, 3)]),
        ("KDA-K005", "Missing-value Profile", {k: metrics[k] for k in ("age_missing_count", "cabin_missing_count", "embarked_missing_count", "fare_missing_count")}),
        ("KDA-K006", "Family Feature Profile", {"alone": alone.row_count, "not_alone": not_alone.row_count}),
        ("KDA-K007", "Alone Survival Difference", metrics["not_alone_survival_rate"] - metrics["alone_survival_rate"]))
    evidence = backend.evidence(table, operation_refs=[x["operation_id"] for x in table.provenance])
    knowledge = [{"knowledge_id": kid, "statement": statement, "value": value, "unit": None, "confidence": 1.0,
        "evidence_refs": [evidence["evidence_id"]], "dataset_refs": [table.source_ref.dataset_id]} for kid, statement, value in definitions]
    public = serialize_analysis_result(status="pass", input_mode="CSV_DIRECT", backend=backend, table=table,
        metrics=metrics, knowledge=knowledge, evidence=evidence, project_root=backend.project_root)
    return TitanicAnalysisExecution(TitanicAnalysisResult(public), table, backend)


def analyze_titanic(path: str | Path, *, project_root: str | Path | None = None) -> dict[str, Any]:
    """Analyze Titanic CSV data and return only the JSON-safe public result."""
    return analyze_titanic_execution(path, project_root=project_root).result.to_dict()
