# ReasonScript Explicit Runtime Reasoning State / Lightweight RUS v0.1

Implementation notes and verification record. The requirement text is the
"Explicit Runtime Reasoning State / Lightweight RUS v0.1 Specification"; section
numbers (§) below refer to it.

## What changed

```text
RU (Executable RU completes)
  → ReasonStructure::finish_executable        (one hook, all RU producers)
  → RuntimeReasoningState::effect_of          (operation → typed updates)
  → ReasonStructure::apply_reasoning_state_update   (single mutation gateway)
  → RuntimeReasoningState::apply              (diff, no-op check, revision, StateTransition)
  → StateCausality::observe / link_next_ru    (CAUSES_STATE_CHANGE / ENABLES / TERMINATES)
```

| File | Role |
| --- | --- |
| `reasoning_state.rs` (new) | `RuntimeReasoningState`, `ReasonStateField`, `ReasonStateValue`, `GoalStatus`, `StateTransition`, replay, hash, metrics, `RUS-*` |
| `state_causality.rs` | No longer owns state or revisions; projects transitions into relations |
| `reason_structure.rs` | Owns both; the only place state is mutated; RU-completion hook |
| `vm.rs` | All manual before/after JSON hooks deleted; `relation.filter` runs real RUs |
| `runtime-cli` | `context.reasoning_state`, `metadata.reasoning_state` |

`record_state_transition(before, after)` no longer exists (Phase F, §112);
`test_no_manual_state_transition_hook_remains_in_the_runtime` guards it, including
that `RuntimeReasoningState` is the only constructor of `StateTransition`.

## Decisions the spec left open

1. **Where state changes.** In `finish_executable`, keyed by the RU's *operation*
   (§46/§47 "RU semantic operation → Evidence → state update → RU complete"). The VM
   never touches state, so `relation.filter`, legacy `reasoning.event`, and future
   native RUs share one path, and `source_ru` is always a real RU id (§48).
2. **Where `remaining` comes from (§53–§57).** A program reports semantic events;
   the *runtime* computes the values. `REASON_STATE_CREATED(n)` initializes
   `remaining = n`, `search_bound = isqrt(n)`, `goal_status = ACTIVE` at revision 0
   with no transition (§70/§71). A `HYPOTHESIS_VERIFIED(f)` then sets
   `remaining / f` and `isqrt(remaining / f)` in one atomic transition. If `f` does
   not divide the runtime `remaining`, the update is refused with `RUS-003` — the
   runtime, not the program, is the source of truth (§3, §10).
3. **Compatibility.** Without `REASON_STATE_CREATED`, `HYPOTHESIS_VERIFIED` has no
   state effect. A second `REASON_STATE_CREATED` after any transition is `RUS-004`;
   v0.1 tracks one reasoning problem per run.
4. **`relation.filter` goal.** The old code borrowed the last verification RU as the
   goal transition's source. It now completes a real `GOAL_EVALUATION` RU
   (`FILTER_GOAL`, `GOAL_CONFIRMED` Evidence) before the termination check, so the
   §60 chain holds natively. These RUs already only existed when state causality was on.
5. **ENABLES mapping (§64).** Kept as is, plus `GOAL_EVALUATION` for `remaining` /
   `search_bound`: goal evaluation is the reader of those fields, and without it the
   semiprime chain `remaining → next RU → goal` has no next RU. `link_next_ru` still
   links from the latest transition only.
6. **Enabling (§74/§75).** `state_causality != off` enables the state automatically;
   `reasoning_state = lightweight` alone maintains state and hashes without recording
   transitions/relations. Both need `executable_reason_units = full`; otherwise
   `RUS-005`. Defaults stay `off` (§155).
7. **Hash (§85/§86).** SHA-256 of `{"revision", "fields"}` with fields in external-name
   order; `initial_hash` is the same at revision 0. Recomputable from artifacts alone
   (tested), and `RuntimeReasoningState::replay` rebuilds the final state from the
   initial state plus transitions (§82), checked by a `debug_assert!` (§129).
8. **Redundant work removed.** `link_next_ru` scanned all relations to dedupe, but is
   called exactly once per RU begin, so the scan is gone.

## Diagnostics

`RUS-001` missing source RU · `RUS-002` unknown field (JSON entry point) ·
`RUS-003` invalid value / factor does not divide `remaining` ·
`RUS-004` revision misuse (late initialization, non-contiguous replay) ·
`RUS-005` reasoning state used without executable RU `full` or while off.

## Verification

| Spec item | Evidence |
| --- | --- |
| A–D initial state, single/atomic update, no-op | Rust `group_a`…`group_d` tests; Python `test_group_a…`, `test_groups_b_c_d…` |
| E–F source RU, FACTOR_CONFIRMED Evidence | `test_groups_e_f…` |
| G–K, P real factorization of 77, chain, minimal semiprime chain | `test_groups_g_h_i_j…`, `test_group_k_and_p…` |
| L rejected candidates | `test_group_l…`, `test_inconsistent_verification…` |
| M 3-run determinism (state, transition, observation, relation hashes) | `test_group_m…` |
| N/O multiple factors, prime | `test_group_n…`, `test_group_o…` |
| Golden 49/77/84/97/221 | `golden_reasoning_state/golden.json`, generated by an independent Python oracle; `test_golden_dataset…` also asserts `oracle(n) == case` |
| Differential | `test_runtime_state_equals_independent_oracle_for_every_small_n` (N = 2…89) |
| No hand-written state graph | inputs are source template + N + context only; `test_golden_inputs_contain_no_hand_written_state` |
| Schemas | `schemas/reasoning_state.schema.json`; `test_artifacts_validate_against_the_published_schemas` |

The tests were also checked to fail under deliberate mutations (no-op detection off,
stale `search_bound`, double revision increment, rejected verification adding a
constraint).

Golden N=77: revision 8; `current_candidate` 2→…→7 (six transitions), then
`{remaining 77→11, search_bound 8→3}` as one transition, then `goal_status
ACTIVE→REACHED`; factors 7 × 11; final `remaining 11, search_bound 3`.

## Known limits

- **Evidence coverage.** Candidate adoption through legacy `HYPOTHESIS_CREATED`
  events has no Evidence (the legacy adapter does not create it, and changing it would
  change existing Full/Count hashes), so `state_evidence_coverage` is below 1.0 for
  event-driven runs (N=77: 0.25). §51 allows this; the metric reports it.
- **Overhead is above the reference targets** (§133/§134, reference only). Release
  build, host boundary, trace off, 5 factorization cases, total against
  `executable_reason_units=full`: Lightweight RUS +16–19%, with State Causality
  +45%. Measured internal cost is ~0.57 µs per transition for the state and ~0.5 µs
  for causality (per-transition strings, maps, and provenance JSON), not the clock
  reads. The candidates are lazy relation/provenance construction at trace time and
  interned field names; not done because v0.1 is correctness-first.
- **Not a formal benchmark.** `scripts/benchmark_reasoning_state.py` records
  `working_tree_dirty`, `source_commit`, and `runtime_binary_sha256`; the recorded
  run had `working_tree_dirty = true`, so it needs a re-run on a clean commit (§136).
- Count-compatible state causality, state read tracking, and persistence remain P1 (§157).
