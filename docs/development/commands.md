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

`playground/frontend` remains available for legacy verification only. It is not the official IDE target for Phase 5 and later.

```bash
python3 scripts/dev.py playground
python3 scripts/dev.py frontend
```

## Command Reference

### `setup`
Install / fetch all dependencies.

```bash
python3 scripts/dev.py setup
```

Runs: `pip install -r requirements-dev.txt`, creates `playground/.venv`, `npm install` (frontend), `cargo fetch` (Rust workspaces).

---

### `check`
Environment and repository sanity check.

```bash
python3 scripts/dev.py check
```

Delegates to `python3 scripts/check_environment.py`.

---

### `playground`
Launch the legacy Playground UI workflow (backend + frontend together).

```bash
python3 scripts/dev.py playground
```

This command is deprecated for official IDE development. Opens `http://localhost:5173`. Runs backend on port 8000.

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

### `frontend`
Launch the legacy Playground frontend dev server only (port 5173).

```bash
python3 scripts/dev.py frontend
```

This command is deprecated for official IDE development. Runs: `npm run dev -- --port 5173` in `playground/frontend/`

---

### `build`
Production / validation build.

```bash
python3 scripts/dev.py build
```

Runs `npm run build` in `apps/reasonscript-ide/ui/`, then runs the legacy build in `playground/frontend/`.

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

### `test playground-frontend`
Legacy Playground frontend build validation.

```bash
python3 scripts/dev.py test playground-frontend
```

Runs `npm run build` in `playground/frontend/`.

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
