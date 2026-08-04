# ReasonScript Semantic Visualization Runtime Rust Design v0.1

Specification ID: `reasonscript-semantic-visualization-runtime/0.1`
Status: IN_PROGRESS — Milestone 1 IMPLEMENTED
Target: ReasonScript 0.6 experimental optional runtime
Implementation language: Safe Rust (Rust 2021 or later)

## 1. Decision

ReasonScriptにVisualization Runtimeを追加する。ただし、その正規責務は画像生成ではなく、ReasonScriptが保持する意味構造、空間構造、証拠、不確実性、推論経路、状態遷移を、決定論的で監査可能なCanonical Visualization IRへ投影することである。

v0.1は次を実装対象とする。

- RUO、3DRUO、VisionObservation、World StateからSemantic Sceneを構築する
- 2D、簡易3D、関係、証拠、推論状態、時系列を表現する
- Sceneの原子的更新、差分、Snapshot、Rollback、Replayを提供する
- Canonical Visualization IR、Render Plan、Evidence、Validation、Manifestを生成する
- SVGを決定論検証用Reference Adapterとして提供する
- 外部Renderer向けのAdapter契約を提供する

次はRuntime本体へ実装しない。

- Rasterizer、GPU command queue、Shader compiler
- PBR、Ray Tracing、Global Illumination
- Texture生成、Rigging、Physics、Particle、Fluid
- 頂点編集、UV編集、SculptなどのモデリングUI
- Game loopまたは汎用Game Engine
- 見た目の自然さを判定する推論アルゴリズム

フル機能3D Rendererは、ReasonScript言語処理系ではなく、ReasonScript上で構築される可視化対応推論システムのBackendとする。

## 2. 設計根拠

VisionWorldModelの処理は概ね次の経路を持つ。

```text
Image
  -> Observation
  -> Semantic Analysis
  -> Primitive Construction
  -> Geometry / Topology
  -> Structural Completion
  -> 3DRUO
  -> VisionWorldModel
```

JSONや数値検証だけでは、左右反転、不自然な包含、奥行き矛盾、過剰補完、局所的に正しいが全体として破綻した形状を見落としやすい。Visualization Runtimeは構造検証の代替ではなく、構造検証と併用する監査投影基盤である。

本設計は既存資産を置換しない。

- `runtime.visualization`のVisualization Standard Library v0.1は、表形式データとチャートのPython APIとして維持する
- `VisionRuntime`はObservationからRUOを生成するRust境界として維持する
- 新RuntimeはSemantic Sceneと状態投影を担当し、両者から利用可能な別プロファイルとする
- 既存の`reasonscript-visualization-ir/0.1`と非互換な構造を同じSchema IDで再定義しない

## 3. アーキテクチャ境界

```text
ReasonScript Program / Reasoning System
  -> Projection Request
  -> Semantic Visualization Runtime (Rust)
       -> Source Adapter
       -> Projection Engine
       -> Scene Kernel
       -> Transaction / Patch / Timeline
       -> Canonicalizer / Validator
       -> Artifact Writer
  -> Canonical Semantic Visualization IR
  -> Renderer Adapter
       -> SVG Reference Adapter
       -> Web / WebGPU Adapter
       -> Blender Adapter
       -> Godot Adapter
       -> OpenUSD / CAD Adapter
```

Runtimeの正規結果は`SceneSnapshot`とCanonical IRであり、PNG、画面、Blender Sceneなどは派生成果物である。Backend固有出力の差異はCanonical IRの同一性を損なってはならない。

### 3.1 Runtimeが保証すること

- Source identity、provenance、evidence、confidence、semantic stateの保存
- 座標系、Geometry、Transform、Camera、Layer、Relation、Timelineの共通型
- 同一入力と同一Profileから同一バイト列を得る決定論的投影
- 検証前のSceneを公開しない原子的更新
- Resource budget、Capability、外部Resource参照の検証
- Renderer非依存のRender PlanとAdapter要求

