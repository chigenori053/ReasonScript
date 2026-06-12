# ReasonScript Transaction Protocol Specification v0.1

Status: VALIDATED  
Applies to: `reason-ir/0.1`

## 1. Authority

State Kernelだけがcurrent stateを変更できる。Planner、Graph、Memory Adapter、
Tool Adapter、SDKはstate snapshotまたはdelta candidateを生成できるがcommitできない。

## 2. Prepare

入力:

```text
transaction_id
execution_plan_id
TransitionSpec
proposed StateSnapshot
```

出力:

```text
PreparedDelta
├─ candidate_id
├─ transaction_id
├─ execution_plan_id
├─ before_state
├─ proposed_state
├─ transition
├─ validation_status = pending
└─ validation_failures = []
```

Prepareはstateを変更しない。transaction IDはkernel内で一意とする。
transition sourceとcurrent state、transition targetとproposed stateが一致しない場合は
candidateを作成しない。

## 3. Validate

必須検証:

```text
constraint
guard
policy
budget
state_consistency
```

全項目成功時だけ`accepted`とする。1項目以上失敗した場合は`rejected`とし、
失敗項目をTransactionRecordへ保存する。candidateの再検証は禁止する。

## 4. Commit

Commit precondition:

1. candidateが存在する。
2. validation statusが`accepted`である。
3. candidateが未commitである。
4. current stateがPreparedDelta.before_stateと一致する。

Commit operation:

```text
StateKernel.apply
  -> new StateDelta
  -> state_delta_applied TraceEvent
  -> committed TransactionRecord
```

上記は1つの`TransactionKernel::commit`呼出し内で同期して実行する。
成功時はstate、delta ledger、trace、transaction recordがすべて更新される。
candidateの再commitは禁止する。

## 5. Rollback

Rollbackは元deltaの更新や削除ではない。current stateがsource deltaのafter stateと
一致する場合に、before/afterを反転した新しいStateDeltaを生成する。

```text
source:   A -> B (delta-1)
rollback: B -> A (delta-2, applied_transition = rollback:<transition>)
```

rollback deltaにもTraceEventとTransactionRecordを生成する。同じsource deltaを
複数回rollbackすることは禁止する。

## 6. Failure Semantics

- validation rejection: state不変、deltaなし、Rejected recordあり
- commit precondition failure: state不変、trace追加なし
- rollback state mismatch: state不変、rollback済みとして消費しない
- duplicate transaction ID: operation拒否
- missing trace event: transaction consistency failure

## 7. Audit

TransactionRecord:

```text
transaction_id
execution_plan_id
candidate_id
delta_id | null
status
commit_timestamp | null
validation_failures[]
source_delta_id | null
```

全committed/rolled_back recordはdelta IDを持ち、そのdelta IDに対応する
`state_delta_applied` eventが存在しなければならない。

