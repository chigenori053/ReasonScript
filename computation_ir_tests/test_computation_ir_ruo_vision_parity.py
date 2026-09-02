"""Phase 5 gate: complete in-process Rust RUO and Vision parity."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from frontend.computation_ir import interpret_program, lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.language_surface import parse
from toolchain.reasonunit_file import read_file
from toolchain.runtime_dispatch import (
    rust_trace_unsupported_operations,
    unsupported_rust_operations,
)


ROOT = Path(__file__).resolve().parents[1]
BINARY = find_binary()
OBJECT = ROOT / "artifacts/reasonunit_language/ruo_n2/fixtures/objects/complete.ruo"
VISION = ROOT / "tests/fixtures/vision_language"


pytestmark = pytest.mark.skipif(BINARY is None, reason="Rust runtime host is not built")


RUO_SOURCE = r'''model RuoParity {
  reason_object object from "objects/complete.ruo" mode strict;
  calculation ObjectId {
    result = ruo.object_id(object)
  }
  calculation SnapshotStatus {
    result = ruo.status(ruo.snapshot(object))
  }
  calculation Resolve {
    result = ruo.resolve(object, "ruo:unit:root")
  }
  calculation Query {
    result = ruo.query(object, "{\"query\":\"all\"}")
  }
  calculation Select {
    result = ruo.select(object, "{\"entity_ids\":[\"ruo:unit:root\",\"ruo:unit:missing\"]}")
  }
  calculation Materialize {
    result = ruo.materialize(object, "{\"entity_ids\":[\"ruo:unit:root\"]}")
  }
  calculation Project {
    result = ruo.project(object, "{}")
  }
  calculation TensorView {
    result = ruo.tensor_view(object, "ruo:payload:tensor")
  }
  calculation Validate {
    let transaction = ruo.begin(object)
    let applied = ruo.apply(transaction, "{\"state_updates\":{\"ruo:state:committed\":{\"temperature\":321}}}")
    result = ruo.validate(applied)
  }
  calculation Rollback {
    let transaction = ruo.begin(object)
    result = ruo.rollback(transaction)
  }
  calculation Commit {
    let transaction = ruo.begin(object)
    let applied = ruo.apply(transaction, "{\"transaction_id\":\"ruo:transaction:phase5\",\"state_updates\":{\"ruo:state:committed\":{\"temperature\":321}}}")
    result = ruo.commit(applied)
  }
  calculation CommittedValue {
    result = ruo.resolve(object, "ruo:state:committed")
  }
  calculation Save {
    result = ruo.save(object, "objects/saved.ruo", "overwrite")
  }
  calculation Diagnostics {
    result = ruo.diagnostics(object)
  }
}'''


def _ruo_root(path: Path) -> None:
    (path / "objects").mkdir()
    shutil.copyfile(OBJECT, path / "objects/complete.ruo")


def test_all_sixteen_ruo_functions_match_python_and_saved_file_reopens(tmp_path: Path) -> None:
    python_root = tmp_path / "python"
    rust_root = tmp_path / "rust"
    python_root.mkdir()
    rust_root.mkdir()
    _ruo_root(python_root)
    _ruo_root(rust_root)
    ir = lower_program(parse(RUO_SOURCE))

    python = interpret_program(
        ir,
        resource_root=python_root,
        filesystem_read=True,
        filesystem_write=True,
    ).to_dict()["calculations"]
    rust = run_ir(
        ir,
        binary=BINARY,
        cwd=rust_root,
        filesystem_read=True,
        filesystem_write=True,
    )

    assert rust.ok, (rust.error_code, rust.error_message)
    assert Path(python["Save"]["path"]) == python_root / "objects/saved.ruo"
    assert Path(rust.calculation_results["Save"]["path"]) == rust_root / "objects/saved.ruo"
    python["Save"].pop("path")
    rust.calculation_results["Save"].pop("path")
    assert rust.calculation_results == python
    assert read_file(rust_root / "objects/saved.ruo") == read_file(
        python_root / "objects/saved.ruo"
    )
    assert unsupported_rust_operations(ir) == ()


def _copy_vision_fixture(path: Path) -> None:
    for name in ("model.json", "observation.json", "image.bin"):
        shutil.copyfile(VISION / name, path / name)


def test_vision_infer_build_publication_and_trace_match_python(tmp_path: Path) -> None:
    source = (VISION / "vision_pipeline.rsn").read_text(encoding="utf-8")
    ir = lower_program(parse(source))
    python_root = tmp_path / "python"
    rust_root = tmp_path / "rust"
    python_root.mkdir()
    rust_root.mkdir()
    _copy_vision_fixture(python_root)
    _copy_vision_fixture(rust_root)

    python_result = interpret_program(
        ir,
        resource_root=python_root,
        filesystem_read=True,
        filesystem_write=True,
    )
    rust_result = run_ir(
        ir,
        binary=BINARY,
        cwd=rust_root,
        filesystem_read=True,
        filesystem_write=True,
        trace_enabled=True,
    )

    assert rust_result.ok, (rust_result.error_code, rust_result.error_message)
    assert rust_result.calculation_results == python_result.to_dict()["calculations"]
    assert rust_result.metadata["vision_trace"] == python_result.vision_runtime.trace
    assert read_file(rust_root / "output/solar-observation.ruo") == read_file(
        python_root / "output/solar-observation.ruo"
    )
    rust_resources = {
        path.relative_to(rust_root): path.read_bytes() for path in rust_root.rglob("*.ruot")
    }
    python_resources = {
        path.relative_to(python_root): path.read_bytes()
        for path in python_root.rglob("*.ruot")
    }
    assert rust_resources == python_resources
    assert unsupported_rust_operations(ir) == ()
    assert rust_trace_unsupported_operations(ir) == ()


@pytest.mark.parametrize(
    ("filesystem_read", "filesystem_write", "expected"),
    [(False, True, "VIS-CAP-001"), (True, False, "VIS-CAP-002")],
)
def test_vision_capability_diagnostics_are_native(
    tmp_path: Path,
    filesystem_read: bool,
    filesystem_write: bool,
    expected: str,
) -> None:
    _copy_vision_fixture(tmp_path)
    ir = lower_program(parse((VISION / "vision_pipeline.rsn").read_text(encoding="utf-8")))
    result = run_ir(
        ir,
        binary=BINARY,
        cwd=tmp_path,
        filesystem_read=filesystem_read,
        filesystem_write=filesystem_write,
    )
    assert not result.ok and result.error_code == expected


def test_native_ruo_and_vision_paths_reject_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    try:
        (root / "escape").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are not available")

    _ruo_root(root)
    ruo = lower_program(
        parse(
            '''model X {
  reason_object object from "objects/complete.ruo" mode strict;
  calculation Save {
    result = ruo.save(object, "escape/out.ruo", "overwrite")
  }
}'''
        )
    )
    ruo_result = run_ir(
        ruo,
        binary=BINARY,
        cwd=root,
        filesystem_read=True,
        filesystem_write=True,
    )
    assert not ruo_result.ok and ruo_result.error_code == "RUO-N2-006"

    shutil.copyfile(VISION / "model.json", outside / "model.json")
    shutil.copyfile(VISION / "observation.json", outside / "observation.json")
    shutil.copyfile(VISION / "image.bin", outside / "image.bin")
    vision = lower_program(
        parse(
            '''model X {
  calculation Infer {
    result = vision.infer("escape/model.json", "escape/image.bin")
  }
}'''
        )
    )
    vision_result = run_ir(
        vision,
        binary=BINARY,
        cwd=root,
        filesystem_read=True,
        filesystem_write=True,
    )
    assert not vision_result.ok and vision_result.error_code == "VIS-SEC-001"
