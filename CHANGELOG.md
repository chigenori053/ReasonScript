# Changelog

## Unreleased

### Added

- Implemented ReasonScript Phase RUO-N2 ReasonUnit Object Language and CLI
  Integration v1.0:
  - Added nested `reason_object` bindings for `model` and compatibility
    `module`, deterministic clause/source spans, static path and identity
    validation, stable `ReasonObjectBindingIR`, typed `ReasonObjectOperationIR`,
    and explicit capability/native-load/transaction/save execution-plan stages.
  - Added all 12 RUO opaque language types, 10 presence/failure states, and 16
    versioned `ruo.*` standard functions mapped to RUO-N1 native operations.
  - Added the consolidated `reason object` CLI, deterministic formatter,
    capability-gated native loading and atomic persistence, seven offline
    examples, 28 invalid cases, a project-owned schema, and all 56 canonical
    artifacts.
  - Recorded the additive RUO-N1 implementation-status normalization without
    changing any RUO-N1 historical canonical artifact.

### RUO-N2 Validation

- RUO-N2 matrix: 67/67 PASS; dedicated integration tests: 17 PASS.
- Focused RUO and language compatibility regression: 159 PASS.
- Native Rust tests: 5 passed; Clippy and rustfmt: PASS.
- `reason ci --json`: PASS, 1051 tests.
- Agent Protocol: PASS.

- Implemented ReasonScript Phase RUO-N1 Native ReasonUnit Object Runtime Type v1.0:
  - Added the safe-Rust `NativeReasonUnitRuntime` core with namespaced stable IDs,
    generation-checked handles, deterministic native registries, immutable
    concurrent-read snapshots, atomic optimistic transactions, native queries,
    resource lifecycle contracts, Tensor views, and explicit Runtime/Cluster
    projections.
  - Added native RUO-F1 loading and byte-preserving snapshot writing, the thin
    `reason reasonunit-runtime` CLI boundary, 21 fixture classes, 26 hostile and
    invalid cases, a project-owned artifact schema, and all 54 RUO-N1 canonical
    artifacts.
  - Validated RUO-N1-T001 through T074, three-run byte equality, zero unsafe
    blocks, reference/native parity, prerequisite preservation, and transition
    `PROCEED_TO_RUO-N2`.

### Validation

- Native Rust tests: 5 passed; Clippy and rustfmt: PASS.
- Earlier RUO focused regression: 126 passed.
- `reason ci --json`: PASS, 1034 tests.
- Agent Protocol: PASS.

- Implemented the Update Package Provenance and Freshness Verification
  Specification v0.1 (`reasonscript-update-package-manifest/1.0`):
  - `scripts/build_update_package.py` now records the source commit, dirty
    tree state, builder identity and hash, validation profile hash, and
    per-file payload hashes into a canonical
    `metadata/update_package_manifest.json` with a sidecar SHA-256, rejects
    release builds from dirty source trees, stages packages under
    `dist/.staging`, self-validates them with the install-side validator,
    and emits archive/manifest sidecar hashes.
  - `reason update` validates package provenance before staging or
    activation (INS-PROV-001..020 diagnostics), classifies package
    freshness (`fresh`/`stale`/`unknown`/`invalid`/`development`), rejects
    stale, dirty, development-class, and legacy (manifest-less) packages by
    default, and supports `--expected-commit`,
    `--allow-development-package`, and `--allow-legacy-package`.
  - Added `reason update package-inspect <archive>` and
    `reason update package-validate <archive>`.
  - Successful updates retain the package manifest and an installation
    record under `versions/<v>/metadata/`, write
    `reasonscript-update-transaction/1.1` artifacts under
    `metadata/transactions/`, and `reason install-info --json` reports the
    active package provenance; provenance survives rollback for every
    installed version.
  - Added `schemas/update_package_manifest.schema.json`
    (provenance manifest) and `schemas/update_transaction.schema.json`;
    the previous package-manifest schema moved to
    `schemas/install_manifest_v1_1.schema.json`.

### Changed

- Cleaned up repository documentation for the open-source release: removed
  internal validation reports, phase completion reports, and audit artifacts;
  added a documentation index at `docs/README.md`.

## ReasonScript Dynamic ReasonUnit Cluster Execution v0.1 - 2026-07-18

### Status

VALIDATED

### Added

- Added the optional Rust Dynamic ReasonUnit Runtime under
  `ClusterRuntime/src/dynamic`.
- Added deterministic Dynamic Unit Proposal validation and canonical
  ReasonUnit ID generation.
- Added duplicate proposal and duplicate ReasonUnit elimination.
- Added Coordinator-owned lifecycle management with terminal-state protection.
- Added atomic, checksummed Dynamic Plan Revisions at logical-step and epoch
  boundaries.
- Added dynamic dependency validation and cyclic dependency rejection.
- Added declared state access, state proposal validation, conflict detection,
  and Coordinator-owned shared-state commits.
- Added bounded branch management, global and branch budgets, pruning, and
  explicit budget termination.
- Added suspension, reactivation, replacement, retirement, and worker-failure
  reassignment.
- Added quiescence, state stability, convergence evaluation, and convergence
  reporting.
- Added the `reason cluster dynamic` plan, simulate, run, validate, compare,
  and test-model commands through a thin Python CLI adapter.
- Added nine Dynamic ReasonUnit JSON Schemas.
- Added nine canonical Dynamic ReasonUnit artifacts and offline replay
  validation.
- Added DRU-TM-001 through DRU-TM-013 and molecular scenario DRU-TM-MOL-001.

### Validation

- Rust integration tests: PASS.
- Dynamic and molecular acceptance scenarios: 14/14 PASS.
- Dynamic CLI tests: 2 PASS.
- Dynamic artifact validation: 9/9 PASS.
- `reason ci --json`: PASS, 879 tests.
- `reason agent-protocol --json`: PASS, AP-001 through AP-010.
- Canonical agent report: COMPLETED.

### Compatibility

- ReasonScript grammar is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Single-node Runtime behavior is unchanged.
- Static Cluster Runtime behavior is unchanged.
- Static Cluster Runtime canonical artifacts are unchanged.
- Python does not implement Dynamic Runtime semantics.

## ReasonScript Install Foundation v1.1 - 2026-07-14

### Added

