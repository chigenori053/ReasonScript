# ReasonScript Runtime API Validation Phase 3 Report

Version: 0.1  
Validation date: 2026-06-12  
Target: Transaction Model  
Status: COMPLETE

## 1. Executive Summary

4候補を9評価軸とTransaction Invariant、9 validation caseで比較した。

| Rank | Model | Score | Decision |
|---:|---|---:|---|
| 1 | Model-C: StateDelta Transaction | 44 / 45 | Runtime Core v0.1へ採用 |
| 2 | Model-D: Event Sourcing | 38 / 45 | persistence導入時に再評価 |
| 3 | Model-B: Staged Commit | 31 / 45 | delta追跡不足のため不採用 |
| 4 | Model-A: Immediate Commit | 19 / 45 | rollback・audit要件を満たさず不採用 |

採用構造:

```text
ExecutionPlan (immutable)
  -> TransactionKernel.prepare
  -> PreparedDelta
  -> TransactionKernel.validate
  -> TransactionKernel.commit
  -> StateDelta + TraceEvent + TransactionRecord
```

ReasonScript Runtime Core v0.1を次の組合せとして確定する。

```text
State-first Layered Hybrid Runtime
+
StateDelta Transaction Model
```

## 2. Deliverables

実装:

```text
HybridRuntime/src/transaction.rs
HybridRuntime/src/reason_ir.rs
```

検証:

```text
HybridRuntime/tests/runtime_api_phase_3_transaction_validation.rs
```

規範仕様:

```text
docs/Transaction_Protocol_Specification_v0.1.md
docs/ReasonScript_ABI_Specification_v0.1.md
```

## 3. Evaluation

Scoreは各項目5点、合計45点。

| Model | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | E9 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Immediate Commit | 5 | 1 | 1 | 1 | 3 | 2 | 2 | 2 | 2 | 19 |
| Staged Commit | 4 | 2 | 3 | 3 | 4 | 4 | 4 | 4 | 3 | 31 |
| StateDelta Transaction | 4 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 44 |
| Event Sourcing | 1 | 5 | 5 | 5 | 4 | 5 | 5 | 4 | 4 | 38 |

Model-CはStateSnapshot、TransitionSpec、StateDelta、Traceをそのまま利用でき、
MemorySpace参照、DBM plan、WorldModel effect、Tool resultを共通commit protocolへ
投影できる。Model-Dは監査性が高いが、projection、event migration、storageを
Phase 3 scopeへ持ち込むためv0.1では採用しない。

## 4. Invariant Results

| Invariant | Enforcement | Result |
|---|---|---|
| State変更はCommitのみ | PreparedDeltaはsnapshotのみ。mutationはStateKernel commit/rollback | PASS |
| Commit前Stateは不変 | prepare/validate testでcurrent state不変 | PASS |
| 全CommitがStateDelta生成 | commit returnと内部delta ledger | PASS |
| 全DeltaがTraceを持つ | commit内で同期記録、`validate_trace_consistency` | PASS |
| Rollbackは逆Delta | `StateKernel::rollback`で新規delta生成 | PASS |
| ExecutionPlan immutable | plan IDのみ参照、plan object非所有 | PASS |
| Constraint failure時Commit禁止 | Rejected candidateを`CommitNotAllowed` | PASS |
| State KernelだけがCommit可能 | TransactionKernel内部のStateKernelだけをmutation | PASS |
| StateDelta再利用禁止 | candidate commitとsource rollbackを一回に制限 | PASS |
| Transaction ID一意 | kernel内ID setで重複拒否 | PASS |

## 5. Validation Cases

Phase 3 test 9件:

- basic commit: PASS
- constraint rejection: PASS
- rollback: PASS
- trace consistency: PASS
- execution plan immutability: PASS
- multiple commit delta chain: PASS
- WorldModel transition: PASS
- Tool integration: PASS
- candidate / transaction / rollback reuse rejection: PASS

全Runtime test suiteもPASSした。

## 6. Compatibility

- MemorySpace: `ContextRef`や取得結果をproposed stateの根拠として使用できる。
- DBM: immutable ExecutionPlanの各stepを独立transactionとしてcommitできる。
- WorldModel: Transition effectを検証後、snapshot間のStateDeltaとして記録できる。
- LLM/Tool Runtime: tool result自体はstateを変更せず、検証済みcandidateだけをcommitする。
- ABI: `reason-ir/0.1`を維持し、transaction objectとoptional trace fieldを追加した。

## 7. Recommendation

Runtimeのstate-changing adapterは`TransactionKernel`以外へmutation handleを
公開しない。Graph Planner、Memory Adapter、Tool Adapter、SDKは
`PreparedDelta`の入力を生成するだけとする。

永続化、distributed transaction、event sourcingはPhase 3のcommit semanticsを
変更せず、TransactionRecord、StateDelta、Traceを保存する外部層として追加する。

