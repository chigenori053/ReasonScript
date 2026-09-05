# ReasonScript coding-agent guide

Read [the documentation index](docs/README.md), the
[language reference](docs/language-reference.md), and
[CONTRIBUTING.md](CONTRIBUTING.md) before changing public behavior.

## Development Workflow

Use these phases in order: Specification, Implementation, Validation, Artifact verification,
Golden tests, Completion report. A specification may be an issue, test, or
concise task description; do not create phase-specific planning docs inside the
repository.

Task states are monotonic:

`DRAFT -> IN_PROGRESS -> IMPLEMENTED -> VALIDATED -> COMPLETED`

`REJECTED` is terminal when the accepted scope cannot be completed.

## Required Commands

The Canonical CI Entry Point is:

```sh
./reason ci --json
```

Focused commands for diagnosis and incremental work are:

```sh
./reason workspace
./reason check <source.rsn>
./reason analyze <source.rsn>
./reason run <source.rsn>
./reason artifacts <source.rsn> --out <directory>
./reason validate-artifacts <directory>
./reason golden
./reason agent-protocol --json
./reason agent-report --json
```

## Validation Sequence

Every code change must pass workspace validation, diagnostics validation,
artifact validation, and Golden tests. `reason ci` is the required final gate.
CI Stabilization rules are reported as `CI-001` through `CI-010`; canonical
entry-point rules are reported as `CE-001` through `CE-005`.

## Artifact Policy

Generated artifacts must conform to their schemas and must not be edited by
hand. Regenerate them with the owning `reason` command. Frozen compatibility
baselines are stored in `contracts/`.

## Golden Policy

Update Golden baselines only for an intentional behavior or compatibility
change. Add the matching entry to `CHANGELOG.md`; never accept a failing output
automatically.

## Coding Agent Policy

- Preserve unrelated user changes and generated files.
- Prefer behavior tests over tests that assert a planning document exists.
- Keep public docs current and task-oriented. Do not add implementation or
  validation reports.
- Use the Rust runtime as the production execution path. Python runtime modules
  are reference implementations unless code explicitly says otherwise.
- Treat `schemas/` and `contracts/` as machine interfaces, not prose docs.

## Completion Criteria

A task is complete only when implementation matches the requested behavior,
required validations pass, generated artifacts validate, Golden tests pass,
and remaining work is reported.

## Reporting Format

The Completion report must summarize the change, validation results, generated
artifacts, compatibility notes, and remaining work. When a machine-readable
report is required, generate `agent_report.json` with `reason agent-report`.
