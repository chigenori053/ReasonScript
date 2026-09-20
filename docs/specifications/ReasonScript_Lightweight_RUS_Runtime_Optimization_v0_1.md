# ReasonScript Lightweight RUS Runtime Optimization v0.1

Implementation notes and verification record. The requirement text is the
"Lightweight RUS Runtime Optimization v0.1 Specification"; section numbers (§)
refer to it. Semantics, state, causal graph, artifacts, and hashes are unchanged;
only the runtime representation moved.

## Result

Host boundary, release build, `runtime_execution_ns` against
`executable_reason_units=full`, aggregate over the corpus 77 / 997 / 10007 /
30030 / 10403, 3 warm-ups + 25 interleaved samples:

| Stage | Change | Lightweight RUS | State Causality |
| --- | --- | --- | --- |
| R0 | Lightweight RUS v0.1 (commit `111f199a`) | +18.5% | +43.2% |
| R1 | typed state / transition, field bitmask, no BTreeMap | +3.7% | +39.2% |
| R3 | + lazy artifacts, typed relations, lazy provenance (R2 and R3 together) | +3.7% | +7.9% |
| R4 | + streaming hashes, `Rc` for structured values | **+2.9%** | **+6.7%** |

Targets (§141): RUS ≤ 10% and State Causality ≤ 20% → **PASS** on the aggregate and on
every case (per-case RUS 1.3–3.5%, State Causality 5.4–8.7%). Four full runs of the
benchmark put the R4 aggregate at 2.2–4.0% (RUS) and 6.1–7.8% (State Causality) and R0 at
18–19% and 43–44%; the table is the last run, which is what
`artifacts/reasoning_state_optimization/summary.json` holds. That run had
`working_tree_dirty = true`, so it is **not a formal evaluation** (Gate G, §140) — see
"Open items".

The moved work is not the saved work. In-process (run + response construction, same
harness for both builds), R4 / R0 is **0.84** for State Causality (run alone 0.74,
response construction alone 1.17) and 0.88 for Lightweight RUS. Hot-path allocations per
transition fell from 14–18 (RUS) and 44–62 (State Causality) to 0.0 and 0.1–0.6 (only
`Vec` growth).

## What was built

| Spec target | Implementation |
| --- | --- |
| A typed transition | `RuntimeStateTransition { revision_before, source_ru: RuRef, evidence: EvidenceRefs, changed: FieldMask, before[5], after[5] }` |
| B BTreeMap elimination | state is `[ReasonStateValue; 5]`; updates are diffed through a fixed array; no map is built per transition |
| C static field names | `ReasonStateField::name()` is called only when an artifact or hash is produced |
| D lazy artifacts | `RuntimeStateTransition::to_artifact`, called from `StateCausality::trace` (response construction) |
| E/J typed relation, lazy provenance | `RuntimeStateRelation { kind (enum), transition index, RuRef }`; ID strings and provenance JSON are built in `trace` |
| F state hash | `state_hash` writes the canonical bytes `{"revision":R,"fields":{…}}` straight into SHA-256 |
| G transition hash | `transition_hash` streams each transition's canonical bytes into SHA-256 at trace time |
| H/I RU and Evidence references | `RuRef` / `EvidenceRef` are indices into the unit / evidence tables, resolved to canonical IDs by `RefResolver` |
| K metrics | counters only in the hot path; everything else at trace time |
| L clock | unchanged (see below) |

The `changed` bitmask also drives the causal mapping: `reads(kind)` is the set of fields
an RU kind reads, so `ENABLES` is `changed & reads(kind) != 0` and `TERMINATES` is a
goal-status bit on a termination check — no string comparison.

### Decisions

1. **R2 and R3 were built together.** Lazy transitions with eager relations would have
   had to re-resolve every ID string in the hot path, so the intermediate stage would have
   been throwaway code.
2. **The transition hash is streamed at trace time, not rolled at generation** (§32–§34).
   Canonical bytes plus SHA cost about 0.48 µs per transition (`transition_hash_ns`,
   N=10007); the whole remaining hot-path cost is about 0.1 µs per transition, so a rolling
   hash would have made the measured boundary several times worse. It still never
   re-serializes a `Value` tree, and the bytes equal `serde_json::to_vec` exactly.
3. **`Instant::now()` was kept.** A timed section (start + elapsed) costs 33–38 ns here
   (measured, ~16–19 ns per clock read). With two sections per transition (`apply`,
   `observe`) that is about 70 ns — roughly half of the remaining ~0.14 µs per transition.
   Both gates pass with it, and keeping it leaves the `*_runtime_ns` metrics with the same
   meaning in R0 and R4; §49–§51 asks that gains not come from removing timing. If the
   residual overhead ever matters, this is the first lever (time only in benchmark mode).
