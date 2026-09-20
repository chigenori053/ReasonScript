# ReasonScript Lightweight RUS R4 — Main Integration Report

Verification record for the "Lightweight RUS R4 Main Integration / Merge Specification v0.1".
Section numbers (§) refer to that specification.

**Determination at verification: MERGE_READY** — correctness, compatibility, determinism,
replay, performance, and clean tree pass, and every runtime-related CI check passes. The one
failing CI check (Lint) fails identically on `main` before this integration (see below).
`main` is then advanced to the tip of `integration/lightweight-rus-r4` without squashing, so
the merge commit and the R4 history stay in `main`.

## Commits

| Role | Commit |
| --- | --- |
| `main` at merge start (`merge_base_main_sha`) | `e5c82679bf37230ef7593201c8298b4d8d2ff4e4` |
| Lightweight RUS baseline (R0) | `111f199a290292e2108d629742d7a1456c1fdc5e` |
| R4 implementation | `6627ad6442e6d4db7e4273b44346ad990d83e3e2` |
| Formal R4 benchmark artifacts | `70c2895828079214ce2f5ddb11e7975f4dd0b79e` |
| Merge commit (non-squash, `--no-ff`) | `7054afe5d4eef20baac3ae585bcf5bced7cc2fb2` |
| Verified head (merge + verification tooling) | `7b9ec5736d0a4996b4cd741265a5ca49818be26c` |

`main` was an ancestor of the R4 branch, so there were no conflicts and the merge tree is
identical to the R4 tip. The only additions on top of the merge are the verification
tooling and tests (no runtime code change). Verification ran on a clean tree
(`working_tree_dirty = false`).

## Completion conditions (§101)

| # | Condition | Result | Evidence |
| --- | --- | --- | --- |
| 1 | R4 code integrated | PASS | merge commit `7054afe5` |
| 2 | working tree clean | PASS | checked before, between, and after the gates |
| 3 | Rust tests | PASS | `cargo test`: 71 passed, 0 failed (workspace); `reasonscript-computation-ir`: 46 |
| 4 | clippy | PASS | CI-parity command exits 0; no warnings in the R4 files (8 pre-existing warnings elsewhere) |
| 5 | rustfmt | PASS | no drift in any file this integration changes |
| 6 | Python computation tests | PASS | `computation_ir_tests`: 393 passed |
| 7 | Golden 49/77/84/97/221 | PASS | 5 cases |
| 8 | Differential N = 2…89 | PASS | 88 cases |
| 9 | 94/94 R0 compatibility | PASS | `r0_digests.json` test and a live R0 run: 94/94 responses identical |
| 10 | five hashes equivalent | PASS | `reasoning_state_hash`, `initial_hash`, `state_transition_hash`, `causal_observation_hash`, `causal_relation_hash` equal in 94/94 cases (R0 vs post-merge) and pre- vs post-merge |
| 11 | 3-run determinism | PASS | all five hashes, N = 84 and 10007 |
| 12 | artifact replay | PASS | Python (artifacts only) and Rust `replay` |
| 13 | mutation detection | PASS | 12/12 mutants detected (Rust 12, Python 12); sources restored |
| 14 | schema validation | PASS | reasoning_state, state_transition, state_causality, causal_relation, runtime_request |
| 15 | post-merge clean benchmark | PASS | below |
| 16 | RUS overhead ≤ +10% | PASS | +1.4% |
| 17 | State Causality ≤ +20% | PASS | +5.1% |
| 18 | Runtime-related CI | PASS | pull request #56, table below |

The key-order-sensitive comparison (whole response minus `*_ns`, as JSON text) also matched for all
94 cases, pre-merge R4 against post-merge R4 as well (94/94).

## Post-merge performance (§52–§59)

