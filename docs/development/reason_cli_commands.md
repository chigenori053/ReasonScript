# ReasonScript CLI Commands

## Check

```bash
python3 scripts/dev.py reason check <file.rsn>
```

Runs source read, parser validation, semantic validation, and normalized diagnostics. Returns exit code `0` for valid source and `1` for ReasonScript diagnostics.

## Analyze

```bash
python3 scripts/dev.py reason analyze <file.rsn> --json
python3 scripts/dev.py reason analyze <file.rsn> --out artifacts/cli/<name>
```

Runs the IDE/backend analyze path and returns a deterministic CLI wrapper containing diagnostics, artifacts, and `project_state`.

## Run

```bash
python3 scripts/dev.py reason run <file.rsn> --json
python3 scripts/dev.py reason run <file.rsn> --trace
```

Runs analyze plus simulation/runtime result reporting. JSON output uses `reasonscript-cli-run/0.1`.

## Artifacts

```bash
python3 scripts/dev.py reason artifacts <file.rsn> --out <dir>
```

Writes stable JSON artifact filenames.

## Examples

```bash
python3 scripts/dev.py reason examples
```

Validates the `examples/v0_5` corpus.

