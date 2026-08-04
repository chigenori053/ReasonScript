"""Canonical diagnostics model for reasonscript-diagnostics/1.0."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from typing import Any, Iterable


DIAGNOSTICS_VERSION = "1.0"
DIAGNOSTICS_SCHEMA = "reasonscript-diagnostics/1.0"

SEVERITIES = ("ERROR", "WARNING", "INFO", "HINT")
CATEGORIES = (
    "Workspace",
    "Parser",
    "Namespace",
    "Type",
    "Calculation",
    "Pattern",
    "Function",
    "Language",
    "Semantic",
    "ReasonIR",
    "ExecutionPlan",
    "Simulation",
    "Knowledge",
    "Runtime",
    "Artifact",
    "CLI",
    "Compatibility",
)
CODE_CATEGORY_PREFIXES = {
    "WS": "Workspace",
    "DG": "CLI",
    "P": "Parser",
    "PARSE": "Parser",
    "NS": "Namespace",
    "TYPE": "Type",
    "CAL": "Calculation",
    "PT": "Pattern",
    "OPM": "Pattern",
    "FN": "Function",
    "LL": "Language",
    "ST": "Language",
    "AST": "Language",
    "SEM": "Semantic",
    "IR": "ReasonIR",
    "EP": "ExecutionPlan",
    "SIM": "Simulation",
    "KN": "Knowledge",
    "RT": "Runtime",
    "RUO": "Compatibility",
    "TSF": "Runtime",
    "RUST": "Runtime",
    "AR": "Artifact",
    "ART": "Artifact",
    "CLI": "CLI",
    "RSN": "CLI",
    "STRICT": "Compatibility",
    "GT": "Compatibility",
}
KNOWN_DIAGNOSTIC_PREFIXES = tuple(sorted(CODE_CATEGORY_PREFIXES))
DIAGNOSTIC_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+[A-Z0-9-]*$")


@dataclass(frozen=True)
class SourceLocation:
    file: str
    line: int | None = None
    column: int | None = None
    length: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "length": self.length,
        }


@dataclass(frozen=True)
class DiagnosticFix:
    title: str = ""
    description: str = ""
    replacement: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "replacement": self.replacement,
        }


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    category: str
    message: str
    location: SourceLocation
    related_locations: tuple[SourceLocation, ...] = ()
    fix: DiagnosticFix | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def with_id(self, index: int) -> "Diagnostic":
        return Diagnostic(
            self.code,
            self.severity,
            self.category,
            self.message,
            self.location,
            self.related_locations,
            self.fix,
            dict(self.metadata),
            f"diag-{index:08d}",
        )

    def sort_key(self) -> tuple[Any, ...]:
        return (
            self.location.file or "",
            self.location.line if self.location.line is not None else 0,
            self.location.column if self.location.column is not None else 0,
            SEVERITIES.index(self.severity) if self.severity in SEVERITIES else len(SEVERITIES),
            self.code,
            self.message,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "location": self.location.to_dict(),
            "related_locations": [location.to_dict() for location in self.related_locations],
            "fix": self.fix.to_dict() if self.fix is not None else {},
            "metadata": dict(self.metadata),
        }


def diagnostic_from_parts(
    *,
    code: str,
    message: str,
    file: str | None,
    line: int | None = None,
    column: int | None = None,
    length: int | None = None,
    severity: str = "ERROR",
    category: str | None = None,
    related_locations: Iterable[SourceLocation] = (),
    fix: DiagnosticFix | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    canonical_severity = normalize_severity(severity)
    canonical_category = category or category_for_code(code)
    return Diagnostic(
        code=str(code),
        severity=canonical_severity,
        category=canonical_category,
        message=str(message),
        location=SourceLocation(file or "", line, column, length),
        related_locations=tuple(related_locations),
        fix=fix,
        metadata=dict(metadata or {}),
    )


def diagnostic_from_mapping(value: dict[str, Any], *, default_file: str = "") -> Diagnostic:
    metadata = dict(value.get("metadata", {})) if isinstance(value.get("metadata"), dict) else {}
    raw_code = str(value.get("code") or "CLI-000")
    code = raw_code
    if not _is_known_code(code):
        metadata.setdefault("legacy_code", raw_code)
        code = "CLI-000"
    location_value = value.get("location")
    if isinstance(location_value, dict):
        location = SourceLocation(
            str(location_value.get("file", default_file)),
            _optional_int(location_value.get("line")),
            _optional_int(location_value.get("column")),
            _optional_int(location_value.get("length")),
        )
    else:
        location = SourceLocation(
            str(value.get("file") or value.get("source_file") or value.get("relative_path") or default_file),
            _optional_int(value.get("line")),
            _optional_int(value.get("column")),
            _optional_int(value.get("length")),
        )
    related = tuple(
        SourceLocation(
            str(item.get("file", "")),
            _optional_int(item.get("line")),
            _optional_int(item.get("column")),
            _optional_int(item.get("length")),
        )
        for item in value.get("related_locations", [])
        if isinstance(item, dict)
    )
    fix_value = value.get("fix")
    fix = None
    if isinstance(fix_value, dict) and fix_value:
        fix = DiagnosticFix(
            str(fix_value.get("title", "")),
            str(fix_value.get("description", "")),
            str(fix_value.get("replacement", "")),
        )
    return diagnostic_from_parts(
        code=code,
        severity=str(value.get("severity") or "ERROR"),
        category=str(value.get("category")) if value.get("category") else None,
        message=str(value.get("message", "Unknown diagnostic")),
        file=location.file,
        line=location.line,
        column=location.column,
        length=location.length,
        related_locations=related,
        fix=fix,
        metadata=metadata,
    )


def normalize_severity(value: str) -> str:
    severity = str(value or "ERROR").upper()
    if severity == "WARN":
        return "WARNING"
    if severity not in SEVERITIES:
        return "ERROR"
    return severity


def category_for_code(code: str) -> str:
    prefix = str(code).split("-", 1)[0].upper()
    return CODE_CATEGORY_PREFIXES.get(prefix, "CLI")


def _is_known_code(code: str) -> bool:
    if DIAGNOSTIC_CODE_PATTERN.fullmatch(str(code)) is None:
        return False
    return str(code).split("-", 1)[0].upper() in CODE_CATEGORY_PREFIXES


def sort_diagnostics(diagnostics: Iterable[Diagnostic]) -> list[Diagnostic]:
    return sorted(diagnostics, key=lambda item: item.sort_key())


def canonicalize_diagnostics(diagnostics: Iterable[Diagnostic]) -> list[Diagnostic]:
    return [diagnostic.with_id(index) for index, diagnostic in enumerate(sort_diagnostics(diagnostics), start=1)]


def diagnostics_document(diagnostics: Iterable[Diagnostic | dict[str, Any]]) -> dict[str, Any]:
    normalized = [
        diagnostic if isinstance(diagnostic, Diagnostic) else diagnostic_from_mapping(diagnostic)
        for diagnostic in diagnostics
    ]
    canonical = canonicalize_diagnostics(normalized)
    return {
        "version": DIAGNOSTICS_VERSION,
        "schema": DIAGNOSTICS_SCHEMA,
        "diagnostics": [diagnostic.to_dict() for diagnostic in canonical],
    }


def diagnostics_summary(document_or_diagnostics: dict[str, Any] | Iterable[Diagnostic | dict[str, Any]]) -> dict[str, Any]:
    if isinstance(document_or_diagnostics, dict):
        diagnostics = document_or_diagnostics.get("diagnostics", [])
    else:
        diagnostics = diagnostics_document(document_or_diagnostics)["diagnostics"]
    by_severity = {severity: 0 for severity in SEVERITIES}
    by_category = {category: 0 for category in CATEGORIES}
    codes: dict[str, int] = {}
    for diagnostic in diagnostics if isinstance(diagnostics, list) else []:
        if not isinstance(diagnostic, dict):
            continue
        severity = str(diagnostic.get("severity", "ERROR"))
        category = str(diagnostic.get("category", "CLI"))
        code = str(diagnostic.get("code", ""))
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_category[category] = by_category.get(category, 0) + 1
        codes[code] = codes.get(code, 0) + 1
    return {
        "version": DIAGNOSTICS_VERSION,
        "schema": "reasonscript-diagnostics-summary/1.0",
        "total": sum(by_severity.values()),
        "by_severity": by_severity,
        "by_category": by_category,
        "codes": dict(sorted(codes.items())),
    }


def render_diagnostics(diagnostics: Iterable[dict[str, Any] | Diagnostic]) -> str:
    if not isinstance(diagnostics, list):
        diagnostics = list(diagnostics)
    document = diagnostics_document(diagnostics)
    blocks: list[str] = []
    for diagnostic in document["diagnostics"]:
        location = diagnostic["location"]
        loc = _render_location(location)
        block = f"{diagnostic['severity']} {diagnostic['code']}\n\n{diagnostic['message']}"
        if loc:
            block += f"\n\n{loc}"
        blocks.append(block)
    return "\n\n".join(blocks)


def validate_diagnostics_document(value: Any) -> list[dict[str, Any]]:
    validation: list[Diagnostic] = []
    if not isinstance(value, dict):
        return diagnostics_document([
            _validation_diag("DG-006", "Malformed JSON: expected object", file="")
        ])["diagnostics"]
    if value.get("version") != DIAGNOSTICS_VERSION:
        validation.append(_validation_diag("DG-008", f"Version mismatch: {value.get('version')}", file="diagnostics.json"))
    diagnostics = value.get("diagnostics")
    if not isinstance(diagnostics, list):
        validation.append(_validation_diag("DG-006", "Malformed JSON: diagnostics must be an array", file="diagnostics.json"))
        return diagnostics_document(validation)["diagnostics"]
    for item in diagnostics:
        if not isinstance(item, dict):
            validation.append(_validation_diag("DG-006", "Malformed JSON: diagnostic must be an object", file="diagnostics.json"))
            continue
        validation.extend(_validate_diagnostic_item(item))
    if not _is_deterministically_ordered(diagnostics):
        validation.append(_validation_diag("DG-010", "Non-deterministic ordering", file="diagnostics.json"))
    return diagnostics_document(validation)["diagnostics"]


def validate_diagnostic_registry(codes: Iterable[str]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    validation: list[Diagnostic] = []
    for code in codes:
        if code in seen:
            validation.append(_validation_diag("DG-002", f"Duplicate code: {code}", file="diagnostic_registry"))
        seen.add(code)
    return diagnostics_document(validation)["diagnostics"]


def sort_diagnostic_mappings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return diagnostics_document(items)["diagnostics"]


def _is_deterministically_ordered(items: list[dict[str, Any]]) -> bool:
    diagnostics = [diagnostic_from_mapping(item) for item in items if isinstance(item, dict)]
    return [diagnostic.sort_key() for diagnostic in diagnostics] == [
        diagnostic.sort_key() for diagnostic in sort_diagnostics(diagnostics)
    ]


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _validate_diagnostic_item(item: dict[str, Any]) -> list[Diagnostic]:
    validation: list[Diagnostic] = []
    code = item.get("code")
    if not isinstance(code, str) or not code:
        validation.append(_validation_diag("DG-001", "Missing diagnostic code", file="diagnostics.json"))
    elif not _is_known_code(code):
        validation.append(_validation_diag("DG-009", f"Unknown diagnostic code: {code}", file="diagnostics.json"))
    if item.get("severity") not in SEVERITIES:
        validation.append(_validation_diag("DG-003", f"Invalid severity: {item.get('severity')}", file="diagnostics.json"))
    location = item.get("location")
    if not isinstance(location, dict) or not location.get("file"):
        validation.append(_validation_diag("DG-004", "Missing location", file="diagnostics.json"))
    category = item.get("category")
    if category not in CATEGORIES:
        validation.append(_validation_diag("DG-005", f"Invalid category: {category}", file="diagnostics.json"))
    fix = item.get("fix", {})
    if fix not in ({}, None) and not isinstance(fix, dict):
        validation.append(_validation_diag("DG-007", "Invalid fix", file="diagnostics.json"))
    return validation


def _validation_diag(code: str, message: str, *, file: str) -> Diagnostic:
    return diagnostic_from_parts(
        code=code,
        severity="ERROR",
        category="CLI",
        message=message,
        file=file,
        metadata={"rule": code},
    )


def _render_location(location: dict[str, Any]) -> str:
    file = str(location.get("file") or "")
    if not file:
        return ""
    line = location.get("line")
    column = location.get("column")
    if line is None:
        return file
    if column is None:
        return f"{file}:{line}"
    return f"{file}:{line}:{column}"


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
