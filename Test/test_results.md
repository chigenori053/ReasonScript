# ReasonUnit Phase1 Test Results

実行日時: 2026-05-14 JST

## Summary

- 実行コマンド: `cargo test -- --nocapture`
- 実行場所: `/Users/chigenori/development/ReasonScript/Test`
- 結果: PASS
- テスト数: 6 passed, 0 failed

## Verified Items

- ReasonUnit生成
- payload保持
- trace保持
- derive成功
- rollback成功
- dependency保持
- state transition validation
- invalid transition reject

## Phase1 Experiments

| 実験 | 内容 | 結果 |
| --- | --- | --- |
| A | Token生成 `"apple"` | PASS |
| B | Token変換 `"apple" -> "fruit"` | PASS |
| C | 数値演算 `2 + 3 = 5` | PASS |
| D | invalid `2 + 3 = 6` から rollback 後に re-derive | PASS |

## Test Output

```text
   Compiling reasonunit_phase1_test v0.1.0 (/Users/chigenori/development/ReasonScript/Test)
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.14s
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

   Doc-tests reasonunit_phase1_test

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s
```
