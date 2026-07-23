# Quick Start

Goal: a running ReasonScript program in under 10 minutes. This assumes
you've completed [installation.md](installation.md) (Python 3.11+ is
enough for everything below).

## 1. Create a Project

```sh
./reason init hello_world
cd hello_world
```

This scaffolds:

```text
hello_world/
  reason.toml
  src/main.rsn
  tests/sample_test.rsn
  target/{ast,ir,metadata,runtime}/
  packages/
```

`reason.toml`:

```toml
[package]
name = "hello_world"
version = "0.1.0"

[compiler]
language_core = "0.7"
platform = "0.2"

[runtime]
backend = "RuntimeReal"
```

`src/main.rsn`:

```reasonscript
package hello_world
module main {
    fn run(goal) {
        return goal
    }
}
```

## 2. Build It

```sh
./reason build
```

This compiles every `.rsn` file under `src/` through the full pipeline
(Surface AST -> Semantic AST -> Reason IR) and writes artifacts under
`target/`, using a content-addressed build cache
(`.reason_build_cache`). See
[docs/architecture/compiler.md](../architecture/compiler.md) for what
happens during this step.

## 3. Run It

```sh
./reason run
```

`reason run` requires build artifacts to already exist (`target/ir/*.json`)
— if you see a `NoBuildArtifacts` error, run `reason build` first. It reads
`[runtime] backend` from `reason.toml` and dispatches to `RuntimeReal` or
`HybridRuntime` accordingly (see
[docs/architecture/runtime.md](../architecture/runtime.md)).

## 4. Check and Test

```sh
./reason check    # validate sources without building
./reason test      # run tests/*.rsn
```

## 5. Write Something of Your Own

Edit `src/main.rsn` to add a function and a Calculation:

```reasonscript
package hello_world
module main {
    fn Value() -> int {
        return 42
    }

    calculation Result {
        result = Value()
    }

    fn run(goal) {
        return goal
    }
}
```

Rebuild and rerun:

```sh
./reason build
./reason run
```

## What Just Happened

- `reason init` scaffolded a single-package project (multi-package
  dependency resolution isn't implemented yet — see
  [COMPATIBILITY.md](../../COMPATIBILITY.md)).
- `reason build` ran your source through the full compiler pipeline down to
  Reason IR.
- `reason run` planned a deterministic `ExecutionPlan` and executed it on
  `RuntimeReal`, producing a committed result.

## Next Steps

- [first-project.md](first-project.md) — a fuller walkthrough: structs,
  enums, pattern matching.
- [docs/language/syntax.md](../language/syntax.md) — the full language
  surface.
- [docs/references/cli.md](../references/cli.md) — every `reason`
  subcommand and flag.
