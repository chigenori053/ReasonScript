# ReasonScript IDE — frontend/ui Directory Inventory

Status: REVIEWED (Phase 4.5-A)

This document is the detailed per-directory inventory that supports
[ide_code_review_phase_4_5_a.md](ide_code_review_phase_4_5_a.md). It records
the ground truth found for each of the three `frontend`/`ui`-named
directories in the repository, so future phases do not need to re-derive it.

## 1. `apps/reasonscript-ide/ui` — OFFICIAL_IDE_UI

- **package.json**: present. `name: reasonscript-ide-ui`, `private: true`.
  Scripts: `dev` (vite), `build` (`tsc && vite build`), `preview`.
- **Stack**: React 18, TypeScript, Vite 5, Monaco Editor
  (`@monaco-editor/react`), Tauri 2 (`@tauri-apps/api`,
  `@tauri-apps/plugin-dialog`, `@tauri-apps/plugin-fs`, `@tauri-apps/cli`).
- **Platform adapters**: `src/platform/browserAdapter.ts`,
  `src/platform/desktopAdapter.ts`, `src/platform/types.ts`,
  `src/platform/index.ts`, `src/platform/commandRegistry.ts`,
  `src/platform/shortcuts.ts` — implements the `PlatformAdapter` contract
  documented in `platform_adapter_core.md` and `cross_platform_path_policy.md`.
- **Views** (15): `DependencyGraphView`, `DiagnosticsView`,
  `ExecutionPlanFlowView`, `ExecutionPlanView`, `JsonArtifactView`,
  `KnowledgeEvidenceView`, `ModelProjectionView`, `PipelineOverviewView`,
  `ReasonIRView`, `RuntimeOperationsView`, `SimulationTraceView`,
  `SourceModelView`, `StandardLayoutViews` (composition — wires the above
  into `StandardOverviewView` / `ArtifactsInspectorView`), `ValidationView`,
  `WorkspaceExplorerView`.
- **Visualization builders**: `src/visualization/build*.ts` (7 files) —
  transform `ProjectState` into view models.
- **State**: `src/state/projectStore.ts`, `src/state/workspaceStore.ts`.
- **API usage**: `bridge.ts` calls `/api/analyze` (POST) and `/api/core`;
  `browserAdapter.ts` calls `/api/workspace/list`, `/api/workspace/read`,
  `/api/workspace/save`. All other view state (`validation`, `analyzer`,
  `runtime_operations`, `simulation`, `knowledge`, `diagnostics`,
  `execution_plan`, `reason_ir`, `surface_ast`, `semantic_ast`) is derived
  client-side from the single `/api/analyze` JSON response — this UI does
  **not** call dedicated per-feature endpoints the way `playground/frontend`
  does.
- **Vite config**: `apps/reasonscript-ide/ui/vite.config.ts` present.
- **Wired into**:
  - `scripts/test_platform.py` — listed in `NPM_PROJECTS`, used for
    `npm:build:apps/reasonscript-ide/ui`, `npm:lint`/`npm:typecheck` steps.
  - **Not** wired into `scripts/dev.py` in any command (`ide` command looks
    for a nonexistent `ide/desktop` Tauri project instead).
  - Referenced in docs only structurally: `platform_adapter_core.md`,
    `cross_platform_path_policy.md`. Not named as "the official IDE" in
    `commands.md` or `test_matrix.md`.
  - Test coverage: `tests/ide/*` (22 Python files) test the underlying
    contracts (workspace adapter, command registry, platform adapter core,
    standard layout contract, per-file diagnostics/artifacts) that this UI
    implements, but these are Python-side contract tests, not a UI build/lint
    check.

## 2. `playground/frontend` — LEGACY_IDE_UI

- **package.json**: present. `name: reasonscript-playground`,
  `private: true`. Scripts: `dev` (vite), `build` (vite build), `preview`.
- **Stack**: React 18, JSX (no TypeScript), Vite 5, Monaco Editor.
  No Tauri dependency — browser-only.
