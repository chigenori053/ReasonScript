# ReasonUnit Phase1.5 Runtime Stability Validation Report

実行日時: 2026-05-14 JST

## Summary

- 実行コマンド: `cargo test -- --nocapture`
- 実行場所: `/Users/chigenori/development/ReasonScript/Test`
- 結果: PASS
- 合計: 11 passed, 0 failed
- Phase1.5: 5 passed, 0 failed

## Phase1.5 Verified Items

- persistence
- serialization
- deserialization
- deterministic replay
- rollback cascade
- long-chain transition
- dependency integrity
- `Invalidated` state transition

## Phase1.5 Experiments

| 実験 | 内容 | 結果 |
| --- | --- | --- |
| E | `ReasonUnit("apple")` の serialize -> deserialize -> compare | PASS |
| F | `2 + 3` の derive -> trace 保存 -> replay | PASS |
| G | `A = 2`, `B = A + 3`, `C = B + 4` で `rollback(B)` 後に `C` invalidated | PASS |
| H | `RU1 -> RU2 -> ... -> RU100` の long-chain stability | PASS |

## Stability Criteria

| 評価基準 | 結果 |
| --- | --- |
| Persistence Integrity | PASS |
| Replay Determinism | PASS |
| Rollback Consistency | PASS |
| Transition Stability | PASS |

## Failure Conditions

| 失敗条件 | 検出結果 |
| --- | --- |
| trace mismatch | Not detected |
| dependency corruption | Not detected |
| replay mismatch | Not detected |
| rollback inconsistency | Not detected |
| state corruption | Not detected |
| invalid propagation | Not detected |
| transition divergence | Not detected |

## Test Output

```text
   Compiling reasonunit_phase1_test v0.1.0 (/Users/chigenori/development/ReasonScript/Test)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.32s
     Running unittests src/lib.rs (target/debug/deps/reasonunit_phase1_test-85da8b8e8bd8d1cc)

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

     Running tests/phase1.rs (target/debug/deps/phase1-e6bc7a741b4cbd94)

running 6 tests
test experiment_a_creates_token_unit ... ok
test experiment_b_transforms_token_and_keeps_traceability ... ok
test experiment_c_derives_numeric_sum_with_dependencies ... ok
test experiment_d_rolls_back_invalid_result_and_rederives ... ok
test rejects_invalid_state_transitions ... ok
test validates_allowed_state_transitions ... ok

test result: ok. 6 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

     Running tests/phase1_5.rs (target/debug/deps/phase1_5-ec9cd0d856b5e9ef)

running 5 tests
test experiment_f_deterministic_replay_reconstructs_same_result_trace_and_dependency ... ok
test experiment_g_rollback_cascade_invalidates_downstream_linear_dependency ... ok
test experiment_e_persistence_roundtrip_preserves_complete_unit ... ok
test phase1_5_state_machine_allows_rollback_to_invalidated ... ok
test experiment_h_long_chain_stability_keeps_trace_dependency_and_rollback_valid ... ok

test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s

   Doc-tests reasonunit_phase1_test

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```
