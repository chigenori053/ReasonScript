# ReasonScript

ReasonScript is a reasoning-first programming language for proofable AI
workflows, deterministic execution, and rollback-safe systems. It is
currently at **`0.1.0-alpha`** — an early, working platform with frozen
core interfaces, not yet a Beta-ready product. See
[COMPATIBILITY.md](COMPATIBILITY.md) before depending on it in production.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## 1. What is ReasonScript?

ReasonScript is a language and runtime pair built around one idea: **a
program is a typed graph of states and transitions, and every execution
step is validated before it commits.** Instead of running arbitrary
imperative code, a ReasonScript program declares a `Goal`, an initial
`State`, and a set of candidate `Transition`s and `Constraint`s; the
compiler and runtime deterministically plan and execute a path between
them, producing a fully traceable, reversible history.

This makes it suited to workloads where you need to *prove* what happened
and why — AI-assisted planning, simulation, and any system where silent,
unauditable state mutation is unacceptable.

## 2. Design Goals

- **Determinism** — identical input (Reason IR + policies) always produces
  the same plan and the same result.
- **Auditability** — every committed change is traceable back to the
  `Goal` and `Constraint`s that justified it.
- **Rollback-safety** — failure reverts through a traced reverse delta, not
  a silent discard; history is never edited.
- **Layered, versioned interfaces** — the Compiler, Runtime, and IR are
  independently frozen and versioned so tooling can depend on a stable
  contract even while the language surface evolves. See
  [COMPATIBILITY.md](COMPATIBILITY.md).
- **No special-cased escape hatches** — even mathematical computation is
  ordinary `State --Transition--> State`, not a separate evaluator.

## 3. Key Features

- A module/function/struct/enum language surface with pattern matching
  (or-patterns, guards, struct destructuring) — see
  [docs/language/syntax.md](docs/language/syntax.md).
- A validation-only type system covering primitives (`Int`, `Float`,
  `Bool`, `String`) and Reason State types (`Concept`, `Object`, `Event`,
  `Action`, `Attribute`, `Goal`, `Constraint`) — see
  [docs/language/type-system.md](docs/language/type-system.md).
- A deterministic compiler pipeline: Source -> Surface AST -> Semantic AST
  -> Reason IR -> ExecutionPlan — see
  [docs/architecture/compiler.md](docs/architecture/compiler.md).
- Two Rust execution engines (`RuntimeReal`, `HybridRuntime`) implementing
  a Prepare -> Validate -> Commit -> StateDelta transaction protocol — see
  [docs/architecture/runtime.md](docs/architecture/runtime.md).
- A WorldModel SDK for building, validating, and simulating spatial/
  semantic scenes on top of the runtime — see
  [docs/architecture/worldmodel.md](docs/architecture/worldmodel.md).
- A versioned Reason IR JSON ABI with DTO bindings for Rust, Python,
  TypeScript, Go, and Java (`dto/`), plus a layered conformance framework
  (`conformance/`).
- A `reason` CLI (`init`/`build`/`run`/`test`/`check`), a VS Code
  extension, an LSP, and an early desktop IDE — see
  [docs/guides/ide.md](docs/guides/ide.md).

## 4. Architecture Overview

```text
ReasonScript Source (.rsn)
  -> Surface AST            (frontend/language_surface/)
  -> Semantic AST           (frontend/ast/)
  -> Reason IR              (reason-ir/0.1)
  -> ExecutionPlan          (immutable)
  -> Runtime execution      (RuntimeReal / HybridRuntime)
  -> StateDelta + InferenceResult
```

Full breakdown, including the ReasonUnit graph model, the WorldModel SDK,
and what's explicitly *not* implemented (Cluster Runtime, a standalone
Tensor Runtime): [docs/architecture/overview.md](docs/architecture/overview.md).

## 5. Installation

```sh
git clone https://github.com/chigenori053/reasonscript.git
cd reasonscript
./reason --help
```

The `reason` CLI needs only Python 3.11+. Building the Rust runtimes
(`RuntimeReal`, `HybridRuntime`) additionally needs `cargo`. Full
requirements and verification steps:
[docs/guides/installation.md](docs/guides/installation.md).

## 6. Quick Start

```sh
./reason init hello_world
cd hello_world
./reason build
./reason run
```

Full 10-minute walkthrough: [docs/guides/quick-start.md](docs/guides/quick-start.md).
A fuller worked example with structs, enums, and pattern matching:
[docs/guides/first-project.md](docs/guides/first-project.md).

## 7. Example

```reasonscript
package scorer
module main {

    enum Tier {
        Bronze
        Silver
        Gold
    }

    struct Player {
        wins: int
        tier: Tier
    }

    fn TierBonus(tier: Tier) -> int {
        match tier {
            Tier.Bronze => return 0
            Tier.Silver => return 5
            Tier.Gold => return 10
        }
    }

    fn Score(player: Player) -> int {
        match player {
            Player { wins } when wins > 100 => return 100 + TierBonus(player.tier)
            Player { } => return player.wins + TierBonus(player.tier)
        }
    }

    calculation Result {
        result = Score(Player { wins: 42, tier: Tier.Silver })
    }
}
```

More syntax: [docs/language/syntax.md](docs/language/syntax.md).

## 8. Current Status

ReasonScript is **`0.1.0-alpha`**, architecturally coherent but explicitly
**not Beta-ready**. Subsystem maturity (from the Platform Architecture
Review):

| Subsystem | Status |
| --- | --- |
| Language, Runtime, Execution Architecture, Toolchain, SDK, World Model SDK, LSP, IDE | Partially Complete |
| Cross-Layer Architecture, Versioning | Requires Refactoring |
| ReasoningTrace | Missing (proposal only) |
| Cluster Runtime | Not implemented |

Frozen interfaces (`reason-ir/0.1`, `parser/0.1`, `compiler/0.1`,
`reasonscript-language-surface/0.1`, `reasonscript-semantic-language/0.2`,
and more) are safe to build tooling against; everything else can change
without notice. Full detail, known limitations, and what Beta requires:
[COMPATIBILITY.md](COMPATIBILITY.md).

## 9. Documentation

Documentation is organized into three layers:

1. **Users** — [Guides](docs/guides/): installation, quick start, first
   project, IDE setup, migration.
2. **Developers** — [Language](docs/language/) (syntax, semantics, type
   system) and [Reference](docs/references/) (CLI, diagnostics, glossary).
3. **System architects / researchers** —
   [Architecture](docs/architecture/) (compiler, runtime, ReasonUnit,
   WorldModel, and the honest status of Cluster Runtime and Tensor) and
   [Specifications](docs/specifications/) (every normative spec and
   validation report).

Also see [ROADMAP.md](ROADMAP.md), [COMPATIBILITY.md](COMPATIBILITY.md),
and [CHANGELOG.md](CHANGELOG.md).

## 10. Roadmap

Current focus is Beta readiness: platform diagnostics, a `ReasoningTrace`
contract, a Toolchain package graph, and `ExecutionScope`/`CallStack`
semantics. Full roadmap, including completed phases:
[ROADMAP.md](ROADMAP.md).

## 11. Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for
development setup, build/test commands, and how to propose changes to a
frozen interface. Please also read
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Project decision-making is
described in [GOVERNANCE.md](GOVERNANCE.md); for help, see
[SUPPORT.md](SUPPORT.md); to report a vulnerability, see
[SECURITY.md](SECURITY.md).

## 12. License

Licensed under the [Apache License, Version 2.0](LICENSE). See
[NOTICE](NOTICE) for attribution.

Copyright 2026 ReasonScript Contributors.
