# ReasonScript Unified Execution Runtime Architecture v0.1 Specification

## English Specification

### 1. Overview and Architecture
The ReasonScript Unified Execution Runtime Architecture (RS-UERA-001 v0.1) defines a cohesive, local-first execution layer with physical separation of compute backends and deterministic cluster offloading.

The architecture is founded on the principle of **Logical Integration / Physical Separation**:
- **Unified Execution Orchestrator (UEO)**: Acts as the central coordination layer between the Compiler/Reason IR/ExecutionPlan and the runtime backends (`RuntimeReal`, `TensorRuntime`, `RuntimeComplex`, `ReasonUnitRuntime`, `ClusterRuntime`).
- **Local First Policy**: Workloads are categorized into `LOCAL`, `LOCAL_MONITORED`, or `CLUSTER_PLANNED` based on static `WorkloadEstimate` and dynamic `RuntimePressure`.
- **Safe Boundary Escalation**: Dynamic migration to cluster execution occurs only at explicit safe boundaries (layer/operation transitions), never midway through an instruction.
- **Deterministic Cluster Execution**: Canonical partitioning, worker assignment, and reduction order guarantee byte-identical outputs across multiple independent executions.

### 2. Validation Matrix (UERA-T001 - UERA-T025)

| ID | Category | Description | Acceptance Criteria |
|---|---|---|---|
| **UERA-T001** | Capabilities | Runtime capability catalog enumeration | All local and cluster backends expose structured `RuntimeCapability` |
| **UERA-T002** | Transparency | Logical backend vs execution engine | Logical backend IDs (e.g. `RuntimeReal`) and engines (e.g. `rust`) are transparently separated |
| **UERA-T003** | Interface | Common execution request interface | Standard `ExecutionRequest` is accepted and executed consistently across local backends |
| **UERA-T004** | Error Handling | Structured request validation | Malformed requests are rejected with `UER-REQ-002` error |
| **UERA-T005** | Numerics | Numeric promotion and scalar casting | Mixed integer/float operations promote deterministically |
| **UERA-T006** | Types | Tensor type propagation in expressions | Tensor element types and dimensions propagate correctly through IR |
| **UERA-T007** | Memory | Tensor deterministic last-use release | Intermediate tensors are released immediately after last use |
| **UERA-T008** | Memory | Persistent and parameter tensor preservation | Model parameters and persistent states are protected from early release |
| **UERA-T009** | Compiler | Workload estimation from Reason IR | Compiler derives `WorkloadEstimate` and capability requirements without backend coupling |
| **UERA-T010** | Placement | Placement decision and reason recording | Orchestrator selects `LOCAL`, `LOCAL_MONITORED`, or `CLUSTER_PLANNED` and logs rationale |
| **UERA-T011** | Boundary | Safe boundary migration constraint | Instruction-level mid-operation migration is strictly prohibited |
| **UERA-T012** | Escalation | Dynamic escalation under pressure | Elevated pressure triggers cluster offload only at operation/layer boundaries |
| **UERA-T013** | Partitioning | Canonical cluster partition determinism | 3 isolated runs produce byte-identical cluster partition manifests |
| **UERA-T014** | Resilience | Worker availability and canonical fallback | Offline workers fall back deterministically to available nodes |
| **UERA-T015** | Parity | Cluster worker execution parity | Cluster execution yields results semantically identical to local backends |
| **UERA-T016** | Reduction | Deterministic canonical reduction | Reduction follows partition sequence, not asynchronous completion order |
| **UERA-T017** | Recovery | Explicit cluster failure recovery policies | `FALLBACK_LOCAL`, `RETRY`, and `FALLBACK_SINGLE_NODE` execute and trace correctly |
| **UERA-T018** | Safety | No silent fallback on abort | `ABORT` policy halts execution with diagnostic `UER-OFF-002` |
| **UERA-T019** | Optimization | Pure function inlining and constant folding | Pure Reason functions are inlined and constant-folded deterministically |
| **UERA-T020** | Performance | Relation Matrix execution optimization | Transformer Relation Matrix executes within latency and determinism targets |
| **UERA-T021** | Parser | Multiline parenthesized expression support | Parser accepts expressions split across multiple lines within parentheses |
| **UERA-T022** | Parser | Multiline function signature support | Parser accepts function declarations with multiline parameter lists |
| **UERA-T023** | Load Fixtures | Small/Medium/Large/Overload offload matrix | Orchestrator routes each workload fixture according to policy thresholds |
| **UERA-T024** | Regression | Transformer and Sparse Routing regression | Training, autograd, optimizer, and routing maintain baseline contracts |
| **UERA-T025** | Determinism | End-to-end 3-run byte-identical verification | 3 independent end-to-end runs produce byte-identical serialized JSON artifacts |

---

## 日本語仕様書 (Japanese Specification)

### 1. 概要とアーキテクチャ
ReasonScript Unified Execution Runtime Architecture (RS-UERA-001 v0.1) は、計算バックエンドの物理的分離と決定論的分散オフロードを備えた、ローカルファーストな統合実行レイヤーを定義します。