### 3.2 上位推論システムが決定すること

- 最適視点、Occlusion解釈、構造補完
- Material、Lighting、Animation、物理表現
- 何を強調し、どのCamera候補を選択するか
- 視覚的妥当性の評価

Runtimeは候補、評価値、選択結果を表現できるが、推論方針を固定しない。

## 4. Rust Workspace案

初期実装は独立crate `VisualizationRuntime`とし、成熟後に共通Runtime Coreを抽出する。

```text
VisualizationRuntime/
  Cargo.toml
  src/
    lib.rs
    model.rs          # Scene、Object、Geometry、Camera、Layer、Timeline
    source.rs         # RUO / Vision / World Stateの入力境界
    projection.rs     # Source -> Scene proposal
    kernel.rs         # authoritative current Scene
    transaction.rs    # prepare / validate / commit / rollback
    patch.rs          # SceneDiffと適用
    canonical.rs      # 並び順、数値正規化、canonical JSON、digest
    validation.rs     # structural / semantic / evidence検証
    budget.rs         # resource limits
    capability.rs     # adapterと外部Resource権限
    artifacts.rs      # artifact set、manifest、checksum
    diagnostics.rs    # SVR-* diagnostics
    adapter.rs        # RendererAdapter trait
    svg.rs            # deterministic reference adapter
    replay.rs         # snapshot / seek / replay
    main.rs           # reason-visualization-runtime
  tests/
    conformance.rs
    determinism.rs
    transaction.rs
    svg_golden.rs
```

推奨する初期依存は`serde`、`serde_json`、`sha2`である。行列計算やScene Graphのために大規模な描画Frameworkへ依存しない。必要なら`thiserror`を診断実装の補助に限定して採用する。

## 5. Core Data Model

### 5.1 Scene

```rust
pub struct VisualizationScene {
    pub schema_version: String,
    pub scene_id: SceneId,
    pub revision: u64,
    pub source: SourceDescriptor,
    pub coordinate_systems: BTreeMap<CoordinateSystemId, CoordinateSystem>,
    pub layers: BTreeMap<LayerId, VisualizationLayer>,
    pub objects: BTreeMap<ObjectId, VisualizationObject>,
    pub relations: BTreeMap<RelationId, VisualizationRelation>,
    pub cameras: BTreeMap<CameraId, VisualizationCamera>,
    pub timeline: Option<VisualizationTimeline>,
    pub profile: OutputProfile,
    pub extensions: BTreeMap<String, serde_json::Value>,
}
```

SceneのRust内部表現は`BTreeMap`を用いる。配列へSerializeする場合も、明示的な`order`、安定ID、IDの辞書順で順序を確定する。HashMapのiteration orderをCanonical出力へ使用しない。

### 5.2 Objectと意味状態

```rust
pub struct VisualizationObject {
    pub object_id: ObjectId,
    pub source_ref: SourceRef,
    pub parent_id: Option<ObjectId>,
    pub layer_ids: BTreeSet<LayerId>,
    pub geometry: Vec<GeometryInstance>,
    pub semantic_state: SemanticState,
    pub appearance: SemanticAppearance,
    pub evidence_refs: BTreeSet<EvidenceId>,
    pub confidence: Option<Confidence>,
    pub lifecycle: LifecycleState,
    pub revision: u64,
}

pub enum SemanticState {
    Observed,
    Inferred,
    Predicted,
    Unknown,
    Conflicted,
    Invalid,
    Inactive,
    Selected,
    Changed,
    Historical,
}
```

`Selected`や`Changed`は本来、Observedなどと直交する表示状態である。このため実装時は次の3軸へ分離する。

- `epistemic_state`: observed / inferred / predicted / unknown / conflicted
- `validity_state`: valid / invalid
- `interaction_state`: normal / inactive / selected / changed / historical

上記`SemanticState`は概念一覧であり、単一enumへ押し込まない。

