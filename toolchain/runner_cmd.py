"""reason test — discover and execute ReasonScript test suites."""

from __future__ import annotations

from pathlib import Path

from .manifest import Manifest, ManifestError
from .pipeline import PipelineError, compile_source


def run(project_root: Path) -> int:
    try:
        Manifest.load(project_root)
    except ManifestError as e:
        print(f"Error:\n\n{e}")
        return 1

    tests_dir = project_root / "tests"
    if not tests_dir.exists():
        print("No tests/ directory found.")
        return 0

    test_files = sorted(tests_dir.rglob("*.rsn"))
    if not test_files:
        print("No test files found.")
        return 0

    passed: list[str] = []
    failed: list[tuple[str, str]] = []

    for test_path in test_files:
        name = test_path.stem
        source = test_path.read_text(encoding="utf-8")
        try:
            compile_source(source, test_path)
            passed.append(name)
        except PipelineError as e:
            failed.append((name, f"{e.code}: {e.message}"))

    for name in passed:
        print(f"PASS  {name}")
    for name, msg in failed:
        print(f"FAIL  {name}")
        print(f"      {msg}")

    print()
    print(f"{len(passed)} passed")
    print(f"{len(failed)} failed")

    return 3 if failed else 0
