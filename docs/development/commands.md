# ReasonScript — Development Commands

All development commands use the unified entry point:

```bash
python3 scripts/dev.py <command>
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
Launch the Playground IDE (backend + frontend together).

```bash
python3 scripts/dev.py playground
```

Opens `http://localhost:5173`. Runs backend on port 8000.

---

### `ide`
Launch the Desktop IDE (Tauri).

```bash
python3 scripts/dev.py ide
```

Requires `ide/desktop/` to be present. Not available in the current phase.

---

### `backend`
Launch the Playground backend only (port 8000).

```bash
python3 scripts/dev.py backend
```

Runs: `uvicorn playground.backend.main:app --reload`

---

### `frontend`
Launch the Playground frontend dev server only (port 5173).

```bash
python3 scripts/dev.py frontend
```

Runs: `npm run dev -- --port 5173` in `playground/frontend/`

---

### `build`
Production / validation build.

```bash
python3 scripts/dev.py build
```

Runs `npm run build` in `playground/frontend/`.

---

### `test smoke`
Minimum smoke validation.

```bash
python3 scripts/dev.py test smoke
```

Runs: `tests/compatibility`, `playground_integration_tests`, frontend build.

---

### `test backend`
Compiler / analyzer / compatibility tests.

```bash
python3 scripts/dev.py test backend
```

---

### `test frontend`
Frontend build validation.

```bash
python3 scripts/dev.py test frontend
```

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