### 5.3 Geometry

v0.1の正規Primitiveは次とする。

```text
Point2, Point3
Line2, Line3
Polyline2, Polyline3
Bezier2, Bezier3
Polygon2, Polygon3
Circle, Ellipse
Plane
BoundingBox2, BoundingBox3
Sphere, Cylinder
Mesh
Trajectory2, Trajectory3
LabelAnchor
```

すべてのGeometryは次を持つ。

```rust
pub struct GeometryInstance {
    pub geometry_id: GeometryId,
    pub source_ref: Option<SourceRef>,
    pub coordinate_system_id: CoordinateSystemId,
    pub primitive: GeometryPrimitive,
    pub transform: Transform3,
    pub semantic_role: GeometryRole,
    pub evidence_refs: BTreeSet<EvidenceId>,
    pub confidence: Option<Confidence>,
}
```

Meshの大規模vertex/index列は、Canonical IRへ無制限にinline化しない。小規模Meshはinline、大規模MeshはSHA-256 digestを持つProject-root内Resourceとして参照する。Resourceのbyte order、scalar type、shape、index baseを明示する。

### 5.4 Coordinate SystemとTransform

座標系は暗黙にしない。

```text
handedness: right | left
up_axis: x | y | z
units: normalized | pixel | millimeter | meter | custom
origin: explicit vector
source_frame_ref: optional
```

Transformの合成順序は`parent_world * local`に固定する。Matrixはrow-majorまたはcolumn-majorの一方をSchemaで固定し、Adapter側の推測を禁止する。v0.1ではrow-major 4x4、column vector、右から適用を推奨する。

### 5.5 Camera

```rust
pub enum Projection {
    Orthographic { width: FiniteF64, height: FiniteF64 },
    Perspective { vertical_fov_radians: FiniteF64, near: PositiveF64, far: PositiveF64 },
}

pub struct VisualizationCamera {
    pub camera_id: CameraId,
    pub transform: Transform3,
    pub projection: Projection,
    pub viewport: Viewport,
    pub visibility: VisibilityPolicy,
    pub score: Option<FiniteF64>,
    pub selected: bool,
}
```

Reference SVG Adapterはv0.1でOrthographicを必須対応とする。PerspectiveはIRと検証を必須とし、SVG投影対応はMilestone 2とする。Camera選択の同点はscore降順、camera ID昇順で解決する。

### 5.6 Layer、Relation、Evidence

標準Layer roleは次とする。

```text
geometry
topology
semantics
relations
evidence
confidence
inference
diagnostics
state_transition
annotation
```

Relationは単なる線ではなく、source object、target object、relation kind、direction、evidence、confidenceを保持する。Adapterは`relation_edge`へ投影できるが、正規意味はScene側に残る。

Evidenceは最低限、`evidence_id`、`source_artifact_ref`、`source_element_ref`、`observation_id`、`model_provenance`、`claim`、`confidence`を持つ。StyleだけでObservedとInferredを表し、IRから根拠を失うことは禁止する。

### 5.7 Semantic Appearance

AppearanceはRenderer非依存の意味指定であり、PBR Materialではない。

```rust
pub struct SemanticAppearance {
    pub color_role: ColorRole,
    pub surface_class: SurfaceClass,
    pub opacity: UnitInterval,
    pub emphasis: Emphasis,
    pub line_role: LineRole,
    pub label_policy: LabelPolicy,
    pub renderer_extensions: BTreeMap<String, serde_json::Value>,
}
```

標準ProfileはSemantic StateからAppearanceを決定論的に解決する。例としてObservedは実線、Inferredは破線、Unknownは低opacity、Conflictedは警告色、Invalidは診断overlayとする。色だけに依存せず、線種、label、patternを併用する。

## 6. Source Projection Contract

Source Adapterは入力を直接commitせず、`SceneProposal`を返す。