- Added the cross-platform `reason update` CLI for package checks, local package updates, installed-state validation, and rollback.
- Added common install state, current-version, managed-file inventory, update-history, package checksum, and update-report contracts.
- Added deterministic version planning, SHA-256 verification, archive traversal protection, staging, version-directory installation, atomic activation, preservation, and rollback.
- Added macOS, Linux, and Windows Platform Adapter contracts plus a dependency-free native Rust activation helper.
- Added deterministic local update-package generation and bundled Phase 1R validation fixtures.

### Changed

- Updated ReasonScript from 0.5.0 to 0.5.1 so the update foundation ships as a distinct Release Unit.
- Updated clean installation to create v1.1 metadata while retaining the v1.0 root manifest and `current` compatibility entry.
- Updated the fixed launcher to resolve `metadata/current.json` and the active version's `bin/reason-runtime`.

### Validation

- Native updater unit test: PASS.
- Install/update regression tests: PASS.
- Installed `0.5.0 -> 0.5.1`, post-install validation, and explicit rollback lifecycle on macOS arm64: PASS.
- `reason ci --json`: PASS, 839 tests.
- Linux and Windows adapters are implemented and contract-tested; device validation remains pending.

## ReasonScript KDA-2 Component Validation v1.0

### Status

PROPOSED (specification); executed with result VALIDATED — see Execution Results below.

### Added

- Added the formal KDA-2 component-validation contract, Specification ID `reasonscript-kda2-component-validation/1.0`.
- Added installed-only Runtime provenance validation (KDA2-V1).
- Added Dataset, Feature, Rule, Prediction, Evidence, Evaluation, Knowledge, Visualization, Artifact, and Determinism validation phases (KDA2-V2 through KDA2-V13).
- Added `KDA2-CV-001` through `KDA2-CV-050`.
- Added explicit repository-wide CI failure classification (`kda2_related` / `unrelated` / `uncertain`).
- Added formal component-validation result and report contracts.

### Execution Results

- Acceptance criteria: 50 passed / 0 failed
- KDA-2 diagnostics: 0
- Determinism (full pipeline rerun, 416 files compared): PASS, 0 digest mismatches
- Installed-only import provenance: CONFIRMED, no `.deps` or core-repository source used
- KDA-1 regression, `reason doctor --json`, `reason install-validate --json`: PASS
- Repository-wide `./reason ci --json`: FAIL — `CI-008`, classified `unrelated`, does not block KDA-2 component status
- Final KDA-2 Component Status: **VALIDATED**

### Compatibility

- KDA-2 implementation semantics are unchanged.
- Titanic Rule Set v1.0 is unchanged.
- Data Foundation, VSL v0.1, and MLV v0.2 semantics are unchanged.
- Repository-wide certification remains separate from KDA-2 component validation.

## ReasonScript KDA-2 Titanic Rule-based Classification v1.0 Specification

### Status

VALIDATED (KDA-2 Component) — external consumer implementation exists; formal component validation executed and passed via `reasonscript-kda2-component-validation/1.0`.

### Added

- Added the initial formal specification for KDA-2 Titanic Rule-based Classification.
- Added Specification ID `reasonscript-kda2-titanic-rule-classification/1.0`.
- Defined the Dataset, Feature, Rule, Prediction, Decision Path, Evidence, Evaluation, Knowledge, Visualization, Artifact, Determinism, and Installed Distribution contracts.
- Added `KDA2-AC-001` through `KDA2-AC-050`.
- Defined strict installed-only Runtime provenance requirements.
- Separated KDA-2 component validation from repository-wide canonical CI reporting.
- Documented the external implementation and artifact location under the `kaggle-titanic-validation` project.

### Verified External Results

- Dataset rows: 891
- Feature records: 891
- Predictions: 891
- Prediction Evidence records: 891
- Accuracy: 0.7598204264870931
- Balanced accuracy: 0.777538107563992
- AUC: 0.8462755248777681
- Average precision: 0.7903496180334
- Knowledge records: 10
- Visualizations: 14
- Diagnostics: 0
- Repeated-run artifact digest equality: PASS
- KDA-1 regression: PASS

### Validation Status

- External KDA-2 implementation and artifacts: CONFIRMED
- Installed Distribution import provenance: CONFIRMED
- Formal KDA-2 component validation: PENDING
- Repository-wide canonical CI: FAIL — `CI-008 Test failure`
- Repository-wide failures are recorded separately and are not hidden.

### Compatibility

- No KDA-2 domain implementation was added to the ReasonScript Core repository.
- Data Analysis Foundation behavior is unchanged.
- Visualization Standard Library behavior is unchanged.
- ML Evaluation Visualization v0.2 behavior is unchanged.
- Reason IR, ExecutionPlan, Simulation, Knowledge, and Core CLI semantics are unchanged.

## Installed Distribution ML Evaluation v0.2 Correction

- Include the complete `runtime.visualization.evaluation` import closure and v0.2 schemas in installed-distribution validation.
- Record every ML Evaluation Python module in the install manifest under the `ml-evaluation-visualization-v0.2` component.
- Validate installed-only public API imports, repository isolation, Matplotlib-independent evaluation, JSON serialization, and canonical AUC/AP values.

## ReasonScript ML Evaluation Visualization Standard Library v0.2 - 2026-07-12

### Status

VALIDATED

### Added

- Added JSON-safe binary and multiclass classification evaluation models.
- Added confusion matrices, normalization, classification metrics, ROC/AUC, and precision–recall/AP.
- Added Rule coverage/accuracy, error distribution, Decision Path, confidence, and score visualizations.
- Added classification, metric, threshold, Rule, and Decision Path evidence.
- Added evaluation Visualization IR, Render Plan, JSON Schemas, Artifacts, and Manifest integration.
- Added installed external-project regressions.

### Compatibility

- Visualization v0.1 behavior remains unchanged and Matplotlib remains render-time optional.
- Evaluation and JSON Artifact generation require no Matplotlib.
- Data Foundation, Tensor functions, Reason IR, and non-visualization programs remain unchanged.

### Validation

- Binary and multiclass evaluation: PASS
- Confusion matrices, metrics, ROC/AUC, and precision–recall/AP: PASS
- Rule, Decision Path, error, confidence, and score evaluation: PASS
- PNG/SVG rendering and same-environment determinism: PASS
- Installed external-project regression: PASS
- Canonical `reason ci --json`: PASS (808 tests)

