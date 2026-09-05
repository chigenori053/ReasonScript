# ReasonScript — Development Commands

All development commands use the unified entry point:

```bash
python3 scripts/dev.py <command>
```

## Official IDE

The official IDE UI lives in:

```text
apps/reasonscript-ide/ui
```

Run the official IDE workflow with the backend and UI in separate terminals:

```bash
python3 scripts/dev.py backend
python3 scripts/dev.py ide-ui
```

`python3 scripts/dev.py ide` prints this workflow. It does not launch multiple long-running processes in one Python command.

## Legacy Playground UI

The legacy Playground frontend (`playground/frontend`) was physically removed in Phase 4.5-D. `python3 scripts/dev.py playground` and `python3 scripts/dev.py frontend` now print an error directing you to `ide` / `ide-ui`.

## Command Reference

## ReasonScript CLI

Package manifests may optionally declare a canonical source entry:

```toml
[source]
entry = "src/main.rsn"
```

When present, the entry file must exist and is validated as the package's
canonical source. The remaining `src/**/*.rsn` files are still compiled as
the complete module graph. Manifests without `[source]` retain the legacy
recursive multi-file discovery behavior.

```bash
python3 scripts/dev.py reason check <file.rsn>
python3 scripts/dev.py reason analyze <file.rsn>
python3 scripts/dev.py reason run <file.rsn>
python3 scripts/dev.py reason artifacts <file.rsn> --out <dir>
python3 scripts/dev.py reason examples
```

The ReasonScript CLI is the official non-IDE compiler/runtime path. It reuses the backend analyze pipeline used by the official IDE and can emit stable JSON with `--json`.

---

### `setup`
Install / fetch all dependencies.

```bash
python3 scripts/dev.py setup
```

Runs: `pip install -r requirements-dev.txt`, creates `playground/.venv`, `npm install` (official IDE UI), `cargo fetch` (Rust workspaces).

---

### `check`
Environment and repository sanity check.

```bash
python3 scripts/dev.py check
```

Delegates to `python3 scripts/check_environment.py`.

---

### `ide`
Show the official IDE workflow.

```bash
python3 scripts/dev.py ide
```

Prints the two-terminal workflow for `backend` and `ide-ui`.

---

### `ide-ui`
Launch the official IDE UI dev server only (port 5173).

```bash
python3 scripts/dev.py ide-ui
```

Runs: `npm run dev -- --host 0.0.0.0 --port 5173` in `apps/reasonscript-ide/ui/`

---

### `backend`
Launch the Playground backend only (port 8000).

```bash
python3 scripts/dev.py backend
```

Runs: `uvicorn playground.backend.main:app --reload`

---

### `build`
Production / validation build.

```bash
python3 scripts/dev.py build
```

Runs `npm run build` in `apps/reasonscript-ide/ui/`.

---

### `test smoke`
Minimum smoke validation.

```bash
python3 scripts/dev.py test smoke
```

Runs: `tests/compatibility`, `playground_integration_tests`, official IDE UI build.

---

### `test backend`
Compiler / analyzer / compatibility tests.

```bash
python3 scripts/dev.py test backend
```

---

### `test frontend`
Official IDE UI build validation.

```bash
python3 scripts/dev.py test frontend
```

Runs `npm run build` in `apps/reasonscript-ide/ui/`.

---

### `test rust`
Rust workspace tests (RuntimeReal, HybridRuntime).

```bash
python3 scripts/dev.py test rust
```

---

### `test ide`
IDE contract / visualization tests.

```bash
python3 scripts/dev.py test ide
```

Runs: `ide_phase1_tests/`, `tests/ide/`.

---

### `test all`
CI-equivalent full test run.

```bash
python3 scripts/dev.py test all
```

Runs all test categories sequentially.

---

## Environment Check Script

```bash
python3 scripts/check_environment.py
```

Standalone environment verification. Can be run without `dev.py`.
