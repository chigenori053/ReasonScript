# First Project

This walks through a slightly fuller ReasonScript project than
[quick-start.md](quick-start.md): structs, an enum, pattern matching with a
guard, and a Calculation, wired together in one module.

## Set Up

```sh
./reason init scorer
cd scorer
```

## Write the Program

Replace `src/main.rsn` with:

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

    fn run(goal) {
        return goal
    }
}
```

This exercises, in order: [enums](../language/syntax.md#enums),
[structs](../language/syntax.md#structs),
[pattern matching with guards](../language/syntax.md#pattern-matching), and
a [Calculation](../language/syntax.md#calculations).

## Build, Check, Test

```sh
./reason check    # syntax + structural validation only
./reason build     # full pipeline to Reason IR
./reason test
```

If `check` reports a non-exhaustive match, re-read
[pattern_guard_v1.md](../specifications/pattern_guard_v1.md) — remember
that a guarded arm (`when wins > 100`) never counts toward exhaustiveness,
so the plain `Player { }` fallback above is required.

## Run It

```sh
./reason run
```

## Add a Test

`tests/sample_test.rsn` follows the same module syntax as `src/`. Add an
assertion-style scenario using the same `Player`/`Score` shape as above
(mirroring the pattern used throughout `tests/*.rsn` in the main
repository, e.g. `tests/pg_001.rsn` for a guard example and `tests/op_003.rsn`
for a struct or-pattern example) and rerun `./reason test`.

## Inspect What the Compiler Produced

```sh
cat target/ir/main.json   # exact path depends on your project layout
```

This is the Reason IR document described in
[docs/architecture/compiler.md](../architecture/compiler.md) — useful when
debugging why a program behaves unexpectedly, since it's the actual input
to the runtime, not your source text.

## Next Steps

- [docs/language/type-system.md](../language/type-system.md) — add type
  annotations (`Int`, `Float`, or a `Goal`/`Constraint` Reason State type)
  to this project.
- [docs/architecture/overview.md](../architecture/overview.md) — understand
  what `reason run` did under the hood.
- [ide.md](ide.md) — set up editor support for a project like this one.