---

## ReasonScript Visualization Standard Library v0.1 - 2026-07-12

### Status

VALIDATED

### Added

- Added immutable backend-independent Visualization specifications under `runtime.visualization` (`visual.*`).
- Added basic and analytical chart constructors with Typed Table grouping, aggregation, correlation, and missingness.
- Added the optional Matplotlib reference backend with deterministic PNG/SVG rendering.
- Added Visualization IR, Render Plan, Evidence, Validation, JSON Schemas, and Artifact Manifest output.
- Added seven-chart Titanic and installed external-project regressions.

### Security and Resources

- Added project-root output confinement, path traversal rejection, explicit format and image limits, and lazy backend loading.

### Compatibility

- Matplotlib remains optional through `reasonscript[visualization]`; Core and Data Foundation behavior is unchanged when absent.

### Validation

- Basic and analytical chart contracts: PASS
- Matplotlib PNG/SVG rendering and same-environment determinism: PASS
- Titanic seven-chart regression and installed external-project rendering: PASS
- Canonical `reason ci --json`: PASS (804 tests)

---

## ReasonScript Data Analysis Public Result Serialization v1.0 - 2026-07-12

### Status

VALIDATED

### Added

- Added JSON-safe public data-analysis result envelopes and JSON Schemas.
- Added explicit public/internal Titanic analysis API separation.
- Added deterministic backend, table-summary, dataset, Knowledge, and Evidence serialization.
- Added optional `titanic_analysis_result.json` artifact support and serialization regressions.

### Fixed

- Fixed `analyze_titanic` leaking non-serializable `DataBackend` and `Table` instances.
- Fixed standard `json.dumps` persistence and public result determinism.

### Compatibility

- Titanic metrics, Knowledge count, and Data Analysis Foundation semantics remain unchanged.
- Runtime-context callers use `analyze_titanic_execution`.

### Validation

- Public result serialization, JSON Schema contract, and determinism: PASS
- Installed external-project Titanic regression: PASS
- Canonical `reason ci --json`: PASS (801 tests)

---

## ReasonScript Install Practical Validation Corrections v1.0 - 2026-07-11

### Status

VALIDATED

### Added

- Added `reason version-validate [--json]` and its version-validation schema.
- Added current release metadata consistency validation to canonical CI environment validation.
- Added package-identifier normalization and separate project name/identifier fields.
- Added project-configured artifact output resolution without requiring `--out`.
- Added atomic installed CLI smoke-state finalization and practical external-project regressions.

### Compatibility

- Explicit artifact `--out` remains supported and overrides project configuration.
- Existing projects are never rewritten implicitly.
- Runtime, parser, Reason IR, ExecutionPlan, Simulation, and Knowledge semantics are unchanged.

---

## ReasonScript Install Foundation v1.0 - 2026-07-11

### Status

VALIDATED

### Certification

- Repository validation: PASSED
- macOS local installation validation: PASSED
- Linux x86_64 release certification: PENDING CI runner validation
- Windows x86_64 release certification: PENDING CI runner validation

### Summary

ReasonScript Install Foundation v1.0 establishes the official installation,
environment validation, project initialization, manifest, integrity, and safe
uninstallation contracts for ReasonScript.

The foundation enables users and Coding Agents to install and validate
ReasonScript outside the source repository through a user-scoped installation
layout.

### Added

- Added `reason --version [--json]`.
- Added `reason doctor [--json]`.
- Added `reason install-info [--json]`.
- Added `reason install-validate [--json]`.
- Added `reason init <path> --template minimal`.
- Added macOS and Linux installation through `scripts/install.sh`.
- Added Windows installation through `scripts/install.ps1`.
- Added atomic version installation and activation.
- Added Install Manifest generation.
- Added SHA-256 file integrity records.
- Added source and `pipx` Python package entry points.
- Added Standard Library distribution resources.
- Added Install Foundation JSON Schemas.
- Added safe uninstall with dry-run and purge modes.
- Added platform-specific installation documentation.
- Added installation contract and end-to-end tests.

### Validation

- `reason ci --json`
  - PASSED
- Full test suite
  - 787 passed
- Golden Corpus
  - PASSED
- Phase 8 Golden
  - 6 scenarios passed
- Install Foundation tests
  - 4 passed
- Existing Toolchain conformance tests
  - 39 passed
- Temporary installation lifecycle
  - install: PASSED
  - CLI execution: PASSED
  - manifest validation: PASSED
  - uninstall: PASSED
  - residual file validation: PASSED

### Known Certification Gaps

- Linux x86_64 clean-runner release certification remains to be completed.
- Windows x86_64 clean-runner release certification remains to be completed.
- PyPI publication is not included in Install Foundation v1.0.
- Homebrew, winget, Scoop, Chocolatey, apt, and standalone binary distribution
  remain future distribution channels.

### Compatibility

- Existing repository-local `./reason` execution remains supported.
- Existing CLI behavior is preserved.
- Runtime semantics are unchanged.
- Parser semantics are unchanged.
- Existing Reason IR, ExecutionPlan, Simulation, Knowledge, and ReasoningModel
  contracts are unchanged.
- Optional ML and image-processing backends are not required for Core
  installation.

---

## ReasonScript IDE Phase 4-D - Cross-platform Policy, Tests, and Docs - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 4-D has been completed as the Cross-platform Policy,
Tests, and Docs phase.

This phase consolidates the Phase 4 cross-platform adapter foundation. It fixes
the browser-first policy, desktop stub policy, final `PlatformAdapter` contract,
path policy, workspace/artifact adapter policy, command/shortcut policy,
settings persistence policy, notification policy, and desktop shell deferred
policy.

Phase 4-D is a stabilization phase. Parser behavior, runtime behavior,
Reason IR semantics, `/api/analyze`, and `/api/workspace/*` contracts remain
unchanged.

### Added

- Added Phase 4-D policy documentation:
  - `phase4_cross_platform_foundation.md`
  - `browser_desktop_boundary.md`
  - `platform_adapter_final_contract.md`
  - `phase4_policy_index.md`
  - `desktop_shell_deferred_policy.md`