```rust
pub trait SceneProjector<S> {
    fn profile(&self) -> &'static str;
    fn project(
        &self,
        source: &S,
        goal: &VisualizationGoal,
        context: &ProjectionContext,
    ) -> Result<SceneProposal, VisualizationError>;
}
```

v0.1で用意するProjectorは次とする。

- `VisionObservationProjector`: bounding box、center、class、confidence、track relation
- `RuoProjector`: AtomicReasonUnit、relation、state、evidence
- `ThreeDRuoProjector`: Geometry、Topology、completion state、front/side/top view
- `WorldStateProjector`: versioned state、dependency、change、lifecycle
- `TraceProjector`: reasoning stageをTimeline frameへ投影

Source Adapterが意味を推測して捏造することは禁止する。Sourceに存在しない推論結果は、明示的な推論操作とprovenanceを持つ上位システムだけが追加できる。

## 7. Scene KernelとTransaction

Scene Kernelだけがcurrent Sceneを変更できる。既存Transaction Protocolと同じPrepare、Validate、Commit、Rollback原則を採用する。

```text
visualization.begin
  -> SceneProposal
  -> prepare(ScenePatch)
  -> validate(structure, reference, semantic, evidence, budget, capability)
  -> commit
  -> SceneSnapshot(revision + 1)
```

### 7.1 Patch操作

```rust
pub enum PatchOperation {
    AddObject(VisualizationObject),
    UpdateObject { object_id: ObjectId, expected_revision: u64, value: VisualizationObject },
    RemoveObject { object_id: ObjectId, expected_revision: u64 },
    AddRelation(VisualizationRelation),
    UpdateRelation { relation_id: RelationId, expected_revision: u64, value: VisualizationRelation },
    RemoveRelation { relation_id: RelationId, expected_revision: u64 },
    SetLayerVisibility { layer_id: LayerId, visible: bool },
    SetCamera { camera_id: CameraId },
    AppendFrame(TimelineFrame),
}
```

Patchは`base_scene_id`、`base_revision`、`patch_id`、ordered operations、source transaction IDを持つ。参照revisionが一致しない更新は拒否する。

### 7.2 Commit不変条件

- object、geometry、relation、layer、camera IDが一意
- parent graphがacyclic
- 全参照先が存在する
- GeometryとTransformの数値がfinite
- confidenceが`[0, 1]`
- Camera near/far、viewport、projectionが有効
- Source identityとEvidence参照が追跡可能
- Resource budgetを超過しない
- Adapter capabilityが許可される
- current revisionがprepared patchのbase revisionと一致する

Commit失敗時はScene、ledger、traceを変更しない。Rollbackは過去状態への破壊的巻き戻しではなく、逆Patchを新revisionとしてcommitする。

## 8. Diff、Partial Update、Timeline、Replay

`diff(A, B)`は安定ID単位で最小の意味差分を生成する。byte-level JSON差分は正規契約にしない。

```text
World State Change
  -> Dependency Analysis
  -> Affected SourceRefs
  -> Re-project affected Visualization Objects
  -> ScenePatch
  -> validate
  -> atomic commit
  -> AdapterPatch
```

TimelineはAnimation Editorではなく推論再現機能である。

```text
Frame 0 Observation
Frame 1 Primitive recognition
Frame 2 Semantic component construction
Frame 3 Topology
Frame 4 Structural completion
Frame 5 3DRUO publication
```

各Frameはfull Sceneを複製せず、基準Snapshot IDとPatch IDを参照できる。一定間隔でcheckpoint Snapshotを置き、`seek`時のPatch適用数を制限する。

標準操作は`create_scene`、`project`、`prepare`、`validate`、`commit`、`snapshot`、`diff`、`apply`、`rollback`、`seek`、`replay`、`serialize`とする。

## 9. CanonicalizationとDeterminism

Canonical IRは同一の入力bytes、Projection Profile、Runtime version、Resource digestsから同一bytesを生成しなければならない。

固定事項:

