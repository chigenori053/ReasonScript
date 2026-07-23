from __future__ import annotations

import json
from pathlib import Path

import pytest

from frontend.language_surface import ReasonObjectBindingNode, SurfaceSyntaxError, compile_program, execution_plan_for, parse, to_json_value
from toolchain.object_cmd import run as cli_run
from toolchain.reasonunit_language import (
    CANONICAL_ARTIFACTS, PROFILE, RUO_FUNCTIONS, RUO_TYPES, bind_source_objects,
    compile_reason_object_source, format_reason_object_source,
    generate_language_profile, validate_language_profile, verify_ruo_n1,
)
from toolchain.reasonunit_language.phase import INVALID_CASES

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def generated(tmp_path: Path) -> Path:
    output = tmp_path / "ruo-n2"
    assert generate_language_profile(ROOT, output)["phase_status"] == "VALIDATED"
    return output


def test_n1_prerequisite_and_status_normalization(tmp_path: Path) -> None:
    verified = verify_ruo_n1(ROOT); assert verified["summary"] == {"passed": 74, "failed": 0, "total": 74}
    missing = tmp_path / "missing"; missing.mkdir()
    assert generate_language_profile(ROOT, tmp_path / "out", n1_directory=missing)["phase_status"] == "NOT_VALIDATED"


def test_parse_model_module_and_all_binding_clauses() -> None:
    source = 'model X {\n reason_object vehicle from "objects/v.ruo" resources "objects/r" mode preserve as "ruo:object:v";\n}\n'
    node = parse(source).modules[0].body[0]
    assert isinstance(node, ReasonObjectBindingNode) and node.load_mode == "preserve" and node.expected_object_id == "ruo:object:v"
    assert {span.clause for span in node.clause_spans} == {"name", "from", "resources", "mode", "as"}
    assert isinstance(parse(source.replace("model X", "module X")).modules[0].body[0], ReasonObjectBindingNode)


@pytest.mark.parametrize("source,code", [
    ('reason_object x from "x.ruo";\n', "RUO-N2-002"),
    ('model X {\n reason_object x from "../x.ruo";\n}\n', "RUO-N2-006"),
    ('model X {\n reason_object x from "https://x/x.ruo";\n}\n', "RUO-N2-006"),
    ('model X {\n reason_object x from "x.ruo" mode strange;\n}\n', "RUO-N2-003"),
    ('model X {\n reason_object x from "x.ruo" mode strict mode strict;\n}\n', "RUO-N2-003"),
])
def test_invalid_syntax_and_paths_are_rejected(source: str, code: str) -> None:
    with pytest.raises(SurfaceSyntaxError, match=code): parse(source)


def test_duplicate_binding_is_rejected() -> None:
    with pytest.raises(SurfaceSyntaxError, match="duplicate"):
        parse('model X {\n reason_object x from "a.ruo";\n reason_object x from "b.ruo";\n}\n')


def test_ast_ir_and_plan_are_typed_deterministic_and_identity_safe() -> None:
    source = 'model X {\n reason_object x from "objects/x.ruo" mode strict as "ruo:object:x";\n}\n'
    first = compile_reason_object_source(source); second = compile_reason_object_source(source)
    assert first == second and len(first["static_types"]) == len(RUO_TYPES) == 12 and len(first["standard_functions"]) == len(RUO_FUNCTIONS) == 16
    binding = first["bindings"][0]; assert binding["node_type"] == "ReasonObjectBindingIR" and binding["binding_id"] != binding["expected_object_id"]
    plan = first["execution_plans"][0]["reason_object_plan"]; assert [step["operation"] for step in plan["steps"]][:3] == ["binding_resolution", "capability_validation", "native_load"]


def test_ruo_standard_function_namespace_lowers_to_typed_operations() -> None:
    calls = {"object_id": "x", "snapshot": "x", "resolve": 'x, "ruo:unit:x"', "query": 'x, "{}"', "begin": "x", "apply": 'x, "{}"', "validate": "x", "commit": "x", "rollback": "x", "select": 'x, "{}"', "materialize": 'x, "{}"', "project": 'x, "{}"', "save": 'x, "out.ruo", "deny"', "tensor_view": 'x, "ruo:payload:tensor"', "status": "x", "diagnostics": "x"}
    for method, arguments in calls.items():
        source = f'model X {{\n reason_object x from "objects/x.ruo";\n calculation A {{\n  result = ruo.{method}({arguments})\n }}\n}}\n'
        ir = compile_program(parse(source))[0]; operation = ir["metadata"]["reason_object_operations"][0]
        assert operation["operation"] == method and operation["output_type"]
    with pytest.raises(SurfaceSyntaxError, match="RUO-N2-009"): parse('model X {\n reason_object x from "x.ruo";\n calculation A {\n result = ruo.unknown(x)\n }\n}\n')


def test_non_opt_in_ast_ir_and_plan_remain_unchanged() -> None:
    source = 'model X {\n calculation A {\n  result = 1\n }\n}\n'; program = parse(source); before = to_json_value(program); ir = compile_program(program)[0]
    assert format_reason_object_source(source) == source and to_json_value(parse(source)) == before
    assert "reason_object_bindings" not in ir["metadata"] and "reason_object_plan" not in execution_plan_for(ir)


