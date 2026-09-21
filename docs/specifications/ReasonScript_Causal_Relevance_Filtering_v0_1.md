# ReasonScript Causal Relevance Filtering v0.1

Implementation notes and verification record for the "Causal Relevance Filtering v0.1 Specification".
Section numbers (§) refer to it.

## What was built

```text
Runtime Reasoning Graph (Executable RU, Evidence, RUS, StateTransition, CausalRelation)
        │  after execution only
        ▼
Goal-seeded backward traversal ──▶ Classification per RU ──▶ Relevance mask ──▶ Relevant RUS / RUO view
   (roots, max_causal_depth)        ESSENTIAL / SUPPORTING /              (only NOISE leaves;
                                    EXCLUSION / UNRESOLVED / NOISE         Full View untouched)
```

`crates/computation-ir/src/causal_relevance.rs` (classification, §67–§68) sits between `causal.rs`
(causality judgement) and `reason_objects.rs` (RUS/RUO projection, which now takes an optional mask, §69).
Nothing runs while the program executes (§64–§65); the analysis reads the causal trace and the runtime tables.

`context.causal_relevance` is `off` (default), `annotate`, or `filter`:

| Mode | Output | Requires |
| --- | --- | --- |
| `off` | nothing; the response is byte-identical to before | — |
| `annotate` | `metadata.causal_relevance`: roots, a class and reason codes per RU, metrics, `causal_relevance_hash` | `causal_evaluation != off` (`REL-007`) |
| `filter` | the above and `relevant`: relevant RUS / RUO view, `relevant_ruo_graph_hash`, size and reduction metrics | also `executable_reason_units=full` (`RUO-001`) and `state_causality=full` (`RUO-002`) |

`filter` does not require `reason_objects` to be on. With `reason_objects=off` the response has only the relevant view;
with `rus_ruo` it has both, and `metadata.rus` / `metadata.ruo` are unchanged (§58, §74). Classification is never
attached to `metadata.ruo` objects, so the existing artifacts and `ruo_graph_hash` cannot change (§74, §76).
`context.causal_relevance_roots` (array of IDs) adds user roots (§27); the spec listed it as future work, and it is what
lets the synthetic test graphs (external observations, no native RUs) name a goal.

## Classification

Backward traversal runs from the **roots**: Termination and GoalEvaluation RUs, the final RUS, the
`goal_status` transition (§26), and user roots (canonical ID order, §81). Traversed relations: the causal relations
(`CAUSES`, `CAUSES_STATE_CHANGE`, `ENABLES`, `TERMINATES`, `DEPENDENCY`, `PREVENTS`) and the state lineage
`UPDATES` / `DERIVES_STATE` / `READS_STATE` (RU → RUS after, parent RUS → RUS, RUS before → RU; §28–§29). `TEMPORAL`
never propagates (§30). Only causal relations count toward `max_causal_depth`; the RUS chain is structural.