- IDはcontent-derived SHA-256またはSource stable IDから導出し、random UUIDを禁止
- Map key、Object、Layer、Geometry、Relation、Evidence、Frameの順序を明示
- JSON object keyは辞書順
- UTF-8、LF、末尾改行あり
- NaN、Infinity、negative zeroを禁止
- 数値は入力時にfinite validationし、Canonical Profile指定精度へ量子化
- 単位と座標系を明示し、暗黙変換を禁止
- Camera同点、Style cascade、extension namespaceの解決順を固定
- Timestampは意味入力に含まれる場合だけ保存し、実行時wall clockをcanonical artifactへ混入しない
- Renderer生成画像のdigestは派生成果物として記録し、Canonical IR identityへ含めない

推奨量子化はworld coordinate `1e-9`、screen coordinate `1e-6 pixel`である。ただし初期実装前に既存RUO Geometryの精度契約と整合させ、Profileとして固定する。

## 10. Renderer Adapter Contract

```rust
pub trait RendererAdapter {
    fn descriptor(&self) -> AdapterDescriptor;
    fn capabilities(&self) -> CapabilitySet;
    fn validate(&self, scene: &CanonicalScene) -> Vec<Diagnostic>;
    fn render(
        &self,
        scene: &CanonicalScene,
        plan: &RenderPlan,
        sink: &mut dyn ArtifactSink,
    ) -> Result<RenderResult, VisualizationError>;
    fn apply_patch(
        &mut self,
        patch: &CanonicalScenePatch,
    ) -> Result<AdapterRevision, VisualizationError>;
}
```

Capability例:

```text
geometry.2d
geometry.3d
projection.orthographic
projection.perspective
timeline
partial_update
labels
external_resource.read
output.svg
output.raster
interactive
```

Runtimeは要求CapabilityとAdapter capabilityを照合する。未対応Primitiveを黙って欠落させず、Profileで許可されたfallbackへ変換するか`SVR-ADP-002`で拒否する。

Renderer extensionはreverse-domain形式などのnamespace付きkeyに限定し、Core fieldを上書きできない。外部process、network、project root外fileへのアクセスは明示Capabilityなしに許可しない。

## 11. SVG Reference Adapter

SVG Adapterは美麗な描画ではなく、決定論、Golden diff、ブラウザ表示、監査を目的とする。

v0.1必須対応:

- Point、Line、Polyline、Bezier2、Polygon、Circle、Ellipse、BoundingBox2
- Label、Relation edge
- Orthographic camera
- Layer groupとvisibility
- Observed / Inferred / Unknown / Conflicted / Invalidの標準Style
- Evidence IDとSourceRefを`data-*`属性として保持
- 安定したelement順、属性順、数値format

3D PrimitiveはCameraによる2D投影後に描画する。Hidden-surface removalはv0.1必須ではない。Mesh wireframe、front/side/top正投影を最初の3D監査表現とする。

SVG内へ任意script、外部URL、未検証font、任意XMLを注入することは禁止する。LabelはXML escapeする。

## 12. Artifact Contract

1 runの必須成果物は次とする。

```text
visualization_manifest.json
visualization_source.json
visualization_scene.json
visualization_render_plan.json
visualization_evidence.json
visualization_trace.json
visualization_validation.json
visualization_run_summary.json
scene.svg
```

Schema ID:

```text
reasonscript-semantic-visualization-manifest/0.1
reasonscript-semantic-visualization-source/0.1
reasonscript-semantic-visualization-ir/0.1
reasonscript-semantic-visualization-render-plan/0.1
reasonscript-semantic-visualization-evidence/0.1
reasonscript-semantic-visualization-trace/0.1
reasonscript-semantic-visualization-validation/0.1
reasonscript-semantic-visualization-run-summary/0.1
```

既存Visualization Standard Libraryの`visualization_ir.json`と混同しないため、Schema IDでは`semantic-visualization`を必須とする。導入時にファイル名も`semantic_visualization_scene.json`へ変更する選択肢をSchema策定段階で決定する。