- Added Phase 4 final policy index.
- Added Desktop Shell deferred policy.
- Added Phase 4-D integration tests:
  - platform foundation contract
  - no direct platform leakage
  - browser / desktop boundary
  - required policy docs

### Changed

- Clarified that `BrowserPlatformAdapter` is the official Phase 4 runtime
  target.
- Clarified that `DesktopPlatformAdapter` is only a future replacement point.
- Updated `DesktopPlatformAdapter` capability flags so native dialogs, native
  menus, local filesystem shell integration, and local process execution are not
  exposed in Phase 4-D.
- Clarified that desktop workspace and artifact operations return
  `PlatformErrorKind=unsupported` until a desktop shell provides real
  implementations.
- Updated existing platform adapter contract documentation.
- Updated changelog for Phase 4-D.

### Fixed

- Fixed Phase 4 policy boundary across:
  - `PlatformAdapter`
  - `WorkspaceAdapter`
  - `ArtifactAdapter`
  - `CommandAdapter`
  - `SettingsAdapter`
  - `NotificationAdapter`
- Fixed `NormalizedRelativePath` as the UI file identity policy.
- Fixed analyze-result backed `ArtifactAdapter` as the Phase 4 artifact policy.
- Fixed command-oriented shortcuts as the Phase 4 shortcut policy.
- Fixed Desktop Shell as deferred beyond Phase 4.

### Compatibility

- Existing Playground-first behavior is preserved.
- Phase 3 workspace editing behavior is preserved.
- Phase 3.5 standard layout behavior is preserved.
- Phase 4-A/B/C adapter behavior is preserved.
- `/api/analyze` contract is unchanged.
- `/api/workspace/list` contract is unchanged.
- `/api/workspace/read` contract is unchanged.
- `/api/workspace/save` contract is unchanged.
- Runtime semantics are unchanged.
- Parser behavior is unchanged.
- Desktop shell remains deferred.

### Validation

- `python3 -m pytest tests/ide/test_phase4_*.py -v --tb=short`
  - 23 passed
- `python3 -m pytest tests/ide -v --tb=short`
  - 141 passed
- `npm run build`
  - passed
- `python3 scripts/dev.py test ide`
  - 161 passed
- `python3 scripts/dev.py test smoke`
  - passed
- `python3 scripts/dev.py test backend`
  - 33 passed
- `git diff --check`
  - passed

---

## ReasonScript IDE Phase 4 - Cross-platform UI / Platform Adapter Foundation - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 4 has been completed as the Cross-platform UI /
Platform Adapter Foundation.

This phase prepares the Playground-first IDE for future macOS, Windows, and
Linux desktop shell support by separating UI behavior from browser, desktop,
and OS-specific concerns.

Phase 4 does not implement the desktop shell. It establishes the adapter
architecture required for future desktop integration.

### Included Sub-phases

- Phase 4-A: Platform Adapter Core
- Phase 4-B: Workspace & Artifact Adapter Migration
- Phase 4-C: Command / Settings / Notification Adapter
- Phase 4-D: Cross-platform Policy, Tests, and Docs

### Added

- Added `PlatformAdapter`.
- Added `BrowserPlatformAdapter`.
- Added `DesktopPlatformAdapter` stub.
- Added `WorkspaceAdapter` operational boundary.
- Added `ArtifactAdapter` operational boundary.
- Added `CommandAdapter` and `CommandRegistry`.
- Added `SettingsAdapter` persistence.
- Added `NotificationAdapter`.
- Added `PlatformError` model.
- Added `NormalizedRelativePath` validation.
- Added command-oriented shortcut policy.
- Added browser / desktop boundary documentation.
- Added Desktop Shell deferred policy.
- Added Phase 4 integration tests.

### Final Architecture

```txt
UI Components
  -> CommandRegistry / UI State
  -> PlatformAdapter
      -> WorkspaceAdapter
      -> ArtifactAdapter
      -> CommandAdapter
      -> SettingsAdapter
      -> NotificationAdapter
  -> BrowserPlatformAdapter or future DesktopPlatformAdapter
```

### Final Policy

- `BrowserPlatformAdapter` is the official Phase 4 runtime target.
- `DesktopPlatformAdapter` is a future replacement point only.
- Desktop Shell implementation is deferred.
- UI file identity uses `NormalizedRelativePath`.
- Workspace operations go through `PlatformAdapter.workspace`.
- Artifact operations go through `PlatformAdapter.artifacts`.
- IDE actions are command-oriented through `IdeCommand`.
- Settings persist through `SettingsAdapter`.
- User-visible messages go through `NotificationAdapter`.
- Unsupported desktop operations return `PlatformErrorKind=unsupported`.

### Compatibility

- Existing Playground-first workflow is preserved.
- Existing workspace editing behavior is preserved.
- Existing standard IDE layout behavior is preserved.
- `/api/analyze` contract is unchanged.
- `/api/workspace/list` contract is unchanged.
- `/api/workspace/read` contract is unchanged.
- `/api/workspace/save` contract is unchanged.
- Runtime semantics are unchanged.
- Parser behavior is unchanged.
- Desktop shell remains deferred.

### Validation

- Phase 4-D focused tests passed.
- Full `tests/ide` passed.
- UI build passed.
- Official IDE tests passed.
- Smoke tests passed.
- Backend tests passed.
- `git diff --check` passed.

---

## ReasonScript IDE Phase 4-C - Command / Settings / Notification Adapter - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 4-C has been completed as the Command / Settings /
Notification Adapter phase.

This phase adds a command-oriented action boundary for IDE operations,
introduces persistent browser settings through `SettingsAdapter`, and routes
user-visible messages through `NotificationAdapter`.

Top Bar actions, panel switching, and keyboard shortcut readiness now share the
same `IdeCommand` surface. This prepares the Playground-first IDE for future
desktop menu and OS-specific shortcut integration.

### Added

- Added expanded `IdeCommand` surface:
  - `openWorkspace`
  - `refreshWorkspace`
  - `saveFile`
  - `analyzeFile`
  - `runCurrentFile`
  - `validateWorkspace`
  - `auditProject`
  - `showOverview`
  - `showPlan`
  - `showSimulation`
  - `showKnowledge`
  - `showArtifacts`
  - `showProblems`
  - `showOutput`
  - `showLogs`
  - `showTests`
  - `clearOutput`
  - `clearNotifications`
