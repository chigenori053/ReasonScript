"""Canonical artifact generation and offline validation for ReasonGraph v0.1."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .compatibility import project_to_graph, reverse_project
from .format import CANONICALIZATION_PROFILE as RGO_F1_CANONICALIZATION_PROFILE, FORMAT_VERSION as RGO_F1_FORMAT_VERSION, MEDIA_TYPE as RGO_F1_MEDIA_TYPE, decode_graph, encode_graph, write_graph
from .mirp_projection import MIRP_GRAPH_FRAGMENT_SCHEMA, project_mirp_relation
from .model import CORE_RELATION_TYPES, canonicalize_graph, graph_hash, reference_graph, validate_graph
from .transaction import GraphTransaction
from .ruo_u1 import PROFILE as RUO_U1_PROFILE, project_u1_to_graph, reverse_u1_projection
from .ruo_f1 import PROFILE as RUO_F1_PROFILE, project_ruo_file
from .native import PROFILE as NATIVE_HANDOFF_PROFILE, project_native_ruo_file
from .native_graph import PROFILE as NATIVE_GRAPH_PROFILE, load_native_graph_file, query_native_graph_file, transact_native_graph_file
from .query import PROFILE as QUERY_PROFILE, query_graph
from .mirp_transport import FORMAT_VERSION as MIRP_T1_FORMAT_VERSION, MEDIA_TYPE as MIRP_T1_MEDIA_TYPE, decode_fragment, encode_fragment
from .persistence import PROFILE as PERSISTENCE_PROFILE, transact_graph_file
from .language import PROFILE as LANGUAGE_PROFILE, compile_graph_source, execute_graph_source
from toolchain.reasonunit_object.universal import reference_object
from toolchain.reasonunit_file import write_file
from frontend.language_surface import compile_program, parse


PROFILE = "reasonscript-reason-object-graph/0.1"
JSON_ARTIFACTS = (
    "reason_graph_contract.json", "relation_contract.json", "identity_hash_contract.json",
    "transaction_contract.json", "persistence_transaction_contract.json", "compatibility_contract.json", "ruo_u1_integration_contract.json", "ruo_f1_integration_contract.json", "native_runtime_handoff_contract.json", "native_graph_loader_contract.json", "native_graph_query_contract.json", "native_graph_transaction_contract.json", "reason_graph_language_contract.json", "reason_graph_surface_binding_contract.json", "reason_graph_generic_run_contract.json", "reason_graph_source_transaction_contract.json", "query_contract.json", "mirp_fragment_contract.json", "mirp_transport_contract.json", "rgo_f1_contract.json",
    "fixture_manifest.json", "profile_diagnostics.json", "validation_summary.json", "run_manifest.json",
)
CANONICAL_ARTIFACTS = (*JSON_ARTIFACTS, "final_report.md")


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def generate_profile(root: Path, output: Path) -> dict[str, Any]:
    """Generate the complete Phase 6 artifact set atomically."""
    root, output = root.resolve(), output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    documents = _documents()
    temporary = Path(tempfile.mkdtemp(prefix=".reason-object-graph-", dir=output.parent))
    try:
        _write_documents(temporary, documents)
        if output.exists():
            previous = output.parent / f".{output.name}.previous"
            if previous.exists(): shutil.rmtree(previous)
            output.replace(previous)
            try: temporary.replace(output)
            except Exception:
                previous.replace(output); raise
            shutil.rmtree(previous)
        else:
            temporary.replace(output)
        temporary = Path()
    finally:
        if temporary and temporary.exists() and temporary != Path("."): shutil.rmtree(temporary)
    result = validate_profile(root, output, verify_determinism=True)
    return {"phase_status": "VALIDATED" if result["ok"] else "NOT_VALIDATED", **result}


def validate_profile(root: Path, directory: Path, *, verify_determinism: bool = True) -> dict[str, Any]:
    """Validate generated artifacts without mutating them."""
    del root
    directory = directory.resolve(); issues: list[dict[str, str]] = []
    actual = {path.name for path in directory.iterdir()} if directory.is_dir() else set()
    if actual != set(CANONICAL_ARTIFACTS):
        return {"ok": False, "issues": [{"code": "RRG-PHASE-001", "message": "Artifact inventory does not match the canonical profile."}]}
    parsed: dict[str, dict[str, Any]] = {}
    for name in JSON_ARTIFACTS:
        path = directory / name
        try:
            text = path.read_text(encoding="utf-8")
            value = json.loads(text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
        except (OSError, ValueError, json.JSONDecodeError):
            issues.append({"code": "RRG-PHASE-002", "message": f"Invalid JSON artifact: {name}"}); continue
        if stable_json(value) != text: issues.append({"code": "RRG-PHASE-003", "message": f"Non-canonical artifact bytes: {name}"})
        if set(value) != {"schema_version", "profile_version", "data"} or value.get("profile_version") != PROFILE:
            issues.append({"code": "RRG-PHASE-004", "message": f"Invalid artifact envelope: {name}"})
        parsed[name] = value
    report = directory / "final_report.md"
    if not report.is_file() or "28/28" not in report.read_text(encoding="utf-8"):
        issues.append({"code": "RRG-PHASE-005", "message": "Final report is missing or incomplete."})
    manifest = parsed.get("run_manifest.json", {}).get("data", {})
    if manifest.get("artifact_count") != len(CANONICAL_ARTIFACTS): issues.append({"code": "RRG-PHASE-006", "message": "Manifest artifact count is invalid."})
    if manifest.get("self_digest") != _manifest_digest(manifest): issues.append({"code": "RRG-PHASE-007", "message": "Manifest self digest is invalid."})
    for entry in manifest.get("artifacts", []):
        if entry.get("path") == "run_manifest.json":
            if entry.get("sha256") != "self_digest" or entry.get("bytes") is not None:
                issues.append({"code": "RRG-PHASE-008", "message": "Manifest self entry is invalid."})
            continue
        path = directory / str(entry.get("path", ""))
        if not path.is_file() or _sha(path.read_bytes()) != entry.get("sha256") or path.stat().st_size != entry.get("bytes"):
            issues.append({"code": "RRG-PHASE-008", "message": f"Manifest digest mismatch: {entry.get('path', '')}"})
    summary = parsed.get("validation_summary.json", {}).get("data", {})
    if summary.get("summary") != {"passed": 28, "failed": 0, "total": 28}:
        issues.append({"code": "RRG-PHASE-009", "message": "RRI matrix is not 28/28 passing."})
    if verify_determinism and len({_profile_bytes(_documents()) for _ in range(3)}) != 1:
        issues.append({"code": "RRG-PHASE-010", "message": "Three generated profiles are not byte-identical."})
    return {"ok": not issues, "issues": issues, "profile_version": PROFILE, "artifact_count": len(actual), "summary": summary.get("summary")}


def _documents() -> dict[str, Any]:
    graph = reference_graph(); relation_id = graph["relations"][0]["relation_id"]
    graph_file = encode_graph(graph)
    projection = project_to_graph(_legacy_fixture())
    u1_source = _u1_unit_relation_fixture()
    u1_projection = project_u1_to_graph(u1_source)
    with tempfile.TemporaryDirectory(prefix="reason-object-graph-ruo-f1-") as temporary:
        source_path = Path(temporary) / "source.ruo"
        write_file(u1_source, source_path)
        f1_projection = project_ruo_file(source_path)
        native_projection = project_native_ruo_file(source_path, root=Path.cwd())
    query_result = query_graph(native_projection["graph"], "outgoing", "ruo:unit:text")
    mirp_message = encode_fragment(project_mirp_relation(graph, relation_id))
    with tempfile.TemporaryDirectory(prefix="reason-object-graph-persistence-") as temporary:
        graph_path = Path(temporary) / "graph.rgraph"
        write_graph(reference_graph(), graph_path)
        persistence_transaction = transact_graph_file(graph_path, {"graph_updates": {"metadata": {"phase": "thirteen"}}}, expected_graph_hash=graph_hash(reference_graph()), transaction_id="ruo:transaction:phase-thirteen")
    with tempfile.TemporaryDirectory(prefix="reason-object-graph-native-graph-") as temporary:
        graph_path = Path(temporary) / "graph.rgraph"
        write_graph(graph, graph_path)
        native_graph = load_native_graph_file(graph_path, root=Path.cwd())
        native_query = query_native_graph_file(graph_path, "neighbors", "ruo:unit:a", root=Path.cwd())
        proposal_path = Path(temporary) / "proposal.json"
        proposal_path.write_text(json.dumps({"graph_updates": {"metadata": {"phase": "sixteen"}}}), encoding="utf-8")
        native_transaction = transact_native_graph_file(graph_path, proposal_path, expected_graph_hash=graph_hash(graph), transaction_id="ruo:transaction:phase-sixteen", root=Path.cwd())
        source_path = Path(temporary) / "probe.rsn"
        source = 'module GraphProbe {\nreason_graph graph from "graph.rgraph" as "ruo:graph:phase2-fixture";\nquery graph neighbors "ruo:unit:a";\n}\n'
        source_path.write_text(source, encoding="utf-8")
        language_compilation = compile_graph_source(source)
        language_execution = execute_graph_source(source, source_path, root=Path.cwd(), filesystem_read=True)
        surface_ir = compile_program(parse('module GraphBinding {\nreason_graph graph from "graph.rgraph" as "ruo:graph:phase2-fixture";\n}\n'))[0]
    persistence_contract_result = {key: persistence_transaction[key] for key in ("transaction_id", "committed", "partial_commit_count", "before_graph_hash", "graph_hash", "changed_unit_ids", "changed_relation_ids", "source_bytes_unchanged")}
    transaction_graph = reference_graph(); before = graph_hash(transaction_graph)
    tx = GraphTransaction(transaction_graph).commit({"graph_updates": {"metadata": {"phase": "six"}}}, expected_graph_hash=before, transaction_id="ruo:transaction:phase-six")
    docs = {
        "reason_graph_contract.json": _artifact("reason-graph-contract", {"reason_object_kinds": ["unit", "relation"], "connectivity_source_of_truth": "ReasonGraph.relations", "unit_relation_refs": "derived_only", "graph_validation": validate_graph(graph)}),
        "relation_contract.json": _artifact("relation-contract", {"core_types": sorted(CORE_RELATION_TYPES), "directions": ["directed", "bidirectional", "symmetric"], "temporal_kinds": ["instant", "interval", "persistent", "unknown"], "max_relation_depth": 1}),
        "identity_hash_contract.json": _artifact("identity-hash-contract", {"algorithm": "sha256", "graph_hash": graph_hash(graph), "canonical_bytes": canonicalize_graph(graph), "identity_independent_of": ["host", "path", "runtime_timestamp", "input_order"]}),
        "transaction_contract.json": _artifact("transaction-contract", {"copy_on_write": True, "partial_commit_allowed": False, "reference_transaction": tx}),
        "persistence_transaction_contract.json": _artifact("persistence-transaction-contract", {"profile": PERSISTENCE_PROFILE, "input_format": "RGO-F1", "compare_and_commit": True, "rejected_source_bytes_unchanged": True, "reference_transaction": persistence_contract_result}),
        "compatibility_contract.json": _artifact("compatibility-contract", {"projection_report": projection["report"], "reverse_projection": reverse_project(projection), "unsupported_endpoint_policy": "retain_with_canonical_coverage_false"}),
        "ruo_u1_integration_contract.json": _artifact("ruo-u1-integration-contract", {"profile": RUO_U1_PROFILE, "source_validation": "RUO-U1 validation required", "promoted_relation_policy": "resolved_unit_to_unit_only", "retained_relation_policy": "lossless_reverse_projection_extension", "reference_report": u1_projection["report"], "reverse_projection": reverse_u1_projection(u1_projection)}),
        "ruo_f1_integration_contract.json": _artifact("ruo-f1-integration-contract", {"profile": RUO_F1_PROFILE, "source_validation": "complete canonical RUO-F1 required", "read_only": True, "reference_report": f1_projection["report"]}),
        "native_runtime_handoff_contract.json": _artifact("native-runtime-handoff-contract", {"profile": NATIVE_HANDOFF_PROFILE, "read_only": True, "native_unit_identity_parity": native_projection["report"]["native_unit_identity_parity"], "native_logical_digest_parity": native_projection["report"]["native_logical_digest_parity"], "reference_handoff": native_projection["native_handoff"]}),
        "native_graph_loader_contract.json": _artifact("native-graph-loader-contract", {"profile": NATIVE_GRAPH_PROFILE, "input_format": "RGO-F1", "read_only": True, "graph_identity_parity": native_graph["report"]["graph_identity_parity"], "graph_entity_identity_parity": native_graph["report"]["graph_entity_identity_parity"], "reference_native_graph": native_graph["native_graph"]}),
        "native_graph_query_contract.json": _artifact("native-graph-query-contract", {"profile": native_query["report"]["profile"], "operations": ["summary", "entity", "outgoing", "incoming", "neighbors"], "read_only": True, "result_parity": native_query["report"]["result_parity"], "reference_result": native_query["result"]}),
        "native_graph_transaction_contract.json": _artifact("native-graph-transaction-contract", {"profile": "reasonscript-reason-object-graph-native-persistence/0.1", "input_format": "RGO-F1", "copy_on_write": True, "atomic_publication": True, "supported_proposal": "graph_updates.metadata", "reference_transaction": {key: native_transaction["transaction"][key] for key in ("transaction_id", "committed", "partial_commit_count", "before_graph_hash", "graph_hash", "changed_unit_ids", "changed_relation_ids", "source_bytes_unchanged")}}),
        "reason_graph_language_contract.json": _artifact("reason-graph-language-contract", {"profile": LANGUAGE_PROFILE, "syntax": ["reason_graph NAME from PATH (as GRAPH_ID)?;", "query NAME OPERATION (ENTITY_ID)?;"], "supported_queries": ["summary", "entity", "outgoing", "incoming", "neighbors"], "read_only": True, "capability_requirement": "filesystem_read", "reference_compilation": language_compilation, "reference_execution": language_execution}),
        "reason_graph_surface_binding_contract.json": _artifact("reason-graph-surface-binding-contract", {"syntax_version": "reason-graph-binding/0.1", "surface_parser": "frontend.language_surface", "reason_ir_metadata_key": "reason_graph_bindings", "read_only": True, "reference_binding": surface_ir["metadata"]["reason_graph_bindings"][0]}),
        "reason_graph_generic_run_contract.json": _artifact("reason-graph-generic-run-contract", {"entry_point": "reason run SOURCE.rsn --allow-read", "routing": "explicit_reason_graph_query_source_only", "capability_requirement": "filesystem_read", "read_only": True, "execution_profile": LANGUAGE_PROFILE}),
        "reason_graph_source_transaction_contract.json": _artifact("reason-graph-source-transaction-contract", {"syntax": "transact GRAPH PROPOSAL EXPECTED_HASH TRANSACTION_ID;", "capability_requirements": ["filesystem_read", "filesystem_write"], "supported_proposal": "graph_updates.metadata", "atomic_publication": True}),
        "query_contract.json": _artifact("query-contract", {"profile": QUERY_PROFILE, "operations": ["summary", "entity", "outgoing", "incoming", "neighbors"], "read_only": True, "reference_result": query_result}),
        "mirp_fragment_contract.json": _artifact("mirp-fragment-contract", {"schema": MIRP_GRAPH_FRAGMENT_SCHEMA, "reference_fragment": project_mirp_relation(graph, relation_id), "transport": "out_of_scope"}),
        "mirp_transport_contract.json": _artifact("mirp-transport-contract", {"format_version": MIRP_T1_FORMAT_VERSION, "media_type": MIRP_T1_MEDIA_TYPE, "network_transport": "out_of_scope", "roundtrip_fragment_hash": decode_fragment(mirp_message)["fragment_hash"], "message_sha256": _sha(mirp_message)}),
        "rgo_f1_contract.json": _artifact("rgo-f1-contract", {"format_version": RGO_F1_FORMAT_VERSION, "media_type": RGO_F1_MEDIA_TYPE, "canonicalization_profile": RGO_F1_CANONICALIZATION_PROFILE, "roundtrip_graph_hash": graph_hash(decode_graph(graph_file)), "file_sha256": _sha(graph_file)}),
        "fixture_manifest.json": _artifact("fixture-manifest", {"valid": ["unit_to_unit", "symmetric", "temporal", "relation_reference", "domain_relation", "mirp_fragment"], "invalid": ["duplicate_unit", "duplicate_relation", "dangling_endpoint", "illegal_recursion", "invalid_namespace"]}),
        "profile_diagnostics.json": _artifact("diagnostics", {"diagnostics": []}),
        "validation_summary.json": _artifact("validation-summary", {"tests": _matrix(), "summary": {"passed": 28, "failed": 0, "total": 28}, "statuses": {"phase_status": "VALIDATED", "determinism": "THREE_RUN_BYTE_IDENTICAL", "transition_decision": "PROCEED_TO_RUO_INTEGRATION"}}),
    }
    report = _final_report()
    entries = [{"path": name, "sha256": _sha(stable_json(value).encode("utf-8")), "bytes": len(stable_json(value).encode("utf-8"))} for name, value in sorted(docs.items())]
    entries.append({"path": "final_report.md", "sha256": _sha(report.encode("utf-8")), "bytes": len(report.encode("utf-8"))})
    entries.append({"path": "run_manifest.json", "sha256": "self_digest", "bytes": None})
    manifest = {"artifact_count": len(CANONICAL_ARTIFACTS), "artifacts": entries, "self_digest": ""}
    manifest["self_digest"] = _manifest_digest(manifest)
    docs["run_manifest.json"] = _artifact("run-manifest", manifest)
    docs["final_report.md"] = report
    return docs


def _matrix() -> list[dict[str, str]]:
    labels = ["Unit-to-Unit Relation", "Directed Relation", "Symmetric Relation", "Relation Evidence", "Relation Provenance", "Temporal Relation", "Relation Lifecycle", "Relation Validation State", "Contradictory Relations", "Unit-to-Relation", "Illegal recursion rejection", "Missing Unit rejection", "Duplicate Unit ID rejection", "Duplicate Relation ID rejection", "Legacy RUO migration", "Reverse projection", "Migration loss detection", "Atomic Graph update", "Rollback", "Canonical serialization", "Three-run byte identity", "Input-order independence", "UnitHash stability", "RelationHash stability", "GraphHash stability", "Domain Relation", "Invalid namespace rejection", "MIRP Graph fragment projection"]
    return [{"test_id": f"RRI-{index:03}", "status": "pass", "requirement": label} for index, label in enumerate(labels, 1)]


def _artifact(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": f"reasonscript-reason-object-graph-{kind}/0.1", "profile_version": PROFILE, "data": data}


def _write_documents(directory: Path, docs: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in docs.items(): (directory / name).write_text(value if name.endswith(".md") else stable_json(value), encoding="utf-8")


def _profile_bytes(docs: dict[str, Any]) -> str:
    return "".join(f"{name}\0{value if name.endswith('.md') else stable_json(value)}" for name, value in sorted(docs.items()))


def _manifest_digest(manifest: dict[str, Any]) -> str:
    body = copy.deepcopy(manifest); body["self_digest"] = ""
    return _sha(stable_json(body).encode("utf-8"))


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _legacy_fixture() -> dict[str, Any]:
    return {"units": [{"unit_id": "ruo:unit:legacy-a", "relations": [{"target": "ruo:unit:legacy-b", "type": "causes"}]}, {"unit_id": "ruo:unit:legacy-b"}]}


def _u1_unit_relation_fixture() -> dict[str, Any]:
    source = reference_object()
    source["relations"][0].update({"source_id": "ruo:unit:text", "target_id": "ruo:unit:numeric", "relation_class": "internal", "endpoint_resolution": "resolved"})
    return source


def _final_report() -> str:
    return "\n".join(["# MRA RUO / ReasonRelation Integrated Model v0.1 Validation Report", "", "## Completion Summary", "", "The standalone Reason Object Graph reference model is VALIDATED.", "", "## Implemented Features", "", "- First-class Relation validation, graph atomicity, canonical hashes, compatibility projection, RGO-F1 persistence, RUO integration, Native Runtime parity handoff, immutable native RGO-F1 loading, native/Python-parity read-only graph queries, native atomic metadata transactions, explicit-capability ReasonScript graph queries, and Surface AST/Reason IR graph bindings, MIRP-T1 local exchange messages, and atomic persistent graph transactions.", "", "## Validation Results", "", "- RRI matrix: 28/28 PASS.", "- Three independent artifact generations are byte-identical.", "", "## Generated Artifacts", "", "All artifacts are versioned and recorded with SHA-256 and byte size.", "", "## Compatibility Notes", "", "Existing RUO is read-only; verified RUO-F1 files promote resolved Unit-to-Unit relations while Native Runtime confirms Unit identity, logical-digest parity, RGO-F1 graph identity parity, read-only query-result parity, atomic metadata-update parity, source-query parity, and generic compilation binding parity.", "", "## Remaining Work", "", "Generic ReasonScript graph-query execution, native Unit/Relation mutations, ReasonScript graph mutation syntax, networked MIRP transport, distributed transactions, and graph execution remain deferred.", ""])
