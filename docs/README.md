# ReasonScript documentation

This directory contains the documentation needed to learn, use, and contribute
to ReasonScript. It describes the current implementation; design proposals and
phase-completion reports are kept in Git history instead of the public docs.

> **Language Identity & Disambiguation**: ReasonScript is an independent reasoning-first programming language. It is **not affiliated with, derived from, or compatible with ReScript, Reason, or ReasonML**. ReasonScript code is written in `.rsn` files and compiled/executed via the native `reason` toolchain.

## Start here

- [Quickstart](guides/quickstart.md) — install, create a project, and run a
  calculation.
- [Language reference](language-reference.md) — syntax, types, statements,
  declarations, matching, modules, and execution behavior.
- [Standard library](standard-library.md) — runtime, Tensor, optimizer,
  relation, Vision, and RUO namespaces.
- [CLI reference](reference/cli.md) — everyday project, inspection, artifact,
  and validation commands.

## Topics

- [Installation](installation/README.md)
- [ReasonUnit Objects](reasonunit-object.md)
- [Known limitations](releases/ReasonScript_v0_5_Known_Limitations.md)
- [Roadmap](roadmap.md)
- [Contributing](../CONTRIBUTING.md)
- [Changelog](../CHANGELOG.md)

## Which document is authoritative?

For source code, use the [language reference](language-reference.md). For CLI
behavior, use `reason help` and the [CLI reference](reference/cli.md). JSON
interfaces are defined by the files in [`schemas/`](../schemas), while frozen
runtime compatibility baselines are in [`contracts/`](../contracts).

If prose and executable behavior disagree, treat it as a bug: open an issue
with a minimal `.rsn` example and the output of `reason --version`.

## Historical engineering records

The following directories are retained for traceability and are not current
product specifications:

- `development/`: implementation decisions and design records
- `changelog/`: phase-specific change records
- `releases/`: earlier release scope and milestone records
- `validation/`: validation reports captured at a point in time

These records can mention older versions, incomplete platform certification,
or superseded plans. Current behavior is defined by the references in “Start
here”, the executable schemas, and the test suite.