- Added `CommandRequest`.
- Added `CommandResult`.
- Added `CommandRegistry`.
- Added shortcut binding table.
- Added command-oriented Top Bar actions.
- Added command-oriented Right Inspector tab switching.
- Added command-oriented Bottom Tool Window tab switching.
- Added browser `SettingsAdapter` persistence using `localStorage` with memory
  fallback.
- Added persistence for:
  - `compilerMode`
  - `rightInspector.activeTab`
  - `bottomToolWindow.activeTab`
- Added `NotificationAdapter` metadata support:
  - `title`
  - `operation`
  - `details`
  - `durationMs`
- Added `PlatformError` to notification severity mapping.
- Added Phase 4-C documentation and contract tests.

### Changed

- Save now routes through the `saveFile` command.
- Analyze now routes through the `analyzeFile` command.
- Run now routes through the `runCurrentFile` command.
- Validate now routes through the `validateWorkspace` command.
- Audit now routes through the `auditProject` command.
- Right Inspector tab selection now routes through command names.
- Bottom Tool Window tab selection now routes through command names.
- Browser settings now use `localStorage` with memory fallback.

### Keyboard Shortcut Policy

Shortcuts bind to `IdeCommand` names, not directly to UI handlers.

Initial bindings:

| Command | macOS | Windows | Linux |
| --- | --- | --- | --- |
| `saveFile` | `Cmd+S` | `Ctrl+S` | `Ctrl+S` |
| `analyzeFile` | `Cmd+Enter` | `Ctrl+Enter` | `Ctrl+Enter` |
| `showProblems` | `Cmd+Shift+M` | `Ctrl+Shift+M` | `Ctrl+Shift+M` |

Full OS-level shortcut binding remains outside Phase 4-C.

### Notification Policy

Notifications are platform-bound user messages with three levels:

- `info`
- `warning`
- `error`

Browser Phase 4-C uses console fallback notifications. Desktop native
notifications are deferred to the desktop shell phase.

### Compatibility

- Existing Playground behavior is preserved.
- Phase 4-B workspace/artifact adapter behavior is preserved.
- `/api/analyze` contract is unchanged.
- `/api/workspace/list` contract is unchanged.
- `/api/workspace/read` contract is unchanged.
- `/api/workspace/save` contract is unchanged.
- Runtime semantics are unchanged.
- Desktop shell remains deferred.

### Validation

- `npm run build`
- `python3 -m pytest tests/ide/test_command_adapter_contract.py tests/ide/test_command_registry.py tests/ide/test_settings_adapter_contract.py tests/ide/test_notification_adapter_contract.py tests/ide/test_shortcut_command_mapping.py -v --tb=short`
- `python3 scripts/dev.py test ide`
- `python3 scripts/dev.py test smoke`
- `python3 scripts/dev.py test backend`
- `git diff --check`

All validation commands passed.

---

## ReasonScript IDE Phase 4-B - Workspace & Artifact Adapter Migration - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 4-B has been completed as the Workspace & Artifact
Adapter Migration phase.

This phase moves workspace list/read/save operations and artifact access behind
the `PlatformAdapter` boundary introduced in Phase 4-A. The browser
implementation continues to use the existing backend contracts, while UI
components no longer directly depend on workspace endpoints.

The phase also adds file-backed analyze path validation, analyze-result backed
artifact access, `PlatformError` mapping, and adapter path enforcement.

### Added

- Added operational `BrowserWorkspaceAdapter` support for workspace list,
  workspace file read, and workspace file save.
- Added analyze-result backed `BrowserArtifactAdapter`.
- Added artifact descriptors for `ast.json`, `semantic_ast.json`,
  `reason_ir.json`, `execution_plan.json`, `simulation.json`, `knowledge.json`,
  `diagnostics.json`, and `validation.json`.
- Added `PlatformError` mapping for workspace and artifact operations.
- Added path enforcement for workspace read/save and file-backed analyze.
- Added Phase 4-B documentation.
- Added Phase 4-B contract tests.

### Changed

- Moved workspace open/refresh through
  `PlatformAdapter.workspace.listWorkspace`.
- Moved file selection through `PlatformAdapter.workspace.readFile`.
- Moved save workflow through `PlatformAdapter.workspace.saveFile`.
- Removed direct bridge dependency from `WorkspaceExplorerView`.
- Moved Artifacts tab access through `PlatformAdapter.artifacts`.
- Added pre-validation for `source_context.relative_path` before file-backed
  analyze.
- Kept raw analyze response available through the fallback `All Raw` view.

### Platform Error Mapping

Workspace backend mappings:

| Backend code | PlatformErrorKind |
| --- | --- |
| `NOT_FOUND` | `missing` |
| `PATH_TRAVERSAL` | `path_traversal` |
| `PERMISSION_DENIED` | `permission_denied` |
| `DECODE_ERROR` | `invalid_encoding` |
| `INVALID_ENCODING` | `invalid_encoding` |
| `VERSION_CONFLICT` | `conflict` |
| `READ_ONLY` | `read_only` |

HTTP mappings:

| HTTP status | PlatformErrorKind |
| --- | --- |
| `404` | `missing` |
| `409` | `conflict` |
| other non-2xx | `network_error` |

Thrown fetch failures are returned as `network_error`. Unsupported desktop stub
operations return `unsupported`.

### Compatibility

- Existing Playground-first behavior is preserved.
- Phase 3 workspace editing behavior is preserved.
- Phase 3.5 standard layout behavior is preserved.
- `/api/analyze` contract is unchanged.
- `/api/workspace/list` contract is unchanged.
- `/api/workspace/read` contract is unchanged.
- `/api/workspace/save` contract is unchanged.
- Temporary source analyze mode remains supported.
- Desktop shell remains deferred.

### Validation

- `npm run build`
- `python3 -m pytest tests/ide/test_workspace_adapter_migration.py tests/ide/test_artifact_adapter_migration.py tests/ide/test_adapter_path_enforcement.py tests/ide/test_workspace_adapter_error_mapping.py -v --tb=short`
- `python3 scripts/dev.py test ide`
- `python3 scripts/dev.py test smoke`
- `python3 scripts/dev.py test backend`

All validation commands passed.

---

## ReasonScript IDE Phase 4-A - Platform Adapter Core - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 4-A defines the Platform Adapter Core.

