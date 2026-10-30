"""Native host setup shared by CLI and handwritten acceptance tests."""
from pathlib import Path
import subprocess
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def native_runtime_host() -> Path:
    from frontend.computation_ir.rust_bridge import find_binary

    binary = find_binary()
    if binary is not None:
        return binary

    runtime_root = REPO_ROOT / "ReasonRuntime"
    completed = subprocess.run(
        ["cargo", "build", "-p", "reasonscript-computation-runtime-cli"],
        cwd=runtime_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    binary = find_binary()
    assert binary is not None
    return binary
