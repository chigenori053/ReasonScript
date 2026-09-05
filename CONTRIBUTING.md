# Contributing to ReasonScript

Issues and pull requests are welcome. For a behavior change, open an issue
first so the intended language or compatibility impact can be agreed on.

## Development setup

Install Python 3.11+, Git, and Rust/Cargo, then clone the repository. Commands
may be run through `./reason` without installing the package globally.

```sh
./reason --version
./reason check examples/v0_5/002_single_calculation.rsn --json
./reason run examples/v0_5/002_single_calculation.rsn --json
```

## Change workflow

1. Describe the observable behavior and compatibility impact.
2. Implement the smallest coherent change.
3. Add or update tests for the behavior, not for planning documents.
4. Regenerate artifacts only through the appropriate `reason` command.
5. Run the canonical validation command.

```sh
./reason ci --json
```

For focused diagnosis, use `reason workspace`, `reason check`, `reason
analyze`, `reason validate-artifacts`, and `reason golden`.

Do not edit generated artifacts or frozen contract baselines manually. Update a
baseline only for an intentional compatibility change, and record that change
in [CHANGELOG.md](CHANGELOG.md).

## Documentation

User-facing language behavior belongs in
[docs/language-reference.md](docs/language-reference.md). CLI behavior belongs
in [docs/reference/cli.md](docs/reference/cli.md). Keep current documentation
task-oriented; do not add implementation reports, validation transcripts, or
phase-specific design documents. Git history and pull requests retain that
development record.