This phase introduces the minimum adapter layer required to prepare the
Playground-first IDE UI for future macOS, Windows, and Linux desktop support.
It does not implement a native desktop shell.

### Added

- Added `apps/reasonscript-ide/ui/src/platform/types.ts`.
- Added `PlatformAdapter`, `PlatformEnvironment`, `PlatformErrorKind`,
  `PlatformError`, and `NormalizedRelativePath`.
- Added minimal workspace, artifact, command, settings, and notification
  sub-adapter interfaces.
- Added `BrowserPlatformAdapter`.
- Added `DesktopPlatformAdapter` stub.
- Added active adapter resolver through `getPlatformAdapter()`.
- Added slash-normalized relative path validation.
- Added explicit unsupported operation error policy.
- Added Phase 4-A platform adapter tests and documentation.

### Non-Goals

- No Desktop shell implementation.
- No native file dialogs.
- No native menus.
- No packaging or installer work.
- No terminal emulator.
- No LSP integration.
- No runtime semantic changes.
- No `/api/analyze` contract changes.
- No workspace API contract changes.

### Compatibility

- Existing Playground workflow remains unchanged.
- Existing Phase 3 workspace editing behavior remains unchanged.
- Existing Phase 3.5 standard layout remains unchanged.
- Desktop support remains deferred.

---

## ReasonScript IDE Phase 3.5 - Standard IDE Layout Simplification - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 3.5 has been completed as the Standard IDE Layout
Simplification phase.

This phase reorganizes the Playground-first IDE into a simpler Android
Studio-style layout with five major regions: Top Bar, Left Project Pane, Center
Editor, Right Inspector, and Bottom Tool Window.

The overloaded right-pane tab structure has been reduced to five primary tabs:
Overview, Plan, Simulation, Knowledge, and Artifacts. Operational feedback has
been moved into a Bottom Tool Window with Problems, Output, Logs, and Tests
tabs.

### Added

- Added Standard IDE Layout v0.2 implementation.
- Added Top Bar with Project, File, Mode, Validate, Run, Analyze, Audit, and
  Status.
- Added simplified Right Inspector tabs:
  - Overview
  - Plan
  - Simulation
  - Knowledge
  - Artifacts
- Added Bottom Tool Window tabs:
  - Problems
  - Output
  - Logs
  - Tests
- Added `StandardLayoutViews.tsx`.
- Added Phase 3.5 layout contract tests.
- Added Phase 3.5 development documentation:
  - `standard_ide_layout.md`
  - bottom tool window contract
  - cross-platform UI readiness
  - layout migration map

### Changed

- Consolidated Pipeline and Summary into Overview.
- Moved detailed diagnostics to Bottom Problems.
- Moved runtime output to Bottom Output.
- Moved AST, Semantic AST, Reason IR, Validation, and Raw JSON into Artifacts.
- Moved ExecutionPlan into Plan.
- Moved Simulation, Runtime, Input, and Trace information into Simulation.
- Moved Knowledge and evidence information into Knowledge.
- Reclassified Diff, Regression, Baseline, and related outputs toward Bottom
  Tests or future Audit sections.
- Preserved existing functionality through relocation, grouping, and collapsible
  detail sections.

### Cross-platform Readiness

- The five-region layout is compatible with browser and future desktop shell
  embedding.
- UI logic does not depend on OS-specific path separators.
- `relative_path` values are treated as slash-normalized display paths.
- Keyboard shortcuts remain command-oriented for future desktop menu bindings.
- Right Inspector and Bottom Tool Window are compatible with future resizable
  panes.
- Native menus, native file dialogs, packaging, and installers remain outside
  Phase 3.5.

### Validation

- `python3 scripts/dev.py test ide`
  - 104 passed
- `python3 -m pytest tests/ide/test_standard_layout_contract.py -v --tb=short`
  - 4 passed
- `npm run build` in `apps/reasonscript-ide/ui`
  - passed

### Compatibility

- Parser behavior is unchanged.
- Runtime behavior is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- `/api/analyze` contract is unchanged.
- Workspace list/read/save contracts are unchanged.
- Phase 3 workspace editing behavior is unchanged.
- Phase 3.5 changes are UI layout and information architecture changes only.

---

## ReasonScript IDE Phase 3 - Local Workspace Editing Foundation - 2026-07-01

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 3 defines the Local Workspace Editing Foundation.

This phase extends the Playground-first IDE from temporary source editing
to workspace file-based development. It introduces selected file state,
editor binding, dirty state tracking, save workflow, analyze-current-file
workflow, per-file diagnostics, and per-file artifact identity. Runtime and
compiler semantics are unchanged — Phase 3 only changes how source text
reaches `/api/analyze`.

### Scope

- Workspace file selection
- Source editor binding
- File read / save
- Dirty state tracking
- Analyze selected file
- Per-file analyze result binding
- Per-file diagnostics
- Per-file artifact identity
- Missing file handling
- Path traversal protection
- Workspace editing documentation
- Workspace editing contract tests

### Non-Goals

- Desktop IDE full implementation
- Terminal emulator
- Full LSP integration
- Multi-file semantic linking
- Package manager
- Git integration
- Advanced runtime replay
- Cloud workspace

### Added

- Added `playground/backend/workspace.py`: workspace scan, read, save, and
  path-safety helpers.
- Added `POST /api/workspace/list` (also serves workspace refresh).
- Added `POST /api/workspace/read`.
- Added `POST /api/workspace/save`.
- Added optional `source_context` field to the `/api/analyze` request
  (`workspace_root`, `relative_path`, `dirty`) — omitting it preserves the
  exact Phase 2 behavior.
- Added `source_context` (with a deterministic `artifact_id`) to the
  `/api/analyze` response when a workspace file was analyzed.
- Added `relative_path` stamping on diagnostics when `source_context` is
  present.
- Added best-effort per-file artifact persistence under
  `<workspace_root>/.reasonscript/artifacts/<artifact_id>/`, reusing the
  existing Phase 2 artifact file names.
- Added `WorkspaceExplorer` sidebar to the Playground frontend: open a
  workspace root, browse the file tree, select a `.rsn`/`.reason` file.
- Added file-aware Source Editor: selected-file header (filename, dirty
  indicator, read-only/missing/stale badges), Save action, and a
  file-bound Analyze action.
