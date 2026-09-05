# ReasonScript documentation

This directory contains the documentation needed to learn, use, and contribute
to ReasonScript. It describes the current implementation; design proposals and
phase-completion reports are kept in Git history instead of the public docs.

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