- **Components** (30, all `.jsx`): `App.jsx` (root, ~holds all state and API
  calls), `BaselinePanel`, `CalculationPanel`, `ComplexityPanel`, `Console`,
  `CyclePanel`, `DependencyGraphPanel`, `DeterminismPanel`,
  `DiagnosticsPanel`, `DiffPanel`, `ExecutionPlanPanel`,
  `ExhaustivenessPanel`, `ExportPanel`, `InputStatePanel`, `JsonViewer`,
  `KnowledgePanel`, `LanguageAuditPanel`, `OutputPanel`, `OwnershipPanel`,
  `PipelineOverviewPanel`, `ProjectionSummaryPanel`, `QualityDashboard`,
  `RegressionRunner`, `RuntimeOperationsPanel`, `RuntimeTracePanel`,
  `SimulationPanel`, `StrictDiagnosticsPanel`, `TabPanel`, `Toolbar`,
  `TypeCoveragePanel`, `ValidationExplorer`, `WorkspaceExplorer`.
- **API usage** (`App.jsx`, dedicated per-feature endpoints): `/api/analyze`,
  `/api/workspace/list` (x2), `/api/workspace/read`, `/api/workspace/save`,
  `/api/validate`, `/api/run-all`, `/api/pipeline`, `/api/export`,
  `/api/import`, `/api/diff`, `/api/baseline`, `/api/language-audit`,
  `/api/language-audit/export`, `/api/examples`.
- **Vite config**: `playground/frontend/vite.config.js` present.
- **Wired into**:
  - `scripts/dev.py`: `cmd_setup` (`npm install`), `cmd_frontend` (dev
    server, port 5173), `cmd_build` (`npm run build`), `cmd_test("smoke")`
    (build), `cmd_test("frontend")` (build) — this is the **only** frontend
    `scripts/dev.py` currently knows about.
  - `playground/start.sh`: launches this dev server alongside
    `playground/backend` on ports 8000/5173/5174.
  - `scripts/check_environment.py`: `playground/frontend` listed in
    `REQUIRED_PATHS`.
  - `scripts/test_platform.py`: also listed in `NPM_PROJECTS` (parity with
    the official UI in that runner).
  - Docs: `docs/development/editor_state_contract.md` (describes
    `App.jsx` as the canonical state implementation), `commands.md`,
    `test_matrix.md`, `docs/specs/reasonscript_language_layer_v0_6_d.md`
    (`cd playground/frontend && npm run build`).
  - No direct pytest dependency — `tests/playground` and
    `playground_integration_tests` test `playground/backend`'s API surface,
    not this UI.

## 3. `frontend` — LANGUAGE_FRONTEND (out of scope, not a UI)

- **No `package.json`.** Confirmed pure Python package: `__init__.py`,
  `ast/`, `ast_validator/`, `compiler/`, `compiler_conformance/`,
  `compiler_fixtures/`, `conformance/`, `dto/` (Go, Rust, TypeScript
  bindings — data-transfer objects, not a UI), `fixtures/`, `ide/`,
  `language/`, `language_surface/`, `lsp/`, `parser/`,
  `parser_conformance/`, `parser_fixtures/`, `runtime_integration.py`,
  `schemas/`.
- **Role**: implements the ReasonScript compiler frontend — lexer, parser,
  AST, semantic analysis, Reason IR lowering, LSP server
  (`frontend.lsp`, used by the VSCode extension via
  `python3 -m frontend.lsp`), and cross-language DTO/schema definitions.
- **References**: extensively used throughout `docs/specifications/*.md`
  (AST/Compiler/Parser validation specs), `docs/reports/ide/*` (VSCode
  extension phase reports reference `frontend.lsp`, `frontend.compiler`,
  `frontend/runtime_integration.py`), `scripts/test_platform.py`
  (`mypy frontend toolchain sdk`, `frontend/parser_conformance`,
  `frontend/compiler_conformance` pytest groups), `scripts/check_environment.py`
  (`REQUIRED_PATHS` includes `frontend`).
- **Conclusion**: this directory shares a name with "IDE UI frontend" only by
  coincidence of the word "frontend" (compiler-frontend vs. UI-frontend).
  It must not be included in any deletion or consolidation plan for the IDE
  UI. No further action under Phase 4.5.

## Summary Table

| Path | package.json | Stack | Wired into scripts/dev.py | Wired into scripts/test_platform.py | Classification |
|---|---|---|---|---|---|
| `apps/reasonscript-ide/ui` | Yes | React/TS/Vite/Tauri | **No** | Yes | OFFICIAL_IDE_UI |
| `playground/frontend` | Yes | React/JSX/Vite | Yes (only frontend known to it) | Yes | LEGACY_IDE_UI |
| `frontend` | No | Python | N/A (not a UI) | Yes (as `mypy`/conformance target, not a UI) | LANGUAGE_FRONTEND |
