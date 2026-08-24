from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary
from frontend.language_surface import parse


HOST = find_binary()


def _program(expression: str) -> dict:
    return lower_program(
        parse(
            f"""
            module M {{
              calculation Answer {{
                result = {expression}
              }}
            }}
            """
        )
    )


def _request(program: dict, *, request_id: str = "protocol-test", trace: bool = False) -> dict:
    return {
        "schema": "reasonscript-runtime-request/1.0",
        "request_id": request_id,
        "operation": "execute",
        "program": program,
        "context": {
            "resource_root": ".",
            "capabilities": {
                "filesystem_read": False,
                "filesystem_write": False,
                "network": False,
            },
            "limits": {},
            "trace": {"enabled": trace},
            "numeric_mode": "compat-reference",
        },
    }


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_runtime_host_executes_versioned_request():
    program = _program("6 * 7")
    completed = subprocess.run(
        [str(HOST)], input=json.dumps(_request(program)), text=True, capture_output=True
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert payload["schema"] == "reasonscript-runtime-result/1.0"
    assert payload["request_id"] == "protocol-test"
    assert payload["calculation_results"] == {"Answer": 42}
    assert payload["diagnostics"] == []
    assert payload["metadata"]["host_profile"] == "reasonscript-runtime-host/1.0"


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_runtime_host_returns_structured_diagnostic_for_unsupported_trace():
    program = _program("1")
    completed = subprocess.run(
        [str(HOST)], input=json.dumps(_request(program, trace=True)), text=True, capture_output=True
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["schema"] == "reasonscript-runtime-result/1.0"
    assert payload["diagnostics"][0]["code"] == "RTH-CAP-001"


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_runtime_host_rejects_malformed_versioned_request():
    request = _request(_program("1"), request_id="")
    completed = subprocess.run(
        [str(HOST)], input=json.dumps(request), text=True, capture_output=True
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 1
    assert payload["diagnostics"][0]["code"] == "RTH-PROTO-001"


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
def test_runtime_host_retains_raw_computation_ir_compatibility():
    program = _program("3")
    completed = subprocess.run(
        [str(HOST)], input=json.dumps(program), text=True, capture_output=True
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert "schema" not in payload
    assert payload["calculation_results"] == {"Answer": 3}
