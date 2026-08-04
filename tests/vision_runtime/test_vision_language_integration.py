from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from frontend.language_surface import (
    SurfaceSyntaxError,
    compile_program,
    execution_plan_for,
    parse,
)
from frontend.lsp.core import ReasonScriptLanguageServer
from frontend.vision.contracts import PROFILE, VISION_TYPES, public_registry
from toolchain.reasonunit_file import read_file, validate_file
from toolchain.reasonunit_tensor import validate_tensor

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/vision_language"


def _run_reason(*arguments: str) -> tuple[int, dict]:
    completed = subprocess.run(
        [str(ROOT / "reason"), *arguments, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_registry_types_reason_ir_and_execution_plan() -> None:
    assert VISION_TYPES == ("VisionModel", "VisionObservation", "VisionBuildResult")
    assert [entry["qualified_name"] for entry in public_registry()] == ["vision.infer", "vision.build_ruo"]
    source = (FIXTURE / "vision_pipeline.rsn").read_text(encoding="utf-8")
    ir = compile_program(parse(source))[0]
    operations = ir["metadata"]["vision_operations"]
    assert [operation["node_type"] for operation in operations] == ["VisionCallIR", "VisionCallIR"]
    assert [operation["native_operation"] for operation in operations] == ["vision_infer", "vision_build_ruo"]
    plan = execution_plan_for(ir)["vision_plan"]
    assert plan["profile"] == PROFILE
    assert plan["publication_policy"] == "atomic_ruo_f1"
    assert plan["operations"][1]["transaction_boundary"] is True


@pytest.mark.parametrize(("expression", "code"), [
    ('vision.unknown("a", "b")', "VIS-LANG-001"),
    ('vision.infer("model.json")', "VIS-LANG-002"),
    ('vision.infer("../model.json", "image.bin")', "VIS-LANG-003"),
    ('vision.build_ruo(observation, "output.json")', "VIS-LANG-004"),
])
def test_invalid_vision_calls_have_stable_diagnostics(expression: str, code: str) -> None:
    source = f"model X {{\n calculation C {{\n  result = {expression}\n }}\n}}\n"
    with pytest.raises(SurfaceSyntaxError, match=code):
        parse(source)


def test_language_runtime_requires_explicit_capabilities(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    status, result = _run_reason("run", str(project / "vision_pipeline.rsn"))
    assert status == 1
    assert result["diagnostics"][-1]["code"] == "VIS-CAP-001"


def test_conformance_backend_rejects_provenance_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    (project / "image.bin").write_bytes(b"different-image")
    completed = subprocess.run(
        [str(ROOT / "reason"), "vision", "infer", str(project / "model.json"), str(project / "image.bin"), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert json.loads(completed.stdout)["diagnostics"][0]["code"] == "VIS-RUN-002"


def test_rust_dispatch_and_atomic_ruo_tensor_publication(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(FIXTURE, project)
    source = project / "vision_pipeline.rsn"
    status, result = _run_reason("run", str(source), "--allow-read", "--allow-write")
    assert status == 0 and result["runtime_result"]["result"]["status"] == "committed"
    assert [item["operation"] for item in result["runtime_result"]["vision_trace"]] == ["vision_infer", "vision_build_ruo"]

    output = project / "output/solar-observation.ruo"
    assert validate_file(output)["ok"] is True
    logical = read_file(output)
    tensors = [payload for payload in logical["payloads"] if payload["profile_id"] == "ruo.payload.tensor/1"]
    assert {payload["value"]["extensions"]["reasonscript.vision"]["role"] for payload in tensors} == {"detections", "embeddings"}
    for payload in tensors:
        resource = output.parent / payload["value"]["storage"]["locator"]
        assert validate_tensor(payload, resource_bytes=resource.read_bytes())["ok"] is True


def test_lsp_exposes_vision_functions_and_types() -> None:
    server = ReasonScriptLanguageServer()
    labels = {item.label for item in server.completion("file:///vision.rsn", 0, 0)}
    assert {"vision.infer", "vision.build_ruo", *VISION_TYPES} <= labels