4. **Field order.** Bit positions follow §17 (`remaining`, `search_bound`, …); artifacts and
   canonical bytes iterate `ReasonStateField::BY_NAME` (alphabetical), which is the order
   `BTreeMap` produced before.
5. **Evidence order.** References are sorted numerically; IDs are zero-padded, so this equals
   the earlier string sort. `to_artifact` still sorts the resolved strings.
6. **`Rc<Value>` for structured candidates.** `relation.filter` candidates are JSON objects;
   the state, the transition, and the artifact now share one copy instead of three. The
   remaining ~8 allocations per transition on that path come from cloning the RU subject
   once (`ExecutableReasonUnit.subject` is owned).
7. **`goal_status` is a typed value** (`ReasonStateValue::Goal`), converted from its string
   only at the JSON entry point.

## Correctness gates (§60–§65, §134–§139)

| Gate | Evidence |
| --- | --- |
| A Golden 49/77/84/97/221 | `test_golden_dataset_matches_runtime_and_the_independent_oracle` |
| B Differential N = 2…89 | `test_runtime_state_equals_independent_oracle_for_every_small_n` |
| D Hash and artifact equivalence with R0 | `r0_digests.json` (generated by the R0 host) holds, for 94 cases, all five hashes and a SHA-256 of the whole response minus `*_ns`; `test_responses_and_hashes_are_identical_to_the_pre_optimization_runtime`. The benchmark also compares R0 and R4 responses as dicts *and* as key-order-sensitive JSON text: 94/94 identical |
| E Determinism | 3 runs, all five hashes, `test_group_m_…` and the benchmark |
| F Replay from artifacts only | `test_state_hash_is_canonical_and_history_replays_from_artifacts_alone`, plus Rust `replay` and a `debug_assert!` |
| Streaming = serde | Rust `streamed_canonical_bytes_equal_the_serde_artifact_bytes`, `streamed_state_hash_equals_the_serde_canonical_hash` (negative/extreme ints, escapes, control characters, Unicode, floats, nested JSON, 0–3 Evidence refs) |
| C Mutations | all detected — the four from §61 (no-op detection off, stale `search_bound`, double revision, rejected verification updating state) and the §62 additions (changed-field bit omitted, wrong source RU, wrong Evidence index, provenance missing the revision, transition hash missing a transition), plus: verification no longer reading `current_candidate`, `ENABLES` linked to the wrong transition, state hash dropping `goal_status`. Every mutant fails the Python suite; the last one that the Rust suite missed (wrong `ENABLES` transition) now fails a strengthened Rust test too |

## Phase 0 profile (§52–§55)

`scripts/profile_reasoning_state.py` (macOS `sample`, `artifacts/reasoning_state_optimization/profile/`),
State Causality on N=10403. Inclusive samples inside `run_calculations` (R0 2431 → R4 2104):

| R0 hot path | samples | R4 |
| --- | --- | --- |
| `RuntimeReasoningState::apply` | 161 | 31 |
| `StateCausality::observe` | 280 | 40 |
| `link_next_ru` | 225 | (inlined, negligible) |
| `state_relation` (provenance `json!`) | 435 | 508, now inside `StateCausality::trace` |
| `StateCausality::trace` (clones, `to_vec`, SHA) | 571 | 1006 (builds the artifacts once) |

R0 spent about 14–18 allocations per state transition and 44–62 with causality. Time was
allocator (`malloc`/`free` ≈ 40% of self samples), `memmove`, and `serde_json`, not the
clock.

## Pitfalls found while measuring

- **Feature unification.** `runtime-cli` enables `serde_json/preserve_order`; a harness built
  from `computation-ir` alone does not, and produced ~7% fewer allocations for the *same*
  code. The harness now lives in `runtime-cli/examples/`, so it is built exactly like the
  host. (It also means `computation-ir` unit tests see sorted JSON objects while the host
  keeps insertion order; only the host output is compared with R0.)
- **`request_id`** is part of the response and therefore of the digest.
- After restoring a mutated file with `mv`, cargo saw an old mtime and reused the mutant
  build; touch sources after a mutation run.

## Open items

- **Formal benchmark (Gate G, §99, §140).** All numbers above come from a dirty working
  tree. Commit, then run
  `scripts/benchmark_reasoning_state.py --binary R0=<r0 host> --binary R4=<host> --baseline-commit 111f199a`
  on release builds; the binaries do not change. The script records commit, dirty flag,
  binary SHA-256, compiler, OS, CPU, profile, and date (§100), and writes `summary.json`,
  `comparison.csv`, and graphs A–F.
- The R0 host for comparison is `git archive 111f199a ReasonRuntime` built with
  `cargo build --release -p reasonscript-computation-runtime-cli`.
- P1 (§133) not done: subject sharing for structured candidates, response-construction
  optimization (it is 17% slower than R0 while the total is 16% faster), Count-mode
  Lightweight RUS, allocator measurement beyond the harness's counting allocator.
