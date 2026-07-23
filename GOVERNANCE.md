# Governance

ReasonScript is a young open-source project. This document describes how
decisions are made today, and how governance is expected to evolve as the
contributor base grows.

## Current Model: Benevolent Maintainer(s)

At this stage, the project is led by its founding maintainer(s), who have
final say on:

- Technical direction and the [ROADMAP](ROADMAP.md).
- What gets merged, and when a release is cut.
- Interpretation of this governance document and the
  [Code of Conduct](CODE_OF_CONDUCT.md).

This is a deliberate, temporary model for a pre-1.0 project: it favors fast,
consistent decisions over process while the core language, Compiler, and
Runtime semantics are still being frozen (see
[COMPATIBILITY.md](COMPATIBILITY.md)). It is expected to evolve toward a
committee/maintainer-team model as the contributor base grows.

## Roles

- **Maintainers** — have merge/write access, set direction, review and
  merge pull requests, cut releases, and triage security reports (see
  [SECURITY.md](SECURITY.md)).
- **Contributors** — anyone who opens issues, discussions, or pull requests.
  See [CONTRIBUTING.md](CONTRIBUTING.md).

New maintainers are added by existing maintainer consensus, based on a
sustained record of quality contributions and sound judgment on project
direction.

## Decision Making

- Day-to-day changes (bug fixes, docs, small features) are decided by normal
  pull request review.
- Changes that affect a **frozen interface** (anything listed as fixed in
  [CHANGELOG.md](CHANGELOG.md) or [COMPATIBILITY.md](COMPATIBILITY.md), e.g.
  `reason-ir/0.1`, `reasonscript-ast/0.1`, `parser/0.1`, `compiler/0.1`)
  require a written proposal (an issue or a doc under
  `docs/specifications/`) and maintainer sign-off before implementation.
- Disagreements are resolved by maintainer consensus; in absence of
  consensus, the founding maintainer(s) make the final call.

## Contact

For governance questions or maintainer contact, open a
[Discussion](https://github.com/chigenori053/reasonscript/discussions) or
see the contact channel listed in [SUPPORT.md](SUPPORT.md). For security
reports, use [SECURITY.md](SECURITY.md) instead of a public channel.

## Changes to This Document

Changes to governance are proposed as a pull request against this file and
require maintainer consensus to merge.