| Relation into a reached node | Gives the source | Reason code |
| --- | --- | --- |
| `CAUSES` / `CONFIRMED`, direct, target is a root | `ESSENTIAL` | `DIRECT_CAUSE` (+ `COUNTERFACTUAL_NECESSARY`) |
| `CAUSES`, transitive (`provenance.indirect`), or a direct cause of a non-root reached node | `SUPPORTING` | `TRANSITIVE_CAUSE` |
| `CAUSES_STATE_CHANGE` / `CONFIRMED`; the RU updates a RUS on the state lineage | `ESSENTIAL` | `STATE_CAUSE` |
| `TERMINATES` / `CONFIRMED`; the RU is a Goal/Termination RU | `ESSENTIAL` | `GOAL_TERMINATION` |
| `PREVENTS` / `CONFIRMED` into a root (else into any reached node) | `ESSENTIAL` (else `SUPPORTING`) | `PREVENTS` |
| `ENABLES` / `CONFIRMED` | `SUPPORTING` | `ENABLES` |
| `DEPENDENCY` / `SUPPORTED` | `SUPPORTING` | `SUPPORTED_DEPENDENCY` |
| `DEPENDENCY` / `REJECTED` with `dependency=true` (an alternative supplies the Evidence) | `SUPPORTING` | `ALTERNATIVE_DEPENDENCY` |
| the RU initialized RUS 0 | `SUPPORTING` | `INITIAL_STATE` |
| rejected candidate check, and later a verified check or a reached goal | `EXCLUSION` | `SEARCH_EXCLUSION` |
| `PREVENTS` into a node off the goal path | `EXCLUSION` (both ends) | `PREVENTED` |
| touches a `CONFLICT` or `INSUFFICIENT` relation | `UNRESOLVED` | `CONFLICT` / `INSUFFICIENT` |
| upstream of a node the depth limit cut off (`REL-004`) | `UNRESOLVED` | `DEPTH_EXCEEDED` |
| rejected check with no later resolution | `UNRESOLVED` | `SEARCH_UNRESOLVED` |
| no root at all (`REL-001`), unknown relation kind (`REL-003`), dangling endpoint (`REL-002`), native RU without a state graph (`REL-008`) | `UNRESOLVED` | `NO_ROOT` / `UNKNOWN_RELATION` / `DANGLING_REFERENCE` / `STATE_GRAPH_UNAVAILABLE` |
| none of the above, only `TEMPORAL` relations | `NOISE` | `TEMPORAL_ONLY` |
| none of the above | `NOISE` | `NO_PATH_TO_ROOT` |

Precedence: `ESSENTIAL` > `UNRESOLVED` > `SUPPORTING` > `EXCLUSION` > `NOISE`, reasons are the union. Only `NOISE` is
ever dropped (§19–§20); anything undecidable resolves to `UNRESOLVED` (§85–§86); any failure fails open (§135–§137):
a missing root keeps everything, an inconsistent result (`REL-006`) reclassifies to `UNRESOLVED`. The classification
hash covers `[ru_ref, class, reason_codes]` in execution order (§80, §82).

### Decisions worth knowing

