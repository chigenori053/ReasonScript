"""reason init — create a new ReasonScript project."""

from __future__ import annotations

from pathlib import Path

_REASON_TOML = """\
[package]
name = "{name}"
version = "0.1.0"

[project]
name = "{name}"
version = "0.1.0"
reason_version = ">=0.5.0"

[source]
entry = "src/main.rsn"

[artifacts]
directory = "artifacts"

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


def run(project_name: str, args: list[str] | None = None) -> int:
    args = args or []
    if "--template" in args:
        index = args.index("--template")
        if index + 1 >= len(args) or args[index + 1] != "minimal":
            print("Error:\n\nUnsupportedTemplate\n\nOnly the minimal template is available.")
            return 1
    root = Path(project_name)
    if root.exists() and project_name != ".":
        print(f"Error:\n\nProjectExists\n\nDirectory '{project_name}' already exists.")
        return 1

    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    root.mkdir(parents=True, exist_ok=True)
    (root / "target" / "ast").mkdir(parents=True)
    (root / "target" / "ir").mkdir(parents=True)
    (root / "target" / "metadata").mkdir(parents=True)
    (root / "target" / "runtime").mkdir(parents=True)
    (root / "packages").mkdir(parents=True)
    (root / "artifacts").mkdir(parents=True)

    (root / "reason.toml").write_text(
        _REASON_TOML.format(name=project_name), encoding="utf-8"
    )
    (root / "src" / "main.rsn").write_text(
        _MAIN_RSN.format(name=project_name), encoding="utf-8"
    )
    (root / "tests" / "sample_test.rsn").write_text(
        _SAMPLE_TEST_RSN.format(name=project_name), encoding="utf-8"
    )
    (root / "README.md").write_text(f"# {root.resolve().name}\n\nA ReasonScript project.\n", encoding="utf-8")
    (root / ".gitignore").write_text("target/\nartifacts/*\n!artifacts/.gitkeep\n", encoding="utf-8")
    (root / "artifacts" / ".gitkeep").write_text("", encoding="utf-8")

    print(f"Created project: {project_name}")
    return 0
