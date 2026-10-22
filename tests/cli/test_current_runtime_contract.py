"""Current CLI/runtime contracts; replaces assumptions from pre-0.5.5.3 behavior."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from frontend.language_surface.parser import SurfaceSyntaxError, _logical_lines

pytest.importorskip("pydantic", reason="reason CLI integration requires development dependencies")

from scripts import reason_cli
from toolchain.__main__ import main
from toolchain.runtime_dispatch import execute_rust_ir


@pytest.mark.parametrize(
    ("trace", "include_trace", "mode"),
    [(None, False, "off"), ("delta", True, "delta"), ("sampled", True, "sampled"), ("off", False, "off")],
)
def test_trace_is_opt_in_and_result_output_is_runtime_value(
    tmp_path: Path, monkeypatch, trace: str | None, include_trace: bool, mode: str
) -> None:
    observed: dict[str, object] = {}

    def fake_run_result(*_args: object, **kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        return {"ok": True, "runtime_result": {"result": 3, "calculations": {"Main": 3}}}

    monkeypatch.setattr(reason_cli, "_run_result", fake_run_result)
    output = tmp_path / "result.json"
    args = Namespace(file="fixture.rsn", compiler_mode="normal", trace=trace, json=True,
                     allow_read=False, allow_write=False, result_output=str(output), out=None)

    assert reason_cli.cmd_run(args) == 0
    assert observed["include_trace"] is include_trace
    assert observed["trace_config"] == {"mode": mode}
    assert json.loads(output.read_text(encoding="utf-8")) == 3


@pytest.mark.parametrize(
    ("args", "mode"),
    [([], "off"), (["--trace"], "delta"), (["--trace=full"], "full"), (["--trace=off"], "off")],
)
def test_package_run_trace_is_opt_in(args: list[str], mode: str) -> None:
    from toolchain.__main__ import _trace_config

    assert _trace_config(["program.rsn", *args]) == {"mode": mode}


def test_trace_unsupported_operations_are_reported_without_blocking_execution(
    tmp_path: Path, monkeypatch
) -> None:
    class Outcome:
        ok = True
        calculation_results = {"Main": 1}
        metadata: dict[str, object] = {}

    observed: dict[str, object] = {}
    monkeypatch.setattr("frontend.computation_ir.rust_bridge.find_binary", lambda: Path("runtime"))
    monkeypatch.setattr("frontend.computation_ir.rust_bridge.run_ir",
                        lambda *_args, **kwargs: observed.update(kwargs) or Outcome())
    document = {"functions": [{"blocks": [{"instructions": [{"op": "call_optimizer", "function_id": "optimizer.adam"}]}]}]}

    result = execute_rust_ir(document, tmp_path, False, False, include_trace=True)
    assert observed["trace_enabled"] is False
    assert result["trace_diagnostics"][0]["code"] == "RTH-TRACE-001"


def test_subcommand_help_does_not_discover_or_write_a_project(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["reason", "build", "--help"])
    assert main() == 0
    assert capsys.readouterr().out.startswith("Usage: reason build")


def test_backslash_continues_one_code_statement() -> None:
    source = "let total = 1 + " + "\\" + "\n  2\n"
    assert _logical_lines(source)[0] == ["let total = 1 + 2"]
    with pytest.raises(SurfaceSyntaxError):
        _logical_lines("let total = 1 + " + "\\")
