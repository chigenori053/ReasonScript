# WorldModel

The WorldModel (World SDK) is a Python SDK, `sdk/world/`, for building,
querying, validating, and simulating spatial/semantic scenes on top of the
ReasonScript runtime. Unlike [Cluster Runtime](cluster-runtime.md), this is
a real, implemented, versioned subsystem (`world-model-sdk/0.1`, extended
through `0.3`). Status: **Partially Complete** per
`docs/platform_architecture_review/world_model_sdk_review.md`.

Normative spec:
[World_SDK_Phase_1_Specification.md](../specifications/World_SDK_Phase_1_Specification.md).

## Layers

The SDK is organized in four layers, matching the roadmap phases in
[ROADMAP.md](../../ROADMAP.md):

### Core layer — `sdk/world/builder.py`

Immutable dataclasses and constructors for the base world model: `World`,
`Scene`, `WorldEntity`, `WorldObject`, `Transform`, `Relation`, `Event`,
`Snapshot`. Every mutation function (`add_scene`, `add_entity`,
`add_object`, `add_relation`, `add_event`, `add_snapshot`, `replace_scene`)
returns a **new** immutable value rather than mutating in place, consistent
with the platform's commit-only mutation invariant (see
[overview.md](overview.md#design-invariants)).

Supporting modules: `query.py` (read accessors — `entities`, `objects`,
`relations`, `scenes`, `snapshots`, id lookups) and `validation.py`
(`validate`, `validate_scene`, `validate_event`, `validate_transform` —
checks schema version, id uniqueness, transform vector shape, and that
relation/event targets exist).

### Spatial layer (Phase 2) — `sdk/world/spatial.py`

Geometry and transform hierarchies: `Geometry` class,
`create_geometry`/`validate_geometry`, `add_spatial_relation`,
`attach_child`/`set_parent` for parent-child transform trees,
`validate_hierarchy`, deterministic layout solving
(`solve_layout`/`apply_constraint_layout`), `world_transform`/
`local_transform`, and `detect_conflicts`.

### Semantic layer (Phase 3) — `sdk/world/semantic.py`

Scene reconstruction: `SceneTemplate`, `ReconstructionTrace`,
`ReconstructionResult`; `create_template`/`match_template`,
`infer_objects`/`infer_relations`, `recover_structure`/
`reconstruct_scene`/`reconstruct_world`, `validate_semantic_consistency`,
`evidence`.

### Simulation layer — `sdk/world/simulation.py`

The largest module (~870 lines): `StateDelta`, `WorldDelta`,
`CompositeTransition`, `SimulationTrace`, `BranchSimulation`,
`WorldSimulationResult`; `generate_delta`, `simulate_step`,
`simulate_until`, `apply_delta`, `replay`, `simulate_branch`. Events are
processed deterministically in `(tick, id)` order, for event types `move`,
`modify`, `destroy`, `interact`, `create`.

### Supporting modules

- `serialization.py` — `to_json` and JSON round-tripping.
- `metadata.py` — world-model metadata injection.
- `runtime.py` — `runtime_value` bridge into the Runtime SDK
  (`sdk/runtime/`).

## Example Shape

```python
from sdk.world import builder

world = builder.create_world()
scene = builder.create_scene(scene_id="scene-1")
world = builder.add_scene(world, scene)

entity = builder.create_entity(entity_id="e1", kind="Object")
world = builder.add_entity(world, "scene-1", entity)
```

(Every call returns a new `World` value; nothing here mutates `world` or
`scene` in place.)

## Known Gaps

From the architecture review (`world_model_sdk_review.md`):

- Trace concepts are duplicated across simulation, reconstruction, runtime,
  and the `ExecutionCoordinator` — a shared trace envelope is needed (this
  is also the motivation for the platform-wide `ReasoningTrace` proposal
  tracked in [ROADMAP.md](../../ROADMAP.md)).
- The Planning/Agent layers should integrate through `ExecutionCoordinator`
  rather than mutating runtime state directly.
- No adapter yet connects WorldModel traces into a platform-wide
  `ReasoningTrace` schema.

## Testing

Conformance tests: `world_sdk_phase1_tests/`.