- Added per-file analyze result cache in the frontend so switching files
  restores that file's last analyze result.
- Added Phase 3 development documentation:
  `workspace_editing_foundation.md`, `file_operation_contract.md`,
  `editor_state_contract.md`, `per_file_artifact_contract.md`,
  `per_file_diagnostics_contract.md`.
- Added workspace contract tests under `tests/ide/`.

### Required File Operations

- `list_workspace_files` — `POST /api/workspace/list`
- `read_workspace_file` — `POST /api/workspace/read`
- `save_workspace_file` — `POST /api/workspace/save`
- `refresh_workspace` — re-invoke `POST /api/workspace/list`
- `select_workspace_file` — frontend-only state; no backend endpoint (the
  backend is stateless per-request)

### Source File Extensions

- `.rsn` as preferred ReasonScript source extension
- `.reason` as optional compatibility extension

### Analyze Request Extension

`POST /api/analyze` may include optional `source_context`:

```json
{
  "source": "model Test {}",
  "compiler_mode": "default",
  "source_context": {
    "workspace_root": "/path/to/project",
    "relative_path": "examples/test.rsn",
    "dirty": false
  }
}
```

### Artifact Identity

Per-file artifacts use a deterministic source-path hash:

```
.reasonscript/artifacts/<artifact_id>/
```

where `artifact_id = sha256(relative_path)[:16]`. Required artifact names
remain unchanged: `ast.json`, `semantic_ast.json`, `reason_ir.json`,
`execution_plan.json`, `simulation.json`, `knowledge.json`,
`diagnostics.json`, `validation.json`.

### Acceptance Criteria

- Workspace file tree can select ReasonScript source files.
- Selected file content loads into Source Editor.
- Dirty state is tracked.
- Selected file can be saved.
- Path traversal is rejected.
- Selected file can be analyzed through `/api/analyze`.
- Analyze result is bound to selected file.
- Runtime panels display selected file analyze result.
- Diagnostics are associated with selected file.
- Missing selected file does not crash the IDE.
- Artifact identity is deterministic per file.
- Temporary source analyze mode remains supported.

### Validation

```
python3 scripts/dev.py test ide
python3 scripts/dev.py test backend
python3 scripts/dev.py test smoke
npm run build (playground/frontend)
```

### Compatibility

- Parser behavior is unchanged.
- Runtime behavior is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- `/api/analyze` remains backward compatible with the Phase 2 request
  shape.
- `source_context` is optional.
- Temporary source analyze mode remains supported.

---

## ReasonScript IDE Phase 2 - Playground-first IDE Runtime Integration - 2026-06-29

### Status

VALIDATED

### Summary

ReasonScript IDE Phase 2 has been completed as the official
Playground-first Runtime Integration layer.

The Playground IDE now treats `POST /api/analyze` as the primary contract
endpoint for Source -> Surface AST -> Semantic AST -> Reason IR ->
ExecutionPlan -> Simulation -> Knowledge -> Diagnostics inspection.

The analyze response now returns a deterministic payload containing pipeline
status, runtime artifacts, structured view data, diagnostics, and compiler
mode.

### Added

- Added stabilized `/api/analyze` response contract.
- Added fixed pipeline stage ids:
  - `source`
  - `surface_ast`
  - `semantic_ast`
  - `reason_ir`
  - `execution_plan`
  - `simulation`
  - `knowledge`
  - `diagnostics`
- Added fixed stage status values:
  - `success`
  - `warning`
  - `error`
  - `skipped`
  - `unavailable`
- Added artifact state handling.
- Added diagnostics-to-pipeline stage mapping.
- Added Pipeline Overview tab to the Playground frontend.
- Added shared analyze result state for runtime artifact display.
- Added structured display integration for ExecutionPlan, Simulation,
  Knowledge, Diagnostics, and Runtime IO.
- Added Desktop-compatible ViewModel status updates.
- Added Phase 2 development documentation.
- Added `/api/analyze` contract test.

### Fixed

- Stabilized missing artifact handling.
- Ensured missing artifacts render as empty, skipped, or unavailable states.
- Prevented missing artifacts from crashing the IDE.
- Normalized diagnostic severity to `error`, `warning`, or `info`.
- Classified unknown diagnostics under the `diagnostics` stage.

### Analyze API Contract

`POST /api/analyze` accepts:

```json
{
  "source": "module Test { calculation Value { result = 42 } }",
  "compiler_mode": "default"
}
```

The response contains:

```json
{
  "ok": true,
  "compiler_mode": "default",
  "pipeline": {
    "stages": []
  },
  "artifacts": {},
  "views": {},
  "diagnostics": []
}
```

Required pipeline stages:

- `source`
- `surface_ast`
- `semantic_ast`
- `reason_ir`
- `execution_plan`
- `simulation`
- `knowledge`
- `diagnostics`

Required artifact names:

- `ast.json`
- `semantic_ast.json`
- `reason_ir.json`
- `execution_plan.json`
- `simulation.json`
- `knowledge.json`
- `diagnostics.json`
- `validation.json`

Every diagnostic returned by `/api/analyze` includes `code`, `message`,
`severity`, `stage`, and `source_range`. Unknown diagnostics are classified
under the `diagnostics` stage.

### Validation

- `python3 scripts/dev.py test smoke`
- `python3 scripts/dev.py test backend`
- `python3 scripts/dev.py test ide`
- `npm run build` in `playground/frontend`
- `npm run build` in `apps/reasonscript-ide/ui`

All validation commands passed.

### Compatibility

- Parser behavior is unchanged.
- Runtime behavior is unchanged.
- Reason IR semantics are unchanged.
- ExecutionPlan semantics are unchanged.
- Simulation semantics are unchanged.
- Knowledge semantics are unchanged.
- Phase 2 only stabilizes Playground IDE runtime integration.

### Positioning

```text
Phase 1:
  Development Environment
  Status: VALIDATED

Phase 2:
  Playground-first IDE Runtime Integration
  Status: VALIDATED

Next:
  Phase 3 candidate selection
```

## ReasonScript Language Layer v0.6-D - 2026-06-29

### Added

- Added Human Surface top-level construct policy.
- Defined `model` as active preferred syntax.
- Defined `module` as active compatibility syntax.
- Reserved `world` for WorldModel / simulation-domain syntax.
- Reserved `system` for multi-model orchestration syntax.
- Reserved `component` for UI / SDK structural composition syntax.
- Added reserved top-level construct diagnostic policy.

