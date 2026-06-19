"""reason init — create a new ReasonScript project."""

from __future__ import annotations

from pathlib import Path

_REASON_TOML = """\
[package]
name = "{name}"
version = "0.1.0"

[compiler]
language_core = "0.7"
platform = "0.2"

[runtime]
backend = "RuntimeReal"
"""

_MAIN_RSN = """\
package {name}
module main {{
    fn run(goal) {{
        return goal
    }}
}}
"""

_SAMPLE_TEST_RSN = """\
package {name}
module sample_test {{
    fn run(goal) {{
        return goal
    }}
}}
"""


def run(project_name: str) -> int:
    root = Path(project_name)
    if root.exists():
        print(f"Error:\n\nProjectExists\n\nDirectory '{project_name}' already exists.")
        return 1

    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "target" / "ast").mkdir(parents=True)
    (root / "target" / "ir").mkdir(parents=True)
    (root / "target" / "metadata").mkdir(parents=True)
    (root / "target" / "runtime").mkdir(parents=True)
    (root / "packages").mkdir(parents=True)

    (root / "reason.toml").write_text(
        _REASON_TOML.format(name=project_name), encoding="utf-8"
    )
    (root / "src" / "main.rsn").write_text(
        _MAIN_RSN.format(name=project_name), encoding="utf-8"
    )
    (root / "tests" / "sample_test.rsn").write_text(
        _SAMPLE_TEST_RSN.format(name=project_name), encoding="utf-8"
    )

    print(f"Created project: {project_name}")
    return 0