本アーキテクチャは **Logical Integration / Physical Separation（論理的統合・物理的分離）** の原則に基づきます：
- **Unified Execution Orchestrator (UEO)**: コンパイラ/Reason IR/ExecutionPlan と各実行バックエンド（`RuntimeReal`, `TensorRuntime`, `RuntimeComplex`, `ReasonUnitRuntime`, `ClusterRuntime`）を結ぶ中央調停レイヤー。
- **Local First Policy（ローカルファースト方針）**: 静的負荷推定（`WorkloadEstimate`）および動的圧力（`RuntimePressure`）に基づき、ワークロードを `LOCAL`、`LOCAL_MONITORED`、`CLUSTER_PLANNED` に分類・配置。
- **Safe Boundary Escalation（安全境界エスカレーション）**: クラスタへの動的移行はレイヤーやオペレーションの安全境界でのみ発生し、命令実行の途中での任意マイグレーションは禁止。
- **Deterministic Cluster Execution（決定論的クラスタ実行）**: 正準パーティショニング、正準ワーカー割り当て、正準リダクション順序により、3回以上の独立実行で byte-identical な完全再現性を保証。

### 2. 検証マトリクス (UERA-T001 〜 UERA-T025)

| ID | カテゴリ | 検証項目 | 受入基準 |
|---|---|---|---|
| **UERA-T001** | 機能情報 | ランタイム機能カタログの列挙 | 全バックエンドが構造化された `RuntimeCapability` を公開すること |
| **UERA-T002** | 透明性 | 論理バックエンドと実行エンジンの分離 | 論理名（`RuntimeReal`等）と実行基盤（`rust`等）が分離されていること |
| **UERA-T003** | 共通IF | 共通実行リクエストインターフェース | 共通 `ExecutionRequest` が全ローカルランタイムで整合して実行されること |
| **UERA-T004** | 異常系 | 不正リクエストの検証と拒否 | 不正なリクエストに対して `UER-REQ-002` エラーを返却すること |
| **UERA-T005** | 数値型 | 数値型昇格とスカラーキャスト | 整数と浮動小数点の混合演算で決定論的に型昇格すること |
| **UERA-T006** | 型推論 | 式におけるTensor型伝播 | テンソルの要素型と形状がIRを通じて正しく伝播すること |
| **UERA-T007** | メモリ | テンソルの決定論的 last-use 解放 | 中間テンソルが最終使用直後に即時解放されること |
| **UERA-T008** | メモリ | パラメータおよび永続テンソルの保護 | モデルパラメータや永続テンソルが早期解放されないこと |
| **UERA-T009** | コンパイラ | Reason IR からの負荷推定 | コンパイラがバックエンド非依存で `WorkloadEstimate` と要求機能を生成すること |
| **UERA-T010** | 配置判断 | 配置判断と選択理由の記録 | UEOが `LOCAL`/`LOCAL_MONITORED`/`CLUSTER_PLANNED` を選定し理由を記録すること |
| **UERA-T011** | 安全境界 | 命令途中での非マイグレーション制約 | オペレーション/命令の実行途中でのクラスタ移行を行わないこと |
| **UERA-T012** | エスカレーション | 高負荷時の動的エスカレーション | 圧力上昇時にオペレーション/レイヤー境界でクラスタへ移行すること |
| **UERA-T013** | 分割 | 正準クラスタパーティションの決定論性 | 3回の独立実行でクラスタ計画マニフェストが byte-identical であること |
| **UERA-T014** | 障害耐性 | ワーカー稼働状況と正準フォールバック | 停止ワーカーが利用可能ノードへ決定論的にフォールバックすること |
| **UERA-T015** | パリティ | クラスタワーカー実行の等価性 | クラスタ実行結果がローカルバックエンドの実行結果と等価であること |
| **UERA-T016** | 集約 | 正準順序による決定論的リダクション | 完了順ではなく正準パーティション順序に従って結果を集約すること |
| **UERA-T017** | 復旧 | 明示的なクラスタ障害ポリシーの実行 | `FALLBACK_LOCAL`, `RETRY`, `FALLBACK_SINGLE_NODE` が正確にトレースされること |
| **UERA-T018** | 安全性 | Abort時の暗黙フォールバック抑止 | `ABORT` ポリシーで暗黙フォールバックせず `UER-OFF-002` を送出すること |
| **UERA-T019** | 最適化 | 純粋関数のインライン化と定数畳み込み | 純粋 Reason 関数がインライン化・定数畳み込みされ決定論性が維持されること |
| **UERA-T020** | 性能 | Relation Matrix 実行の最適化 | Transformer Relation Matrix がレイテンシ目標と決定論性を満たすこと |
| **UERA-T021** | 構文解析 | 括弧内の複数行式のパース対応 | 括弧内で改行された式を正常にパースできること |
| **UERA-T022** | 構文解析 | 複数行の関数シグネチャのパース対応 | 引数リストが改行された関数定義を正常にパースできること |
| **UERA-T023** | 負荷マトリクス | Small/Medium/Large/Overload 配置検証 | 各種負荷フィクスチャがポリシー閾値に従って正しく配置されること |
| **UERA-T024** | 回帰 | TransformerおよびSparse Routing回帰 | 学習・autograd・optimizer・routing の既存契約が完全に維持されること |
| **UERA-T025** | 決定論性 | E2E 3回独立実行の byte-identical 検証 | 3回の独立実行結果が byte-identical（完全一致）すること |