1. **The final RUS is a root, and the state lineage is traversed, so every state-changing RU is reached.** The final state
   derives from every transition through `DERIVES_STATE`; a RU that changed the state is a direct state cause (§14 "…or
   StateTransition"), so `ESSENTIAL`. That is also why the RUS sequence is never reduced: every revision is on the
   derivation chain. `rus_reduction_ratio` is 0 for native traces (§44–§48 hold trivially).
2. **Hypotheses are not rejected checks.** Only a rejected *verification* is an `EXCLUSION`. A hypothesis that changes
   `current_candidate` is a state cause and `ESSENTIAL`; one that repeats the current candidate (composite `N` with
   repeated factors, e.g. `N = 84` after the factor 2) changes nothing and has only `TEMPORAL` relations, so it is
   `NOISE` (§84 verbatim: no root path, no state cause, no Evidence dependency, no search exclusion, no conflict).
3. **"Same search sequence" (§33)** is the single reasoning-state lineage of the run. There are no search branches in v0.1;
   branch RUS would need a per-branch sequence.
4. **Direct vs. transitive (§22–§23):** a direct `CAUSES` is `ESSENTIAL` only when it touches the goal (a root) or the state;
   a cause of a cause is `SUPPORTING`.
5. **`DEPENDENCY` / `REJECTED` is `SUPPORTING`, not `NOISE`,** when it carries an Evidence dependency (§84 requires "no Evidence
   dependency" for `NOISE`); with no Evidence link it is a noise candidate.
6. **The depth limit cuts, it does not delete.** The first version left nodes *behind* a cut-off node unvisited and so
   `NOISE`; a Rust unit test found it. Everything upstream of a node the limit cut off is now `UNRESOLVED`.
7. Selective counterfactual (§87–§90) is P2 and not implemented; the existing causal evaluation's budget exhaustion
   (`CAUSAL-BUDGET-001`) yields `INSUFFICIENT` relations, which are `UNRESOLVED` here, with `REL-005`.

## Relevant view (`filter`)

`relevant.rus` / `relevant.ruo` are ordinary `reason-unit-state/0.1` / `reason-unit-object/0.1` artifacts built by the same
projection with a mask: dropped RUs, their RUOs, the `READS_STATE` relations they own, the ReasonRelations and Evidence
touching them, and every `TEMPORAL` causal relation are left out. IDs are the full projection's IDs (relation numbering is
not compacted), so a reference means the same thing in both views. `relevant.causal_relation_refs` lists the kept causal
relations. The relevant RUS sequence is the full one whenever every state revision is on the lineage, and then
`relevant_rus_sequence_hash == rus_sequence_hash`. Evidence retention (§49–§50) is expressed by the retained RUOs'
`evidence_refs`; orphan Evidence is simply not referenced.

Metrics: the six counts (§112), `ru_/ruo_/rus_/relation_reduction_ratio` (§113), `full_json_bytes`,
`relevant_json_bytes`, `response_reduction_ratio` (§114; the full size needs the full view, so it is `null` when
`reason_objects` is off; sizes include the digits of the embedded `*_ns` values and can differ by a byte between runs),
`causal_relevance_ns`, `relevant_projection_ns` (§115), `reasoning_noise_reduction_ratio` (§117, at RU level) and
`essential_preservation_rate` (§118, recounted from the relevant RUOs, not assumed).

Hashes: `causal_relevance_hash`, `relevant_ruo_graph_hash` (§77–§78), plus `relevant_rus_sequence_hash` and
`relevant_rus_relation_hash`. Diagnostics: `REL-001`..`006` as specified; `REL-007` (`causal_relevance` needs
`causal_evaluation`, a request error) and `REL-008` (native RUs without a state graph are kept `UNRESOLVED`) are additions.
Schema: `schemas/causal_relevance.schema.json` (class and reason-code enums fixed, §132–§133); the request schema gained
`causal_relevance` and `causal_relevance_roots`.

## Verification

| Requirement | Evidence |
| --- | --- |
| A direct cause / B state cause / C ENABLES / D temporal-only / E conflict / F insufficient (§91–§96) | Rust unit tests on synthetic graphs and Python end-to-end tests on external observations (`test_a_…`, `test_d_…`, `test_e_…`, `test_f_…`), N=77 for B/C |
| G rejections, H verified factor, I goal, J termination (§97–§100) | `test_group_g…`, `test_group_h_i_j…` (candidates 2–6 `EXCLUSION`, candidate 7 / goal / termination `ESSENTIAL`, roots) |
| K full vs relevant N=77, L N=84, M prime 97 (§101–§104) | groups K, L, M: relevant RUOs equal the full ones up to dropped `TEMPORAL` references; every verified factor chain kept; 8 exclusions + goal + termination for 97 |
| N unrelated RU injection (§105) | 12 injected `RU_ACTIVATED` events are exactly the `NOISE` set; the other RUs' classes, the RUS field history, and the relevant view are the run without them |
| O alternative Evidence (§106) | `test_o_…`: `SUPPORTING` / `ALTERNATIVE_DEPENDENCY` |
| P determinism (§107) | 3 runs: all four hashes and the whole artifact (minus timing and byte sizes) equal |
| Q existing hashes (§108) | five hashes plus `causal_observation_hash`, and the whole response minus `metadata.causal_relevance`, equal with `annotate` / `filter`, N ∈ {49, 77, 84, 97, 221, 10007}, key order included |
| R `off` byte-compatible (§109) | dict and key-order-sensitive JSON equal, with and without the full view; the 94-case R0 digest test still passes |
| S referential integrity of the relevant view (§110) | independent artifact-only validator, same N set and injected-noise traces; a meta-test proves it detects injected dangling RUS/Evidence/relation/causal/source references |
| T classification mutation (§111) | 14 mutants: `CAUSES`→noise, `CONFLICT`→noise, exclusion removed, goal root removed, wrong edge direction, temporal propagates, depth ignored, missing root not fail-open, state cause demoted, unresolved never applied, reasons out of the hash, temporal kept in the view, noise never dropped, dropped RU's relations kept — **all detected** (one initially survived; the missing case, a relation tying a kept RU to a dropped RU's Evidence, cannot occur with today's event vocabulary and got a Rust unit test) |
| Golden and differential (§155–§156) | golden N = 49, 77, 84, 97, 221 and N = 2…89 against an independent model that never reads the causal graph (state changers essential, rejected checks exclusions, initializer supporting, the rest noise) |
| Metrics recompute | counts, reductions, relation counts, byte sizes, and the three hash families recomputed from the artifacts alone |
| Schemas | `causal_relevance`, `rus`, `ruo`, `runtime_request`; broken enums are rejected |
| Full suite | `cargo test --workspace` (68 tests in `computation-ir`), clippy, `ruff`; Python 2836 passed, 2 failed (`vscode-extension` TypeScript build and dependency presence, environmental and unrelated); all 36 mutants of the reasoning-state gate (R4, RUS/RUO, relevance) detected |

Completion gates: A (classification tests), B (essential preservation = 1.0 in every benchmark and differential case), C (conflict /
insufficient never dropped), D (existing hashes), E (Full View unchanged), F (relevant dangling refs = 0), G (3-run determinism),
H (golden), I (differential N=2…89), J (mutation): met.

## Performance (§122–§129)

Release build, arm64 macOS, rustc 1.93.1, 2 warm-ups + 15 interleaved samples, primes 997 / 10007 / 100003 with
0 / 1 / 3 / 9 unrelated events per rejected candidate. `scripts/benchmark_causal_relevance.py`,
`artifacts/causal_relevance/`. **The tree was dirty for this run: informal.**

* **Execution hot path: unchanged.** `runtime_execution_ns` with the relevance code present but off is 0.994× the build
  before this change (limit 1.10); `annotate` / `filter` do not touch it either (relevance runs after execution).
* **Net Projection Gain** = full RUS+RUO projection cost − (relevance analysis + relevant projection), from the runtime's
  own metrics:

| noise (share of RUs) | 997 | 10007 | 100003 |
| --- | --- | --- | --- |
| 0% (canonical factorization) | −32% | −26% | −26% |
| ~33% | −13% | −9% | −8% |
| ~60% | +5% | +11% | +14% |
| ~82% | +31% | +35% | +38% |

  Break-even is at about 41–49% noise for the projection alone (and about 21–30% for whole-process wall time, which also
  saves serialization: 100003 with 82% noise, 5.9 MB → 4.6 MB). §127 (net gain > 0 on large traces) therefore holds
  **when the trace is noisy**, from roughly half noise; on traces with little noise the analysis costs more than it saves
  (§128–§129 expected this only for small traces, but it also applies to large, clean ones).
* **The canonical factorization has almost no noise**: 0% for the primes and for 77 / 97 / 10007 / 100003; 8.8% of all RUs for
  `N = 2…89` (the repeated-candidate hypotheses). The noise the filter removes in the benchmark is injected, so the
  benchmark shows the mechanism pays off on noisy traces, not that today's factorization traces shrink. With `noise = 0`
  the relevant view is 2–3% *larger* in bytes than the full one only because it also carries the per-RU classification list;
  relations still shrink by 22% (the `TEMPORAL` ones).
* `filter` next to `rus_ruo` computes both views, so it always costs more than either alone; the saving is for consumers that
  ask for the relevant view instead of the full one.

## Not done (§143–§145)

P0 and P1 are implemented (the benchmark is informal, see above). P2 (selective counterfactual, adaptive threshold,
automatic full/relevant switching, DSN activation pruning, pre-execution pruning) is out of scope, as the specification
says. Branch RUS (per-branch search sequences) and Evidence-level classification (Evidence is kept or dropped with its RU)
are also not modelled.
