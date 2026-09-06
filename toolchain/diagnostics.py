"""Canonical diagnostics model for reasonscript-diagnostics/1.0."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DIAGNOSTICS_VERSION = "1.0"
DIAGNOSTICS_SCHEMA = "reasonscript-diagnostics/1.0"


def _load_toolchain_version() -> str:
    try:
        root = Path(__file__).resolve().parents[1]
        version_file = root / "VERSION"
        if version_file.is_file():
            return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "0.5.5.11"


COMPILER_VERSION = _load_toolchain_version()
RUNTIME_VERSION = COMPILER_VERSION

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
    # Classifications required by Issue #41
    "Source",
    "Project",
    "Lexer",
    "Build",
    "ICE",
)
CODE_CATEGORY_PREFIXES = {
    # Official classifications (Issue #41):
    # CLI / SRC / PRJ / LEX / PAR / NAM / TYP / BLD / RUN / ICE
    "CLI": "CLI",
    "SRC": "Source",
    "PRJ": "Project",
    "LEX": "Lexer",
    "PAR": "Parser",
    "NAM": "Namespace",
    "TYP": "Type",
    "BLD": "Build",
    "RUN": "Runtime",
    "ICE": "ICE",
    # Legacy prefixes preserved for compatibility:
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
    "RSN": "CLI",
    "STRICT": "Compatibility",
    "GT": "Compatibility",
}
KNOWN_DIAGNOSTIC_PREFIXES = tuple(sorted(CODE_CATEGORY_PREFIXES))
DIAGNOSTIC_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+[A-Z0-9-]*$")


@dataclass(frozen=True)
class DiagnosticDefinition:
    """Canonical definition of a compiler / toolchain diagnostic code."""

    code: str
    category: str
    severity: str = "ERROR"
    title: str = ""
    description: str = ""
    default_help: str = ""
    legacy_aliases: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "default_help": self.default_help,
            "legacy_aliases": list(self.legacy_aliases),
        }


class DiagnosticRegistry:
    """Catalog managing all diagnostic codes, metadata, and backward compatibility aliases."""

    def __init__(self) -> None:
        self._definitions: dict[str, DiagnosticDefinition] = {}
        self._alias_to_code: dict[str, str] = {}

    def register(self, definition: DiagnosticDefinition) -> None:
        canonical = definition.code
        self._definitions[canonical] = definition
        self._alias_to_code[canonical] = canonical
        for alias in definition.legacy_aliases:
            self._alias_to_code[alias] = canonical

    def get(self, code_or_alias: str) -> DiagnosticDefinition | None:
        canonical = self._alias_to_code.get(code_or_alias, code_or_alias)
        return self._definitions.get(canonical)

    def canonical_code(self, code_or_alias: str) -> str:
        return self._alias_to_code.get(code_or_alias, code_or_alias)

    def all_definitions(self) -> tuple[DiagnosticDefinition, ...]:
        return tuple(sorted(self._definitions.values(), key=lambda d: d.code))

    def all_codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions.keys()))

    def validate(self) -> list[Diagnostic]:
        issues: list[Diagnostic] = []
        for defn in self._definitions.values():
            if not _is_known_code(defn.code):
                issues.append(_validation_diag("DG-009", f"Unknown diagnostic code: {defn.code}", file="diagnostic_registry"))
            if defn.severity not in SEVERITIES:
                issues.append(_validation_diag("DG-003", f"Invalid severity: {defn.severity}", file="diagnostic_registry"))
            if defn.category not in CATEGORIES:
                issues.append(_validation_diag("DG-005", f"Invalid category: {defn.category}", file="diagnostic_registry"))
        return issues


def _init_default_registry() -> DiagnosticRegistry:
    registry = DiagnosticRegistry()

    # CLI
    registry.register(DiagnosticDefinition(
        code="CLI-0001", category="CLI", severity="ERROR",
        title="Command-line argument error",
        description="Unknown option or invalid arguments provided to CLI.",
        default_help="Run with --help to view available commands and options.",
    ))
    registry.register(DiagnosticDefinition(
        code="CLI-0002", category="CLI", severity="ERROR",
        title="Missing required CLI argument",
        description="A required positional argument or flag was omitted.",
        default_help="Specify the required path or option.",
    ))
    registry.register(DiagnosticDefinition(
        code="CLI-0003", category="CLI", severity="ERROR",
        title="I/O or file system error",
        description="Unable to read or write file specified in command line.",
        default_help="Verify file path and permissions.",
    ))

    # Source (SRC)
    registry.register(DiagnosticDefinition(
        code="SRC-0001", category="Source", severity="WARNING",
        title="Source file naming or extension warning",
        description="ReasonScript source files should use the .rsn extension.",
        default_help="Rename file with a .rsn suffix.",
    ))
    registry.register(DiagnosticDefinition(
        code="SRC-0002", category="Source", severity="ERROR",
        title="No source files found",
        description="No .rsn files found in src/ or specified directory.",
        default_help="Add valid .rsn source files to the src/ directory.",
    ))
    registry.register(DiagnosticDefinition(
        code="SRC-0003", category="Source", severity="ERROR",
        title="Source entry missing",
        description="Target source file is not found in package.",
        default_help="Ensure source file exists at the expected path.",
    ))
    registry.register(DiagnosticDefinition(
        code="SRC-0004", category="Source", severity="ERROR",
        title="Source file migration conflict",
        description="Target .rsn file already exists or multiple sources map to the same destination.",
        default_help="Resolve the file conflict before migrating extensions.",
    ))
    registry.register(DiagnosticDefinition(
        code="SRC-0005", category="Source", severity="ERROR",
        title="Unsupported or invalid migration target",
        description="File cannot be migrated due to unsupported format, symlink, or permission issue.",
        default_help="Ensure the file is a regular file and a valid legacy ReasonScript source.",
    ))

    # Project (PRJ)
    registry.register(DiagnosticDefinition(
        code="PRJ-0001", category="Project", severity="ERROR",
        title="Project manifest error",
        description="Failed to parse or validate reason.toml manifest.",
        default_help="Ensure reason.toml contains valid TOML syntax conforming to package schema.",
    ))
    registry.register(DiagnosticDefinition(
        code="PRJ-0002", category="Project", severity="ERROR",
        title="Workspace dependency cycle",
        description="Circular dependency detected between workspace packages.",
        default_help="Remove circular dependencies.",
    ))
    registry.register(DiagnosticDefinition(
        code="PRJ-0003", category="Project", severity="ERROR",
        title="Unknown workspace package",
        description="Requested package is not defined in workspace.",
        default_help="Check package name against reason.toml workspace members.",
    ))

    # Lexer (LEX)
    registry.register(DiagnosticDefinition(
        code="LEX-0001", category="Lexer", severity="ERROR",
        title="Lexical error",
        description="Unsupported character or illegal byte sequence.",
        default_help="Remove or replace unsupported character.",
    ))
    registry.register(DiagnosticDefinition(
        code="LEX-0002", category="Lexer", severity="ERROR",
        title="Unterminated string literal",
        description="String literal was opened but not closed before newline or EOF.",
        default_help="Add closing quote.",
    ))
    registry.register(DiagnosticDefinition(
        code="LEX-0003", category="Lexer", severity="ERROR",
        title="Malformed number literal",
        description="Numeric literal contains invalid digits or formatting.",
        default_help="Check number format.",
    ))

    # Parser (PAR)
    registry.register(DiagnosticDefinition(
        code="PAR-0001", category="Parser", severity="ERROR",
        title="Syntax error",
        description="Failed to parse token sequence into valid AST.",
        default_help="Check syntax rules and brace balancing.",
    ))
    registry.register(DiagnosticDefinition(
        code="PAR-0002", category="Parser", severity="ERROR",
        title="Reserved construct",
        description="Construct is reserved for future features and not active in v0.6-D.",
        default_help="Use model or module instead.",
        legacy_aliases=("LL-002-RESERVED-TOP-LEVEL-CONSTRUCT",),
    ))
    registry.register(DiagnosticDefinition(
        code="PAR-0003", category="Parser", severity="ERROR",
        title="Unexpected delimiter or block",
        description="Unmatched delimiter or unexpected token encountered.",
        default_help="Check matching delimiters.",
    ))
    registry.register(DiagnosticDefinition(
        code="PAR-0004", category="Parser", severity="ERROR",
        title="Invalid package declaration",
        description="Package declaration must precede module/model definitions.",
        default_help="Place package declaration at top of file without semicolon.",
        legacy_aliases=("PV-1",),
    ))

    # Namespace (NAM)
    registry.register(DiagnosticDefinition(
        code="NAM-0001", category="Namespace", severity="ERROR",
        title="Namespace resolution error",
        description="Duplicate symbol or ambiguous declaration.",
        default_help="Ensure symbols have unique names within module/package.",
        legacy_aliases=("NS-001", "NS-V002", "NS-040"),
    ))
    registry.register(DiagnosticDefinition(
        code="NAM-0002", category="Namespace", severity="ERROR",
        title="Module not found",
        description="Imported module could not be found in package or dependencies.",
        default_help="Verify module name and import path.",
        legacy_aliases=("PV-4",),
    ))
    registry.register(DiagnosticDefinition(
        code="NAM-0003", category="Namespace", severity="ERROR",
        title="Unknown symbol",
        description="Symbol referenced does not exist in target module or scope.",
        default_help="Verify symbol spelling and availability.",
        legacy_aliases=("NS-020", "NS-V003"),
    ))
    registry.register(DiagnosticDefinition(
        code="NAM-0004", category="Namespace", severity="ERROR",
        title="Visibility violation",
        description="Cannot access private symbol from another module.",
        default_help="Add 'pub' keyword to make the target symbol public.",
    ))
    registry.register(DiagnosticDefinition(
        code="NAM-0005", category="Namespace", severity="ERROR",
        title="Ambiguous symbol reference",
        description="Symbol is ambiguous due to conflicting imports.",
        default_help="Use fully qualified path to refer to the symbol.",
    ))
    registry.register(DiagnosticDefinition(
        code="NAM-2004", category="Namespace", severity="ERROR",
        title="Unsupported JavaScript API",
        description="ReasonScript does not support JavaScript runtime APIs such as Js.*.",
        default_help="Use ReasonScript standard output API 'Console.log' or 'print' instead.",
    ))

    # Type (TYP)
    registry.register(DiagnosticDefinition(
        code="TYP-0001", category="Type", severity="ERROR",
        title="Type validation error",
        description="Type mismatch or unsupported operation on type.",
        default_help="Ensure types match expected signature.",
    ))
    registry.register(DiagnosticDefinition(
        code="TYP-0002", category="Type", severity="ERROR",
        title="Function return type mismatch",
        description="Returned expression does not match function return type annotation.",
        default_help="Cast or change return expression to expected type.",
        legacy_aliases=("FN-005",),
    ))
    registry.register(DiagnosticDefinition(
        code="TYP-0003", category="Type", severity="ERROR",
        title="Struct field type mismatch",
        description="Field value does not match struct definition.",
        default_help="Provide field with matching type.",
    ))
    registry.register(DiagnosticDefinition(
        code="TYP-0004", category="Type", severity="ERROR",
        title="Pattern matching type mismatch",
        description="Pattern type does not match inspected expression.",
        default_help="Ensure pattern matches expression type.",
    ))

    # Build (BLD)
    registry.register(DiagnosticDefinition(
        code="BLD-0001", category="Build", severity="ERROR",
        title="Build compilation error",
        description="Failed to lower surface AST to ReasonIR.",
        default_help="Check language surface constructs for IR lowerability.",
    ))
    registry.register(DiagnosticDefinition(
        code="BLD-0002", category="Build", severity="ERROR",
        title="Artifact emission error",
        description="Failed to generate or serialize build artifacts.",
        default_help="Verify destination directory permissions and disk space.",
    ))

    # Runtime (RUN)
    registry.register(DiagnosticDefinition(
        code="RUN-0001", category="Runtime", severity="ERROR",
        title="Runtime execution error",
        description="Unhandled runtime error or panic during execution.",
        default_help="Check runtime preconditions and input arguments.",
    ))
    registry.register(DiagnosticDefinition(
        code="RUN-0002", category="Runtime", severity="ERROR",
        title="Assertion failure",
        description="Runtime assertion or reach goal was not met.",
        default_help="Inspect simulation trace.",
    ))
    registry.register(DiagnosticDefinition(
        code="RUN-0003", category="Runtime", severity="ERROR",
        title="Resource limit exceeded",
        description="Execution exceeded maximum step or memory limit.",
        default_help="Optimize algorithm or increase resource limit.",
    ))

    # Internal Compiler Error (ICE)
    registry.register(DiagnosticDefinition(
        code="ICE-0001", category="ICE", severity="ERROR",
        title="Internal compiler error",
        description="Unexpected compiler panic or unhandled internal exception.",
        default_help="Report issue with reproducing source code.",
    ))

    return registry


DEFAULT_REGISTRY = _init_default_registry()


def normalize_path(path: str | Path | None, base_dir: Path | None = None) -> str:
    if not path:
        return ""
    p = Path(path)
    if base_dir is not None and p.is_absolute():
        try:
            p = p.relative_to(base_dir)
        except ValueError:
            pass
    return p.as_posix()


@dataclass(frozen=True)
class SourcePosition:
    line: int  # 1-indexed
    column: int  # 1-indexed
    offset: int | None = None  # 0-indexed byte offset

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "line": self.line,
            "column": self.column,
        }
        if self.offset is not None:
            result["offset"] = self.offset
        return result


@dataclass(frozen=True)
class SourceSpan:
    start: SourcePosition
    end: SourcePosition

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
        }


@dataclass(frozen=True)
class SourceLocation:
    file: str
    line: int | None = None
    column: int | None = None
    length: int | None = None
    uri: str | None = None
    span: SourceSpan | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "length": self.length,
        }
        if self.uri:
            result["uri"] = self.uri
        if self.span is not None:
            result["span"] = self.span.to_dict()
            result["start"] = self.span.start.to_dict()
            result["end"] = self.span.end.to_dict()
        return result


@dataclass(frozen=True)
class DiagnosticFix:
    title: str = ""
    description: str = ""
    replacement: str = ""
    span: SourceSpan | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "title": self.title,
            "description": self.description,
            "replacement": self.replacement,
        }
        if self.span is not None:
            result["span"] = self.span.to_dict()
        return result


def create_fix(
    title: str,
    replacement: str,
    *,
    span: SourceSpan | None = None,
    description: str = "",
) -> DiagnosticFix:
    """Create a structured diagnostic fix candidate."""
    return DiagnosticFix(
        title=title,
        description=description,
        replacement=replacement,
        span=span,
    )


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    category: str
    message: str
    location: SourceLocation
    related_locations: tuple[SourceLocation, ...] = ()
    fix: DiagnosticFix | None = None
    fixes: tuple[DiagnosticFix, ...] = ()
    title: str = ""
    help: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = ""

    def with_id(self, index: int) -> Diagnostic:
        return Diagnostic(
            self.code,
            self.severity,
            self.category,
            self.message,
            self.location,
            self.related_locations,
            self.fix,
            self.fixes,
            self.title,
            self.help,
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
        fix_dict = self.fix.to_dict() if self.fix is not None else {}
        fixes_list = [f.to_dict() for f in self.fixes] if self.fixes else ([fix_dict] if fix_dict else [])
        result: dict[str, Any] = {
            "id": self.id,
            "code": self.code,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "location": self.location.to_dict(),
            "related_locations": [loc.to_dict() for loc in self.related_locations],
            "fix": fix_dict,
            "metadata": dict(self.metadata),
        }
        if self.title:
            result["title"] = self.title
        if self.help:
            result["help"] = self.help
        if fixes_list:
            result["fix_candidates"] = fixes_list
        return result


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
    fixes: Iterable[DiagnosticFix] = (),
    title: str = "",
    help: str = "",
    uri: str | None = None,
    span: SourceSpan | None = None,
    metadata: dict[str, Any] | None = None,
) -> Diagnostic:
    defn = DEFAULT_REGISTRY.get(code)
    canonical_severity = normalize_severity(severity)
    canonical_category = category or (defn.category if defn else category_for_code(code))
    resolved_title = title or (defn.title if defn else "")
    resolved_help = help or (defn.default_help if defn else "")
    normalized_file = normalize_path(file) if file else ""
    canonical_uri = uri or (f"file://{normalized_file}" if normalized_file and not normalized_file.startswith("file://") else normalized_file)
    fixes_tuple = tuple(fixes)
    effective_fix = fix or (fixes_tuple[0] if fixes_tuple else None)
    return Diagnostic(
        code=str(code),
        severity=canonical_severity,
        category=canonical_category,
        message=str(message),
        location=SourceLocation(
            file=normalized_file,
            line=line,
            column=column,
            length=length,
            uri=canonical_uri if canonical_uri else None,
            span=span,
        ),
        related_locations=tuple(related_locations),
        fix=effective_fix,
        fixes=fixes_tuple,
        title=str(resolved_title),
        help=str(resolved_help),
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
    span: SourceSpan | None = None
    uri: str | None = None
    if isinstance(location_value, dict):
        loc_file = str(location_value.get("file", default_file))
        loc_line = _optional_int(location_value.get("line"))
        loc_col = _optional_int(location_value.get("column"))
        loc_len = _optional_int(location_value.get("length"))
        uri = location_value.get("uri")
        span_dict = location_value.get("span")
        if isinstance(span_dict, dict) and "start" in span_dict and "end" in span_dict:
            start_d = span_dict["start"]
            end_d = span_dict["end"]
            span = SourceSpan(
                start=SourcePosition(line=start_d.get("line", 1), column=start_d.get("column", 1), offset=_optional_int(start_d.get("offset"))),
                end=SourcePosition(line=end_d.get("line", 1), column=end_d.get("column", 1), offset=_optional_int(end_d.get("offset"))),
            )
        location = SourceLocation(
            normalize_path(loc_file),
            loc_line,
            loc_col,
            loc_len,
            uri=str(uri) if uri else None,
            span=span,
        )
    else:
        raw_file = str(value.get("file") or value.get("source_file") or value.get("relative_path") or default_file)
        location = SourceLocation(
            normalize_path(raw_file),
            _optional_int(value.get("line")),
            _optional_int(value.get("column")),
            _optional_int(value.get("length")),
        )
    related = tuple(
        SourceLocation(
            normalize_path(str(item.get("file", ""))),
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
    fixes_list: list[DiagnosticFix] = []
    candidates = value.get("fix_candidates")
    if isinstance(candidates, list):
        for c in candidates:
            if isinstance(c, dict):
                fixes_list.append(DiagnosticFix(
                    title=str(c.get("title", "")),
                    description=str(c.get("description", "")),
                    replacement=str(c.get("replacement", "")),
                ))
    title = str(value.get("title", ""))
    help_msg = str(value.get("help", ""))
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
        fixes=fixes_list,
        title=title,
        help=help_msg,
        uri=location.uri,
        span=location.span,
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


def diagnostics_document(
    diagnostics: Iterable[Diagnostic | dict[str, Any]],
    *,
    compiler_version: str = COMPILER_VERSION,
    runtime_version: str = RUNTIME_VERSION,
) -> dict[str, Any]:
    normalized = [
        diagnostic if isinstance(diagnostic, Diagnostic) else diagnostic_from_mapping(diagnostic)
        for diagnostic in diagnostics
    ]
    canonical = canonicalize_diagnostics(normalized)
    return {
        "version": DIAGNOSTICS_VERSION,
        "schema": DIAGNOSTICS_SCHEMA,
        "compiler_version": compiler_version,
        "runtime_version": runtime_version,
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
        title_suffix = f": {diagnostic['title']}" if diagnostic.get("title") else ""
        block = f"{diagnostic['severity']} {diagnostic['code']}{title_suffix}\n\n{diagnostic['message']}"
        if loc:
            block += f"\n\n{loc}"
        if diagnostic.get("help"):
            block += f"\n\nhelp: {diagnostic['help']}"
        fixes = diagnostic.get("fix_candidates") or ([diagnostic["fix"]] if diagnostic.get("fix") else [])
        for f in fixes:
            if isinstance(f, dict) and f.get("title") and f.get("replacement"):
                block += f"\n\nsuggested fix: {f['title']}\n  {f['replacement']}"
        blocks.append(block)
    return "\n\n".join(blocks)


def position_to_lsp(line: int | None, column: int | None) -> dict[str, int]:
    """Convert 1-based line/column to 0-based LSP position."""
    l = max((line or 1) - 1, 0)
    c = max((column or 1) - 1, 0)
    return {"line": l, "character": c}


def position_from_lsp(line: int, character: int) -> tuple[int, int]:
    """Convert 0-based LSP position to 1-based line/column."""
    return (line + 1, character + 1)


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


def validate_diagnostic_registry(codes: Iterable[str] | None = None) -> list[dict[str, Any]]:
    if codes is None:
        codes = DEFAULT_REGISTRY.all_codes()
    seen: set[str] = set()
    validation: list[Diagnostic] = []
    for code in codes:
        if code in seen:
            validation.append(_validation_diag("DG-002", f"Duplicate code: {code}", file="diagnostic_registry"))
        elif not _is_known_code(code):
            validation.append(_validation_diag("DG-009", f"Unknown diagnostic code: {code}", file="diagnostic_registry"))
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
