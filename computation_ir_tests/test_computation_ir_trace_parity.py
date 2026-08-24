from __future__ import annotations

from pathlib import Path

import pytest

from frontend.computation_ir import interpret_program, lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir
from frontend.integrated_computation_runtime import execute_program
from frontend.language_surface import parse


HOST = find_binary()


@pytest.mark.skipif(HOST is None, reason="reason-runtime-host binary not built")
@pytest.mark.parametrize(
    "source",
    [
        """module M {
  calculation C {
    let i = 0
    let total = 0
    while i < 3 {
      i = i + 1
      if i == 2 {
        continue
      }
      total = total + i
    }
    result = total
  }
}
""",
        """module M {
  calculation C {
    let total = 0
    for value in [2, 3, 4] {
      total = total + value
      if total > 4 {
        break
      }
    }
    result = total
  }
}
""",
        """module M {
  calculation C {
    let i = 0
    loop {
      i = i + 1
      if i == 2 {
        break
      }
    }
    result = i
  }
}
""",
    ],
)
def test_loop_trace_matches_ast_python_ir_and_rust(source: str):
    program = parse(source)
    ir = lower_program(program)
    ast_trace = execute_program(program, resource_root=Path.cwd()).to_dict()["loop_trace"]
    python_ir_trace = interpret_program(ir, resource_root=Path.cwd()).to_dict()["loop_trace"]
    rust = run_ir(ir, binary=HOST, trace_enabled=True)
    assert rust.ok
    assert python_ir_trace == ast_trace
    assert rust.metadata["loop_trace"] == ast_trace
