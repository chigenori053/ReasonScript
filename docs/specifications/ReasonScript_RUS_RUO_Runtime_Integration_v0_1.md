# ReasonScript RUS / RUO Runtime Integration v0.1

Implementation notes and verification record. The requirement text is the
"RUS / RUO Runtime Integration v0.1 Specification"; section numbers (§) refer to it.

## What was built

```text
Executable RU ─▶ RuntimeReasoningState ─▶ typed transition   (hot path: unchanged, compact)
                                              │
                          ┌───────────────────┴──────────────────┐
                          ▼   response construction only          ▼
                 RUS  (one per revision)                  RUO  (one per Executable RU)
                 immutable semantic state                 RU + RUS before/after + Evidence
                                                          + ReasonRelation refs + causal refs
```

`RuntimeReasoningState` stays the source of truth (§8, §54, §55). RUS and RUO are
projections built in `reason_objects.rs` from tables the runtime already keeps:
the Executable RU table, the typed transitions, the Evidence and ReasonRelation
tables, and the final causal relations. Nothing is created while the program runs.

Enable with `context.reason_objects` (default `off`):

| Mode | Output | Requires |
| --- | --- | --- |
| `off` | nothing; the response is byte-identical to before | — |
| `rus` | `metadata.rus` | `executable_reason_units=full` (`RUO-001`) and `reasoning_state=lightweight` or `state_causality != off` (`RUO-002`) |
| `rus_ruo` | `metadata.rus` and `metadata.ruo` | the above and `state_causality=full` (`RUO-002`), because RUOs reference causal relations |

`reason_objects=rus` alone keeps the typed transitions internally; `metadata.state_causality`
still reports nothing in that case (a test pins it).

## Existing RUS / RUO inventory (§125–§131)

Two things in the repository are called RUO:

1. **The runtime projection** behind `context.reason_units: ru_rus_ruo`
   (`reason_structure_trace.reason_unit_states / reason_unit_objects`, from `ReasonStructure::record`).
   This is the concept this specification extends: its object has `reason_unit_ref`,
   `current_state_ref`, `evidence_refs`, `relation_refs`, and `lifecycle`; the fields this
   specification adds are exactly the missing ones (`rus_before_ref`, `rus_after_ref`,
   `causal_relation_refs`).
2. **The Reason Object graph** (`reason-object-core`, `.ruo` artifacts, `ruo.*`, RUO-C
   wrap / validate / project / unwrap / semantic compare). It is a different, persistent object
   model and is deliberately untouched; its suites (`tests/reason_object_graph`, the RUO parity
   and native-runtime tests) run in the repository suite and pass.

The native RUO uses the specification's field names and keeps the legacy concepts:

| Legacy `reason_unit_objects` | Native `metadata.ruo.objects` |
| --- | --- |
| `reason_unit_ref` | `ru_ref` |
| `current_state_ref` | `rus_after_ref` (plus `rus_before_ref`) |
| `evidence_refs`, `relation_refs`, `lifecycle` | same names |
| — | `causal_relation_refs`, `status`, `semantic_signature` |

The legacy `reason_structure_trace` is unchanged, also when `reason_objects` is on
(`test_legacy_reason_structure_projection_is_untouched`), so no new field is optional or missing
for existing consumers; native RUOs always carry the new fields (§132).

## Artifacts

**RUS** (`reason-unit-state/0.1`, `schemas/rus.schema.json`), one per revision, in revision order:
`id` (`rus:runtime:00000008`), `revision`, `parent_revision` (`null` at 0), `fields` (the five
runtime fields), `source_ru_ref` (revision 0: the RU that initialized the state, else `null`),
`evidence_refs`, `transition_ref`, `semantic_state_hash`. `semantic_state_hash` is the runtime's
own state hash for that revision, so the last RUS equals `reasoning_state.hash` and RUS 0 equals
`reasoning_state.initial_hash` (§24, §88). `metadata.rus.relations` holds `READS_STATE`
(RUS → RU), `UPDATES` (RU → RUS after), and `DERIVES_STATE` (parent RUS → RUS); `ENABLES`,
`TERMINATES`, and `CAUSES_STATE_CHANGE` stay in the existing causal trace, which RUOs reference.

