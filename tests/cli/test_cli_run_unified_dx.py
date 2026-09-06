"""Tests for unified reason run and CLI operations (Issue #49, RS-DXLI-08).

Verifies that:
1. `reason init <name>` creates a project that directly succeeds with `reason run`.
2. Missing build artifacts trigger automatic on-demand build during `reason run`.
3. Single calculation is resolved deterministically without arguments.
4. Multiple calculations prioritize `Main`/`main` deterministically.
5. Ambiguous calculations without `Main` fail with candidate suggestions without implicit guesswork.
6. Explicit positional entry selection (`reason run <entry>`) works as expected.
7. Unknown entry specification reports available candidate calculations.
8. Exit codes remain consistent (0: success, 1: user error/ambiguity, 2: build/runtime failure).
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def test_init_then_run_out_of_the_box(tmp_path: Path, monkeypatch, native_runtime_host: Path) -> None:
    from toolchain.__main__ import main as toolchain_main

    project_dir = tmp_path / "hello"
    monkeypatch.setattr(sys, "argv", ["reason", "init", str(project_dir)])
    assert toolchain_main() == 0

    assert (project_dir / "reason.toml").is_file()
    assert (project_dir / "src" / "main.rsn").is_file()

    # Direct run without manual build
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(sys, "argv", ["reason", "run"])
    assert toolchain_main() == 0

    # Verify computation artifacts were created on-demand
    assert (project_dir / "target" / "computation_ir" / "package.json").is_file()


def test_deterministic_entry_resolution_single_and_preferred(tmp_path: Path, monkeypatch, capsys, native_runtime_host: Path) -> None:
    from toolchain.__main__ import main as toolchain_main

    project_dir = tmp_path / "calc_proj"
    project_dir.mkdir(parents=True)
    (project_dir / "src").mkdir()
    (project_dir / "reason.toml").write_text(
        """[package]
name = "calc_proj"
version = "0.1.0"
[runtime]
backend = "RuntimeReal"
""",
        encoding="utf-8",
    )
    (project_dir / "src" / "main.rsn").write_text(
        """model Main {
    fn Value() -> int {
        return 100
    }
    calculation SingleEntry {
        result = Value()
    }
}
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(sys, "argv", ["reason", "run"])
    capsys.readouterr()
    assert toolchain_main() == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["status"] == "success"
    assert data["entry"] == "SingleEntry"
    assert data["runtime_result"]["result"] == 100


def test_multiple_calculations_with_main_prefers_main(tmp_path: Path, monkeypatch, capsys, native_runtime_host: Path) -> None:
    from toolchain.__main__ import main as toolchain_main

    project_dir = tmp_path / "multi_main"
    project_dir.mkdir(parents=True)
    (project_dir / "src").mkdir()
    (project_dir / "reason.toml").write_text(
        """[package]
name = "multi_main"
version = "0.1.0"
[runtime]
backend = "RuntimeReal"
""",
        encoding="utf-8",
    )
    (project_dir / "src" / "main.rsn").write_text(
        """model Main {
    calculation Aux {
        result = 10
    }
    calculation Main {
        result = 20
    }
}
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(sys, "argv", ["reason", "run"])
    capsys.readouterr()
    assert toolchain_main() == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["entry"] == "Main"
    assert data["runtime_result"]["result"] == 20


def test_ambiguous_calculations_without_main_fails_and_lists_candidates(tmp_path: Path, monkeypatch, capsys, native_runtime_host: Path) -> None:
    from toolchain.__main__ import main as toolchain_main

    project_dir = tmp_path / "ambiguous"
    project_dir.mkdir(parents=True)
    (project_dir / "src").mkdir()
    (project_dir / "reason.toml").write_text(
        """[package]
name = "ambiguous"
version = "0.1.0"
[runtime]
backend = "RuntimeReal"
""",
        encoding="utf-8",
    )
    (project_dir / "src" / "main.rsn").write_text(
        """model Main {
    calculation First {
        result = 1
    }
    calculation Second {
        result = 2
    }
}
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(sys, "argv", ["reason", "run"])
    capsys.readouterr()
    exit_code = toolchain_main()
    assert exit_code == 1

    out = capsys.readouterr().out
    assert "AmbiguousEntry" in out
    assert "First" in out
    assert "Second" in out


def test_explicit_positional_and_flag_entry_selection(tmp_path: Path, monkeypatch, capsys, native_runtime_host: Path) -> None:
    from toolchain.__main__ import main as toolchain_main

    project_dir = tmp_path / "explicit"
    project_dir.mkdir(parents=True)
    (project_dir / "src").mkdir()
    (project_dir / "reason.toml").write_text(
        """[package]
name = "explicit"
version = "0.1.0"
[runtime]
backend = "RuntimeReal"
""",
        encoding="utf-8",
    )
    (project_dir / "src" / "main.rsn").write_text(
        """model Main {
    calculation First {
        result = 111
    }
    calculation Second {
        result = 222
    }
}
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)

    # Positional argument selection: reason run First
    monkeypatch.setattr(sys, "argv", ["reason", "run", "First"])
    capsys.readouterr()
    assert toolchain_main() == 0
    data1 = json.loads(capsys.readouterr().out)
    assert data1["entry"] == "First"
    assert data1["runtime_result"]["result"] == 111

    # Flag argument selection: reason run --entry Second
    monkeypatch.setattr(sys, "argv", ["reason", "run", "--entry", "Second"])
    assert toolchain_main() == 0
    data2 = json.loads(capsys.readouterr().out)
    assert data2["entry"] == "Second"
    assert data2["runtime_result"]["result"] == 222


def test_unknown_entry_reports_available_candidates(tmp_path: Path, monkeypatch, capsys, native_runtime_host: Path) -> None:
    from toolchain.__main__ import main as toolchain_main

    project_dir = tmp_path / "unknown"
    project_dir.mkdir(parents=True)
    (project_dir / "src").mkdir()
    (project_dir / "reason.toml").write_text(
        """[package]
name = "unknown"
version = "0.1.0"
[runtime]
backend = "RuntimeReal"
""",
        encoding="utf-8",
    )
    (project_dir / "src" / "main.rsn").write_text(
        """model Main {
    calculation CalcA {
        result = 1
    }
    calculation CalcB {
        result = 2
    }
}
""",
        encoding="utf-8",
    )

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(sys, "argv", ["reason", "run", "NoSuchCalc"])
    capsys.readouterr()
    exit_code = toolchain_main()
    assert exit_code == 1

    out = capsys.readouterr().out
    assert "UnknownEntry" in out
    assert "No calculation named: NoSuchCalc" in out
    assert "CalcA" in out
    assert "CalcB" in out


def test_cli_help_options(capsys, monkeypatch) -> None:
    from toolchain.__main__ import main as toolchain_main

    monkeypatch.setattr(sys, "argv", ["reason", "run", "--help"])
    assert toolchain_main() == 0
    out = capsys.readouterr().out
    assert "Usage: reason run" in out
    assert "--entry" in out
