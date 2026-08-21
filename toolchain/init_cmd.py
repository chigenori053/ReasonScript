"""reason init — create a new ReasonScript project."""

from __future__ import annotations

from pathlib import Path

from toolchain.distribution_validation import normalize_project_identifier

_REASON_TOML = """\
[package]
name = "{project_name}"
identifier = "{identifier}"
version = "0.1.0"

[project]
name = "{project_name}"
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

_AGENTS_MD = """\
# Coding Agent Instructions

## Authority

`SPECIFICATIONS/Project_Specification.md` records the project-specific scope.
Its initial status is `DRAFT`; placeholders and `TBD` entries are not accepted
requirements. Implement project-specific behavior only when the user explicitly
approves the scope or an accepted specification records it.

## Development Workflow

Execute phases in this order:

1. Specification
2. Implementation
3. Validation
4. Artifact verification
5. Golden tests, when a Golden corpus exists
6. Completion report

Preserve unrelated user changes and keep task states monotonic:
`DRAFT -> IN_PROGRESS -> IMPLEMENTED -> VALIDATED -> COMPLETED`.

## Required Validation

Run these commands before reporting completion:

```sh
reason check
reason run
reason artifacts src/main.rsn
reason project-validate --json
```

Use `reason ci --json` only when this project is developed inside a repository
that declares the ReasonScript Agent Development Protocol and its CI resources.

## Artifact and Golden Policy

Do not manually edit generated files under `artifacts/` or `target/`. Regenerate
them through official `reason` commands. Update Golden baselines only for an
accepted specification change or an intentional compatibility change, and
record the change in project documentation.

## Completion Report

Report the completion summary, implemented features, validation results,
generated artifacts, compatibility notes, and remaining work. Do not claim
`VALIDATED` unless all required validation commands pass.
"""

_PROJECT_SPECIFICATION = """\
# {project_name} Project Specification

Specification ID: `{identifier}-project/0.1`

Status: DRAFT

Owner: project-maintainer

## Purpose

TBD. Describe the problem this project solves and its intended users.

## Requirements

- TBD. Replace this placeholder with approved, testable behavior.

## Non-goals

- TBD. Record behavior that is intentionally outside the project scope.

## Compatibility

- ReasonScript requirement: `>=0.5.0`
- Package identifier: `{identifier}`
- TBD. Record external interfaces and compatibility guarantees.

## Acceptance Criteria

- [ ] Project-specific requirements are approved and no required item remains
  `TBD`.
- [ ] `reason check` passes.
- [ ] `reason run` passes.
- [ ] `reason artifacts src/main.rsn` produces valid artifacts.
- [ ] `reason project-validate --json` reports `passed`.

## Validation

```sh
reason check
reason run
reason artifacts src/main.rsn
reason project-validate --json
```

## Remaining Decisions

- TBD. Resolve these decisions with the project owner before implementation.
"""


def run(project_name: str, args: list[str] | None = None) -> int:
    args = args or []
    template = "minimal"
    if "--template" in args:
        index = args.index("--template")
        if index + 1 >= len(args) or args[index + 1] not in {"minimal", "agent"}:
            print(
                "Error:\n\nUnsupportedTemplate\n\n"
                "Available templates: minimal, agent."
            )
            return 1
        template = args[index + 1]
    root = Path(project_name)
    package_name = normalize_project_identifier(root.resolve().name if project_name == "." else root.name)
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
        _REASON_TOML.format(project_name=root.resolve().name, identifier=package_name), encoding="utf-8"
    )
    (root / "src" / "main.rsn").write_text(
        _MAIN_RSN.format(name=package_name), encoding="utf-8"
    )
    (root / "tests" / "sample_test.rsn").write_text(
        _SAMPLE_TEST_RSN.format(name=package_name), encoding="utf-8"
    )
    (root / "README.md").write_text(f"# {root.resolve().name}\n\nA ReasonScript project.\n", encoding="utf-8")
    (root / ".gitignore").write_text("target/\nartifacts/*\n!artifacts/.gitkeep\n", encoding="utf-8")
    (root / "artifacts" / ".gitkeep").write_text("", encoding="utf-8")
    if template == "agent":
        (root / "SPECIFICATIONS").mkdir(parents=True)
        (root / "AGENTS.md").write_text(_AGENTS_MD, encoding="utf-8")
        (root / "SPECIFICATIONS" / "Project_Specification.md").write_text(
            _PROJECT_SPECIFICATION.format(
                project_name=root.resolve().name,
                identifier=package_name,
            ),
            encoding="utf-8",
        )

    print(f"Created project: {project_name}")
    print(f"Package identifier: {package_name}")
    return 0