Manifestは各成果物の相対path、media type、schema version、byte size、SHA-256 checksum、required flagを持つ。正規成果物と派生成果物を区別する。

## 13. Diagnostics

診断code prefixは`SVR`とする。

| Code | 意味 |
|---|---|
| `SVR-SRC-001` | Source profileまたはprovenance不正 |
| `SVR-ID-001` | ID重複または不安定ID |
| `SVR-REF-001` | 未解決参照 |
| `SVR-GEO-001` | Geometry不正 |
| `SVR-NUM-001` | 非finiteまたは範囲外数値 |
| `SVR-SCN-001` | Scene graph cycleまたは構造不正 |
| `SVR-EVD-001` | Evidence不整合 |
| `SVR-TXN-001` | Transaction precondition失敗 |
| `SVR-PAT-001` | Patch revision競合 |
| `SVR-DET-001` | 決定論違反 |
| `SVR-RES-001` | Resource budget超過 |
| `SVR-CAP-001` | Capability拒否 |
| `SVR-ADP-001` | Adapter unavailable |
| `SVR-ADP-002` | Adapter capability不足 |
| `SVR-ART-001` | Artifact pathまたはchecksum不正 |

診断順はcode、location、source ref、messageで安定sortする。

## 14. Resource Budgetと安全性

Default Profileは少なくとも次の上限を持つ。

```text
max_objects
max_geometry_instances
max_vertices
max_relations
max_evidence_records
max_frames
max_patch_operations
max_inline_resource_bytes
max_total_artifact_bytes
max_projection_depth
max_label_bytes
```

具体値は実装前benchmarkで決定し、Artifactへ記録する。上限超過時に自動samplingして意味を変えず、fail closedまたは明示されたLevel-of-Detail Profileへ切り替える。

Path traversal、symlink escape、絶対path、digest不一致、巨大Resource、圧縮爆弾、script付きSVG、未許可network accessを拒否する。Artifact出力先はproject root配下へ制限する。

## 15. Public APIとCLI案

ReasonScript namespace案:

```text
visualization.create_scene
visualization.project
visualization.add
visualization.remove
visualization.update
visualization.validate
visualization.snapshot
visualization.diff
visualization.apply
visualization.rollback
visualization.seek
visualization.replay
visualization.serialize
visualization.render
```

CLI案:

```text
reason visualization project <source.json> --source-profile <profile> --output <dir> --json
reason visualization validate <scene.json> --json
reason visualization render <scene.json> --adapter svg --output <dir> --json
reason visualization diff <before.json> <after.json> --json
reason visualization replay <trace.json> --frame <n> --adapter svg --output <dir> --json
```

言語統合前はRust CLIを直接conformance harnessから実行し、契約が安定してから`reason` dispatcherへ追加する。

## 16. 導入ロードマップ

### Milestone 0: Specification freeze

- Core Schema、ID、数値精度、座標系、Artifact名を確定
- 既存Visualization Standard Libraryとのcompatibility matrixを確定
- VisionObservation人物fixtureと簡易3DRUO fixtureを追加

Exit criteria: Schema validationとGolden fixture設計がreview済み。

### Milestone 1: 2D Semantic Audit MVP

- Rust crate、Core model、validator、canonical JSON
- VisionObservation / RUO projector
- Transaction、Snapshot、Diff
- SVG Reference Adapter
- `person_structure.svg`を生成

表示内容はHead、Torso、左右Arm、左右Leg、bounding box、centroid、label、relation、confidence、Observed/Inferredの差とする。

Exit criteria: 同一fixtureを3回実行してCanonical IRとSVGがbyte-identical。