Release build, `runtime_execution_ns` against `executable_reason_units=full`, corpus 77 / 997 / 10007 /
30030 / 10403, 3 warm-ups + 25 interleaved samples, rustc 1.93.1 (01f6ddf75 2026-02-11), macOS-26.6.2-arm64-arm-64bit-Mach-O, arm64.
The post-merge binary is byte-identical to the pre-merge R4 binary
(SHA-256 `16cff3ce8f9b2d6d…`), so any difference between the two R4 rows is run-to-run measurement noise
(about ±1–2 points on this machine), not a code difference.

| Build | Lightweight RUS | State Causality |
| --- | --- | --- |
| R0 (`111f199a`) | +19.7% | +44.8% |
| R4 pre-merge | +2.8% | +5.7% |
| R4 post-merge | **+1.4%** | **+5.1%** |

Per case (post-merge): 77: +5.1% / +6.1%, 997: +3.3% / +9.2%, 10007: -1.1% / +3.2%, 30030: +4.1% / +11.2%, 10403: +1.8% / +3.7%.

Regression guard (§58): post-merge over pre-merge runtime, aggregate ratios
normal 1.004, ru_full 1.008, lightweight_rus 0.995, state_causality 1.003, state_causality_native_causal 0.998 (limit 1.10) — PASS.
No individual case exceeded 1.10.

Formal benchmark on arm64 macOS: aggregate +1.4% / +5.1%
(the R4 formal evaluation of the same binary recorded +3.1% / +6.6%). These are results for the tested corpus, machine, and
configuration, not a general performance guarantee.

## Continuous integration (pull request #56, head `7b9ec573`)

| Check | Conclusion |
| --- | --- |
| Build / Package VS Code extension | pass |
| Build / build | pass |
| CI Stabilization / ci | pass |
| Init and Manifest Compatibility / linux-x86_64 | pass |
| Init and Manifest Compatibility / macos-arm64 | pass |
| Init and Manifest Compatibility / macos-x86_64 | pass |
| Init and Manifest Compatibility / windows-x86_64 | pass |
| Lint / lint | fail — pre-existing, identical on main: ruff E731 at scripts/benchmark_executable_ru.py:265 (clippy for every crate passed; not runtime-related) |
| Test / test | pass |

## Known items that are not caused by this integration

- **Lint** fails on `main` itself (`e5c82679`, before this integration): `ruff` E731 at
  `scripts/benchmark_executable_ru.py:265`, an executable-RU benchmark script. It is not runtime-related
  and is left unchanged here; the fix is turning that lambda into a `def`.
- **rustfmt** drift exists on `main` in `ReasonRuntime/crates/reason-object-core/src/lib.rs`; no file changed by this integration has drift.
- **Environment failures** (missing `vscode-extension/node_modules`), separated from runtime results:
  - `tests/lsp/test_vscode_extension_contract.py::test_vscode_extension_typescript_compiles_cleanly`: known-environment-failure
  - `vscode_extension_phase1_4_tests/test_vscode_extension_phase1_4.py::VSCodeExtensionPhase14Tests::test_vsxp14_003_dependency_presence`: known-environment-failure

## Rollback conditions (§91)

None triggered: no semantic, hash, artifact, or determinism mismatch; Golden, Differential, and
performance gates pass; the runtime-related CI checks pass.

## Frozen contracts after the merge (§104)

`RuntimeReasoningState` v0.1 semantics, `StateTransition` semantics, the five hashes, the causal
state relations (`CAUSES_STATE_CHANGE`, `ENABLES`, `TERMINATES`), and the published artifacts and
schemas are the R4 stable contract. Changing them needs a separate specification and version;
R4 is the fixed baseline for the next verification phase. `reasoning_state` and `state_causality`
remain `off` by default (§115). No language or runtime version bump is made here (§85–§87).

Verification artifacts: `artifacts/reasoning_state_merge/summary.json`, `post_merge_comparison.csv`;
benchmark artifacts and `computation_ir_tests/golden_reasoning_state/r0_digests.json` are kept for regression checks.
