"""CLI for MRA Reason Object Graph profile generation and validation."""

from __future__ import annotations

import json
from pathlib import Path

from toolchain.reason_object_graph.phase import generate_profile, validate_profile
from toolchain.reason_object_graph.ruo_f1 import project_ruo_file, project_ruo_file_to_rgraph
from toolchain.reason_object_graph.format import read_graph
from toolchain.reason_object_graph.query import query_graph
from toolchain.reason_object_graph.mirp_transport import export_graph, read_message
from toolchain.reason_object_graph.format import write_graph
from toolchain.reason_object_graph.persistence import transact_graph_file
from toolchain.reason_object_graph.native_graph import load_native_graph_file, query_native_graph_file, transact_native_graph_file
from toolchain.reason_object_graph.language import compile_graph_source, execute_graph_source


DEFAULT_OUTPUT = Path("artifacts/reason_object_graph/mra_ruo_rr_im_0_1")


def run(args: list[str], root: Path) -> int:
    if not args or args[0] not in {"generate", "validate", "project-ruo", "source-check", "source-run", "native-load", "native-query", "native-transact", "query", "export-mirp", "import-mirp", "transact"}:
        print("Usage: reason reason-object-graph <generate|validate> [--output <dir>] [--json]")
        print("       reason reason-object-graph project-ruo INPUT.ruo [--output OUTPUT.rgraph] [--overwrite] [--json]")
        print("       reason reason-object-graph source-check SOURCE.rsn [--json]")
        print("       reason reason-object-graph source-run SOURCE.rsn --allow-read [--json]")
        print("       reason reason-object-graph native-load INPUT.rgraph [--json]")
        print("       reason reason-object-graph native-query INPUT.rgraph <summary|entity|outgoing|incoming|neighbors> [ENTITY_ID] [--json]")
        print("       reason reason-object-graph native-transact GRAPH.rgraph --proposal PROPOSAL.json --expected-hash SHA256 --transaction-id ruo:transaction:ID [--json]")
        print("       reason reason-object-graph query INPUT.(ruo|rgraph) <summary|entity|outgoing|incoming|neighbors> [ENTITY_ID] [--json]")
        print("       reason reason-object-graph export-mirp INPUT.(ruo|rgraph) --output MESSAGE.mirp [--overwrite] [--json]")
        print("       reason reason-object-graph import-mirp MESSAGE.mirp --output GRAPH.rgraph [--overwrite] [--json]")
        print("       reason reason-object-graph transact GRAPH.rgraph --proposal PROPOSAL.json --expected-hash SHA256 --transaction-id ruo:transaction:ID [--json]")
        return 1
    if args[0] == "project-ruo":
        if len(args) < 2 or args[1].startswith("-"):
            print("project-ruo requires INPUT.ruo")
            return 1
        source = _resolve_path(args[1])
        try:
            result = project_ruo_file_to_rgraph(source, _path_option(args, "--output", source.with_suffix(".rgraph")), overwrite="--overwrite" in args) if "--output" in args else project_ruo_file(source)
        except (OSError, ValueError) as error:
            result = {"ok": False, "error": str(error)}
        ok = "error" not in result
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else ("RUO projected to ReasonGraph" if ok else "RUO projection failed"))
        return 0 if ok else 1
    if args[0] in {"source-check", "source-run"}:
        if len(args) < 2 or args[1].startswith("-"):
            print(f"{args[0]} requires SOURCE.rsn")
            return 1
        try:
            source_path = _resolve_path(args[1])
            source = source_path.read_text(encoding="utf-8")
            result = compile_graph_source(source) if args[0] == "source-check" else execute_graph_source(source, source_path, root=root, filesystem_read="--allow-read" in args, filesystem_write="--allow-write" in args)
            result["ok"] = True
        except (OSError, ValueError, PermissionError) as error:
            result = {"ok": False, "error": str(error)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else ("ReasonGraph source complete" if result["ok"] else "ReasonGraph source failed"))
        return 0 if result["ok"] else 1
    if args[0] == "native-load":
        if len(args) < 2 or args[1].startswith("-"):
            print("native-load requires INPUT.rgraph")
            return 1
        try:
            result = load_native_graph_file(_resolve_path(args[1]), root=root)
            result["ok"] = True
        except (OSError, ValueError) as error:
            result = {"ok": False, "error": str(error)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else ("Native ReasonGraph load complete" if result["ok"] else "Native ReasonGraph load failed"))
        return 0 if result["ok"] else 1
    if args[0] == "native-query":
        if len(args) < 3:
            print("native-query requires INPUT.rgraph and query name")
            return 1
        entity_id = args[3] if len(args) > 3 and not args[3].startswith("-") else None
        try:
            result = query_native_graph_file(_resolve_path(args[1]), args[2], entity_id, root=root)
            result["ok"] = True
        except (OSError, ValueError) as error:
            result = {"ok": False, "error": str(error)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else ("Native ReasonGraph query complete" if result["ok"] else "Native ReasonGraph query failed"))
        return 0 if result["ok"] else 1
    if args[0] == "native-transact":
        required = {"--proposal", "--expected-hash", "--transaction-id"}
        if len(args) < 2 or not required.issubset(args):
            print("native-transact requires GRAPH.rgraph --proposal PROPOSAL.json --expected-hash SHA256 --transaction-id ID")
            return 1
        try:
            result = transact_native_graph_file(_resolve_path(args[1]), _path_option(args, "--proposal", Path("missing")), expected_graph_hash=_option(args, "--expected-hash"), transaction_id=_option(args, "--transaction-id"), root=root)
            result["ok"] = bool(result["transaction"]["committed"])
        except (OSError, ValueError, json.JSONDecodeError) as error:
            result = {"ok": False, "error": str(error)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else ("Native ReasonGraph transaction committed" if result["ok"] else "Native ReasonGraph transaction rejected"))
        return 0 if result["ok"] else 1
    if args[0] == "query":
        if len(args) < 3:
            print("query requires INPUT and query name")
            return 1
        source, query = _resolve_path(args[1]), args[2]
        entity_id = args[3] if len(args) > 3 and not args[3].startswith("-") else None
        try:
            graph = project_ruo_file(source)["graph"] if source.suffix == ".ruo" else read_graph(source)
            result = query_graph(graph, query, entity_id)
        except (OSError, ValueError) as error:
            result = {"ok": False, "error": str(error)}
        ok = "error" not in result
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else ("ReasonGraph query complete" if ok else "ReasonGraph query failed"))
        return 0 if ok else 1
    if args[0] in {"export-mirp", "import-mirp"}:
        if len(args) < 2 or "--output" not in args:
            print(f"{args[0]} requires INPUT and --output")
            return 1
        source, target = _resolve_path(args[1]), _path_option(args, "--output", Path("missing"))
        try:
            if args[0] == "export-mirp":
                graph = project_ruo_file(source)["graph"] if source.suffix == ".ruo" else read_graph(source)
                result = export_graph(graph, target, overwrite="--overwrite" in args)
            else:
                result = write_graph(read_message(source)["graph"], target, overwrite="--overwrite" in args)
            result["ok"] = True
        except (OSError, ValueError) as error:
            result = {"ok": False, "error": str(error)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else ("MIRP operation complete" if result["ok"] else "MIRP operation failed"))
        return 0 if result["ok"] else 1
    if args[0] == "transact":
        required = {"--proposal", "--expected-hash", "--transaction-id"}
        if len(args) < 2 or not required.issubset(args):
            print("transact requires GRAPH.rgraph --proposal PROPOSAL.json --expected-hash SHA256 --transaction-id ID")
            return 1
        try:
            source = _resolve_path(args[1])
            proposal = json.loads(_path_option(args, "--proposal", Path("missing")).read_text(encoding="utf-8"))
            result = transact_graph_file(source, proposal, expected_graph_hash=_option(args, "--expected-hash"), transaction_id=_option(args, "--transaction-id"))
            result["ok"] = bool(result["committed"])
        except (OSError, ValueError, json.JSONDecodeError) as error:
            result = {"ok": False, "error": str(error)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else ("ReasonGraph transaction committed" if result["ok"] else "ReasonGraph transaction rejected"))
        return 0 if result["ok"] else 1
    output = _path_option(args, "--output", root / DEFAULT_OUTPUT)
    result = generate_profile(root, output) if args[0] == "generate" else validate_profile(root, output)
    ok = result.get("phase_status") == "VALIDATED" if args[0] == "generate" else result.get("ok", False)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if "--json" in args else (f"Reason Object Graph {'generated' if args[0] == 'generate' else 'valid'}" if ok else "Reason Object Graph NOT_VALIDATED"))
    return 0 if ok else 1


def _path_option(args: list[str], name: str, default: Path) -> Path:
    if name not in args or args.index(name) + 1 >= len(args): return default
    path = Path(args[args.index(name) + 1])
    return path if path.is_absolute() else Path.cwd() / path


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path.cwd() / path


def _option(args: list[str], name: str) -> str:
    return args[args.index(name) + 1]