Implementation status: IMPLEMENTED. `VisualizationRuntime` provides the
safe-Rust Core model, semantic-input and VisionObservation projectors, Scene
validation, transactional Patch commit/rollback, deterministic SVG Reference
Adapter, artifact manifest/checksums, `reason visualization` CLI integration,
and the person-structure conformance fixture. The currently supported Geometry
is `BoundingBox2`, which is the required audit primitive for this milestone.

### Milestone 2: 3DRUO Orthographic Projection

- Point3、Line3、BoundingBox3、Mesh wireframe
- Transform hierarchy
- front、side、top camera
- `front.svg`、`side.svg`、`top.svg`
- Geometry、Topology、Evidence、Inference layer

Exit criteria: 3面図の構造Golden、参照完全性、projection determinismがpass。

### Milestone 3: Transactional Timeline

- Patch、atomic commit、rollback
- Timeline checkpoint、seek、replay
- reasoning stage別SVG frame
- partial update対応

Exit criteria: 中間失敗でSceneが不変、rollback/replayで同一digestを再現。

### Milestone 4: External Adapter boundary

- Stable `RendererAdapter`
- Capability negotiation
- WebまたはBlender AdapterのPoCを別packageで実装
- Backend固有出力をCanonical identityから分離

Exit criteria: 同一IRをSVGと外部Adapterへ渡し、semantic/evidence参照が保持される。

## 17. Validation Plan

AGENTS.mdに従い、実装taskは次を実行する。

1. Workspace validation
2. Diagnostics validation
3. Artifact validation
4. Golden tests
5. `reason ci --json`

必須test:

- serde round-tripとSchema conformance
- duplicate ID、dangling ref、cycle、NaN、budget超過の拒否
- content-derived IDとcanonical JSONの3-run equality
- prepare時Scene不変、rejected commit時Scene不変
- commitの原子性、duplicate commit拒否、rollbackの新revision化
- Scene A -> diff -> apply == Scene B
- Timeline replayのdigest一致
- SVG XML escape、path traversal、external resource拒否
- VisionObservation人物構造Golden
- 3DRUO front/side/top Golden
- 既存Visualization、VisionRuntime、RUO、non-visualization Goldenの非回帰

画像pixel diffは正規判定に使用しない。正規判定はCanonical IR、Canonical SVG、構造的assertionで行う。

## 18. Compatibility Policy

- Optional Capabilityとし、Visualizationを使用しないprogramのParser、Reason IR、ExecutionPlan、Runtime結果を変更しない
- Python Visualization Standard Library v0.1の公開APIとArtifactを変更しない
- VisionRuntime v0.1のObservation/RUO contractを変更しない
- Renderer Adapterの追加はCore Schemaを変更しない
- Core field追加はminor profile、意味変更またはfield削除は新major profile
- Renderer extensionはnamespace分離し、未知extensionをCore validatorが意味解釈しない

## 19. Open Decisions

実装開始前に次をSpecification freezeで決定する。

1. Crateを独立配置するかCargo workspaceを新設するか
2. Semantic IR artifactのfile nameを既存`visualization_ir.json`と分離するか
3. Canonical floatをquantized decimal JSONとするかfixed-point integerとするか
4. Transform matrixの保存をmatrixのみ、TRSのみ、または検証付き併記とするか
5. 大規模Mesh resourceに既存RUO-T1 containerを再利用するか専用profileを作るか
6. 3DRUOの正式Source profileとSourceRef path grammar
7. Runtime CoreのTransaction実装を共有crateへ抽出する時期

推奨は、Milestone 1では独立crate、分離file name、quantized decimal、TRS正規保存、matrix派生、大規模Mesh対象外とし、共有Core抽出をMilestone 3以降に判断することである。

## 20. Completion Definition

v0.1は、人物構造fixture、3DRUO三面図fixture、推論Timeline fixtureをRust Runtimeへ入力し、意味・Evidence・Confidenceを保持したCanonical IRとCanonical SVGを決定論的に生成できるときに完成とする。

完成条件にフォトリアル画像、GPU描画、リアルタイム編集、Full 3D Rendererは含めない。