**RUO** (`reason-unit-object/0.1`, `schemas/ruo.schema.json`), one per Executable RU, in execution
order: `id` = `ruo:` + the RU ID, `ru_ref`, `rus_before_ref` (state when the RU began),
`rus_after_ref` (the RU's own transition, otherwise the same revision), `evidence_refs`,
`relation_refs` (`relation:ru:*` and `relation:rus:*`), `causal_relation_refs` (causal relations
touching the RU or its own transition, so a verification RUO reaches its `CAUSES_STATE_CHANGE`
and the `ENABLES` of the next RU), `lifecycle`, `status` (`VERIFIED`, `REJECTED`, `COMPLETED`),
`semantic_signature`. A rejected RU and an RU without a state change point at the same RUS
before and after (§40–§43).

**Hashes** (new, response-phase, streamed to SHA-256): `rus_sequence_hash`, `rus_relation_hash`
(`metadata.rus.hashes`) and `ruo_graph_hash` (`metadata.ruo.hashes`) — SHA-256 of a compact JSON
array of fixed-position records (`[id, parent_revision, source_ru_ref, transition_ref,
evidence_refs, semantic_state_hash]` per state, `[id, kind, source_ref, target_ref]` per relation,
`[id, ru_ref, rus_before_ref, rus_after_ref, evidence_refs, relation_refs, causal_relation_refs,
lifecycle, status, semantic_signature]` per object). A state's fields are committed by its
`semantic_state_hash`. The tests recompute all three from the artifacts alone. The legacy
`ruo_graph_hash` in `reason_structure_trace` is a different, unchanged value.

Metrics (`metadata.rus.metrics`, `metadata.ruo.metrics`): `rus_projection_count`,
`rus_relation_count`, `rus_materialization_ns`, `rus_hash_ns`, `ruo_count`,
`ruo_materialization_ns`, `ruo_hash_ns`, `dangling_reference_count`.

Diagnostics: `RUO-001` executable RU unavailable, `RUO-002` reasoning state / state causality
unavailable (both are request errors); `RUO-003` missing state revision, `RUO-004` missing
Evidence, `RUO-005` invalid relation reference, `RUO-006` duplicate RUO; `RUS-PROJ-001` missing
revision, `RUS-PROJ-002` invalid parent, `RUS-PROJ-003` state hash mismatch. Every reference is
validated during projection and counted in `dangling_reference_count`.

## Hot path (§152–§154)

The only additions while the program runs are three plain stores: the state revision at RU
begin (`ExecutableReasonUnit.state_before`, a `u32`), the RU that initialized the state
(`RuntimeReasoningState.initial_source_ru`), and a flag that keeps typed transitions when
state causality is off. Measured allocations in the run phase are identical with and without
projection (0 extra). The RUS/RUO structures, IDs, JSON, and hashes are built afterwards.

## Verification

| Requirement (§149) | Evidence |
| --- | --- |
| Lightweight RUS remains the source of truth; RUS immutable, IDs deterministic; final RUS = runtime state | projection reads the runtime tables; `test_final_rus_is_the_runtime_state_and_hashes_recompute_from_artifacts`; Rust `rus_revisions_are_immutable_projections…` |
| RU before/after refs; native RUO; Evidence / ReasonRelation / CausalRelation refs; rejected and no-change RUO | groups E–J, `test_native_relation_filter_projects_without_an_initialization_ru` |
| dangling refs = 0 | group O (N = 49, 77, 84, 97, 221, 10007), independent artifact-only validator, and a meta-test that it detects injected dangling refs |
| N=77 chain, N=84 multi-factor, N=97 prime | groups J, K, L |
| Golden, differential N = 2…89 | golden cases and `test_runtime_projection_equals_independent_oracle_for_every_small_n` (RUS fields and every RUO's RU, status, before/after against a Python model of the reasoning) |
| 3-run determinism; new hashes stable | group M and hash recomputation from artifacts |
| existing five hashes and existing artifacts unchanged | group P: with `rus` / `rus_ruo` on, the whole response minus `metadata.rus/ruo` and `*_ns` equals the run with them off, as a dict and as key-order-sensitive JSON; `r0_digests.json` (off) still matches |
| replay from RUS alone | group N |
| schemas | `rus.schema.json`, `ruo.schema.json`, `runtime_request.schema.json`; requests and artifacts validated, broken artifacts rejected |
| mutation | `scripts/mutation_reasoning_state.py`: 22/22 mutants detected (the R4 set plus 10 projection mutants: swapped before/after, wrong parent, dropped Evidence, dropped causal refs, skipped state in the hash, shifted RU binding, unrecorded begin revision, unrecorded initial RU, lost retention, leaking retention) |
| CI parity | `cargo test` (workspace), `cargo clippy --all-targets -- -A warnings …`, `rustfmt`, `ruff check .`; Python suite 2707 passed with the two known `vscode-extension/node_modules` failures excluded |

## Performance (§111–§119)

Release build, arm64 macOS, rustc 1.93.1, corpus 77 / 997 / 10007 / 30030 / 10403,
3 warm-ups + 25 interleaved samples, against the R4 configuration
(`executable_reason_units=full`, `state_causality=full`). `scripts/benchmark_reason_objects.py`,
`artifacts/reason_objects/`. **This run had `working_tree_dirty = true`: informal.**

| Cost | RUS | RUS + RUO | Reference |
| --- | --- | --- | --- |
| Execution hot path (`runtime_execution_ns`) | −2.6% | −2.4% (noise; ≈ 0) | ≤ +5% / ≤ +10%, HOLD above +20% |
| Hot-path allocations vs R4 | 0 | 0 | ideal 0 |
| Projection off vs the R4 binary before this change | ratio 0.987 | | ≤ 1.10 |
| Whole host process wall time (start, run, projection, serialization, output) | +8.3% | +18.5% | ≤ +20% (RUS + RUO) |
| In-process run + structure building, no serialization | +78% | +148% | for reference |

The hot path is unaffected. The response side is not free: building RUS costs about 0.3 ms and
RUS + RUO about 0.6 ms more for a 100-transition run (roughly 100 states, 400 relations, 200
objects, about 200 KB of JSON); the process-level figures above are diluted by process
startup. The reference targets are not gates; the only HOLD rule (hot path > +20%) is far from
triggered. The first version serialized the whole artifacts to hash them; streaming compact
records into SHA-256 cut the RUS projection from ~370 µs to ~290 µs at N = 10007.

## Decisions

1. **Extend the runtime projection, do not add a third RUO concept** — see the inventory.
2. **Omit `metadata.rus` / `metadata.ruo` when off** instead of emitting `mode: off`, so an
   existing response (and the R0 digest test) stays byte-identical.
3. **`rus_ruo` requires `state_causality=full`** rather than silently enabling it: enabling it
   would change `metadata.state_causality` and `causal_trace`, which must not change.
4. **RUS binding is recorded, not inferred**: `state_before` costs one store per RU and stays
   correct if RUs ever nest; `rus_after` comes from the RU's own transition.
5. **Relations `READS_STATE` / `UPDATES` / `DERIVES_STATE` are explicit objects** so the
   `RUS → RU → Evidence → RUS` chain (§31) is traversable; they are the largest part of `metadata.rus`.
6. **RUO causal refs include the RU's own transition's relations**, so RUO(A) sees the `ENABLES`
   of the next RU and RUO(B) sees the one that enabled it. References are IDs, never copies (§50).

## Open items

- The benchmark is informal until it is rerun on a clean commit.
- P1 (§148) not done: Count-compatible RUO, persistence, state read tracking, branch RUS, RUO graph
  query, MIRP projection (the relation names map as in §134), DSN and unknown-state integration.
- Response-side cost can be reduced further (borrowed strings, lazy relation endpoints) if the
  end-to-end reference matters more than it does now.