### Fixed

- Clarified that reserved top-level constructs must not silently parse as `model` or `module`.
- Clarified that `source_kind` remains L1/L7 metadata unless a future specification defines distinct core semantics.
- Preserved module/model L3-L6 equivalence guarantees from v0.6-B.

### Validation

- model active preferred syntax policy verified.
- module active compatibility syntax policy verified.
- reserved construct diagnostics verified.
- module/model core non-regression verified.
- top-level construct projection policy verified.
- Playground frontend build verified.

## ReasonScript Language Layer v0.6-C - 2026-06-29

### Added

- Added L7 Developer Projection support for `source_kind`.
- Added Playground Summary View presentation for `model` and `module`.
- Displayed `model` as preferred Human Surface syntax.
- Displayed `module` as compatibility syntax.
- Displayed normalized ReasonGraph target for top-level constructs.
- Added Diagnostics View support for `diagnostics.json`.

### Fixed

- Clarified that source spelling differences are projection metadata, not Reason IR semantics.
- Prevented Developer Projection from implying different core semantics for `module` and `model`.

### Validation

- Source kind projection verified.
- model preferred syntax projection verified.
- module compatibility syntax projection verified.
- Diagnostics artifact consumption verified.
- L3-L6 non-regression verified.
- Playground frontend build verified.

## ReasonScript Language Layer v0.6-B - 2026-06-28

### Added

- Accepted `model Example { ... }` as a top-level Human Surface alias.
- Added `source_kind` to Surface AST to preserve original top-level spelling.
- Added module/model equivalence validation across Reason IR, ExecutionPlan,
  Simulation, and Knowledge.
- Added `diagnostics.json` to Playground pipeline artifact export.

### Fixed

- Clarified that Human Surface spelling must not affect Reason IR semantics.
- Strengthened CI/CD coverage for Language Layer artifact consistency.

### Validation

- Surface AST source_kind distinction verified.
- Reason IR equivalence verified.
- ExecutionPlan equivalence verified.
- Simulation and Knowledge equivalence verified.
- Playground artifact contract verified.

## reasonscript-language-surface/0.5 - 2026-06-28

ReasonScript Language Surface v0.5 feature freeze.

### Frozen Surface

- Module system, declarations, type system, expressions, and statements
- Literal, enum, optional, struct, nested struct, guard, OR, and range patterns
- Source -> Surface AST -> Semantic AST -> Reason IR -> ExecutionPlan ->
  Simulation -> Knowledge pipeline
- Pattern Identity, canonical path generation, and branch evidence propagation

### Fixed Interfaces

- `reasonscript-language-surface/0.5`
- `parser/0.5`
- `reasonscript-ast/0.5`
- `reason-ir/0.5`
- `execution-plan/0.5`

### Compatibility Policy

- `0.5.x` releases may include bug fixes, diagnostics, compiler optimizations,
  and performance improvements.
- Syntax, semantic meaning, IR schema, canonical path generation, and Pattern
  Identity are frozen for the v0.5 line.
- New language features are deferred to v0.6.

## reasonscript-semantic-language/0.2 - 2026-06-15

ReasonScript Semantic Language v0.2 Core freeze.

### Frozen Core

- SemanticUnit and the seven adopted SemanticUnit types
- SemanticRelation and the eight core relation types
- SCV-1 structural validation
- Reasoning Space and SemanticPlan
- deterministic SemanticSimulation and SimulationResult
- validated Knowledge emergence with complete evidence

### Guarantees

- deterministic reasoning for identical graph, plan, and constraints
- SCV-1 enforcement throughout the reasoning pipeline
- immutable Reasoning Space during simulation
- trace, evidence, and confidence preservation
- reproducible SimulationResult and Knowledge JSON

### Out of Scope

- SCV-2 through SCV-5
- Knowledge repositories, persistence, retrieval, and re-reasoning
- MemorySpace, WorldModel, natural language parsing, and external execution

## reasonscript-language-surface/0.1 - 2026-06-14

ReasonScript Language Surface v0.1 release.

### Released

- Deterministic Source -> Surface AST -> Semantic AST -> Reason IR ->
  ExecutionPlan pipeline
- Module namespaces, imports, aliases, visibility, and qualified names
- Declarations, relations, expressions, patterns, statements, and Calculations
- Primitive and Reason State type annotations as validation contracts
- Canonical `node_type` serialization and round-trip compatibility
- Fixed AST, expression, pattern, statement, Calculation, type, and namespace
  validation families

### Fixed Interfaces

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`
- `reasonscript-calculation-semantics/0.1`

## 0.1.0-alpha - 2026-06-13

First integrated ReasonScript Platform alpha release.

### Added

- State-first layered Hybrid Runtime and transaction model
- Versioned `reason-ir/0.1` JSON ABI
- Common DTO declarations for Rust, Python, TypeScript, Go, and Java
- Five-layer platform conformance framework
- Versioned `reasonscript-ast/0.1` semantic AST ABI
- Deterministic `parser/0.1` Source-to-AST contract
- Deterministic `compiler/0.1` AST-to-Reason-IR contract
- End-to-end Source -> AST -> Reason IR -> Runtime validation

### Fixed Interfaces

- `reason-ir/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `transaction/0.1`
- `common-dto/0.1`
- `conformance-framework/0.1`

### Known Limitations

- The user-facing syntax remains experimental.
- Macros, language server, formatter, optimizer, distributed Runtime,
  persistence, and event sourcing are not included.
- Go conformance was not executed in the release environment because the Go
  toolchain was unavailable.
- Java DTO declarations compile, but a Java JSON codec adapter is not included.
- Full five-language SDK compatibility certification is not granted.
# Install Distribution Completeness v1.0

## Added

- Added the Playground backend and complete runtime import closure to the required distribution.
- Added repository-independent installed CLI and generated-project E2E validation.
- Added complete component inventory, entry-point integrity records, and project-name normalization.

## Fixed

- Fixed installed `reason check` failing with `ModuleNotFoundError: playground`.
- Fixed install validation accepting incomplete or repository-dependent distributions.
- Fixed relative source and artifact paths resolving against the installed distribution root.