def test_formatter_is_idempotent_and_orders_clauses() -> None:
    source = 'model X {\n reason_object x from "x.ruo" as "ruo:object:x" mode strict resources "resources";\n}\n'
    formatted = format_reason_object_source(source)
    assert formatted == format_reason_object_source(formatted)
    assert formatted.index("resources") < formatted.index("\n     mode") < formatted.index('as "ruo:object:x"')


def test_capability_denial_and_native_binding(generated: Path) -> None:
    source_path = generated / "fixtures/vehicle.rsn"; source = source_path.read_text()
    with pytest.raises(PermissionError, match="RUO-N2-007"): bind_source_objects(source, source_path, generated / "fixtures", filesystem_read=False)
    result = bind_source_objects(source, source_path, generated / "fixtures", filesystem_read=True, load_profile="eager_verified")
    assert result[0]["object_id"] == "ruo:object:universal-fixture" and result[0]["native_execution_provenance"].endswith("/1.0")


def test_consolidated_cli_check_run_query_select_and_save(generated: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = generated / "fixtures/vehicle.rsn"; obj = generated / "fixtures/objects/complete.ruo"
    assert cli_run(["check", str(source), "--json"], ROOT) == 0; assert json.loads(capsys.readouterr().out)["bindings"]
    assert cli_run(["run", str(source), "--json"], ROOT) != 0; assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "RUO-N2-007"
    assert cli_run(["run", str(source), "--allow-read", "--json"], ROOT) == 0; capsys.readouterr()
    query = tmp_path / "query.json"; query.write_text('{"profile":"all"}')
    assert cli_run(["query", str(obj), "--query", str(query), "--json"], ROOT) == 0; assert json.loads(capsys.readouterr().out)["entity_ids"]
    selector = tmp_path / "selector.json"; selector.write_text('{"entity_ids":["ruo:unit:root"]}')
    assert cli_run(["select", str(obj), "--selector", str(selector), "--output", str(tmp_path / "partial.ruo"), "--json"], ROOT) == 0; capsys.readouterr()
    assert cli_run(["save", str(source), "--binding", "vehicle", "--output", str(tmp_path / "saved.ruo"), "--allow-read", "--allow-write", "--json"], ROOT) == 0
    assert json.loads(capsys.readouterr().out)["canonical_byte_identical"]


def test_object_cli_native_resolution_is_independent_of_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    native = tmp_path / "distribution/bin/reasonunit-runtime-native"
    native.parent.mkdir(parents=True)
    native.write_text(
        "#!/bin/sh\n"
        "printf '%s' '{\"ok\":true,\"object_id\":\"ruo:object:test\","
        "\"revision_id\":\"ruo:revision:0\",\"snapshot_generation\":1,"
        "\"logical_object_digest\":\"sha256:test\"}'\n",
        encoding="utf-8",
    )
    native.chmod(0o755)
    calls: list[tuple[object, ...]] = []

    def resolve(*args: object) -> Path:
        calls.append(args)
        return native

    monkeypatch.setattr("toolchain.object_cmd.resolve_native_reasonunit_runtime", resolve)
    project = tmp_path / "unrelated-project"
    project.mkdir()
    object_path = project / "object.ruo"
    object_path.write_text("native fixture", encoding="utf-8")

    assert cli_run(["inspect", str(object_path), "--json"], project) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] and result["object_id"] == "ruo:object:test"
    assert calls == [()]


def test_phase_generates_56_artifacts_and_67_tests(generated: Path) -> None:
    assert len(CANONICAL_ARTIFACTS) == 56 and all((generated / name).is_file() for name in CANONICAL_ARTIFACTS)
    summary = json.loads((generated / "validation_summary.json").read_text())["data"]
    assert summary["summary"] == {"passed": 67, "failed": 0, "total": 67}
    assert summary["statuses"]["implementation_status"] == "IMPLEMENTED" and summary["statuses"]["transition_decision"] == "PROCEED_TO_RUO-M1"


def test_n1_history_is_not_rewritten_and_invalid_cases_are_complete(generated: Path) -> None:
    normalization = json.loads((generated / "ruo_n1_status_normalization.json").read_text())["data"]
    invalid = json.loads((generated / "invalid_fixture_manifest.json").read_text())["data"]
    assert normalization["historical_artifacts_rewritten"] is False and normalization["normalized_value"] == "IMPLEMENTED"
    assert invalid["case_count"] == len(INVALID_CASES) == 28


def test_artifact_envelopes_manifest_and_three_run_determinism(generated: Path) -> None:
    for path in generated.glob("*.json"):
        value = json.loads(path.read_text()); assert value["profile_version"] == PROFILE and set(value) == {"schema_version", "profile_version", "data"}
    manifest = json.loads((generated / "run_manifest.json").read_text())["data"]
    assert manifest["artifact_count"] == 56 and manifest["file_count"] == len(manifest["files"])
    assert validate_language_profile(ROOT, generated, verify_determinism=True)["ok"]
