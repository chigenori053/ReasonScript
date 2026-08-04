# World Model SDK Phase 1 Specification

Status: Implemented

Version: world-model-sdk/0.1

World Model SDK Phase 1 supersedes `world-sdk/0.1` and introduced the first
Runtime-compatible WorldModel core on top of the existing ReasonGraph,
ExecutionPlan, and Runtime SDK layers.

World Model SDK Phase 2 extends this core to `world-model-sdk/0.2` with
geometry, transform trees, spatial relations, deterministic layout, hierarchy
validation, and spatial serialization fields.

World Model SDK Phase 3 extends the SDK to `world-model-sdk/0.3` with
scene templates, deterministic object and relation inference, recoverable
completion, reconstruction traces, and evidence serialization.

## Scope

World SDK Phase 1 supports:

- World
- Scene
- Entity
- Object
- Transform
- Relation
- Event
- Simulation
- Snapshot

## API Surface

The Python SDK is exposed as `sdk.world`.

Core construction APIs:

- `create_world`
- `create_scene`
- `create_entity`
- `create_object`
- `create_transform`
- `create_relation`
- `create_event`

Core mutation APIs return new immutable values:

- `add_scene`
- `add_entity`
- `add_object`
- `add_relation`
- `add_event`
- `add_snapshot`
- `replace_scene`

Core execution APIs:

- `validate`
- `validate_scene`
- `validate_event`
- `validate_transform`
- `snapshot`
- `simulate`
- `to_json`
- `runtime_value`

## Determinism

World SDK values are immutable dataclasses. Simulation processes pending events
in deterministic `(tick, id)` order and produces serializable snapshots using
the `world-model-sdk/0.1` schema marker.

## Event Semantics

Phase 1 simulation supports deterministic processing for:

- `move`
- `modify`
- `destroy`
- `interact`
- `create`

`move`, `modify`, `destroy`, and `create` update world state. `interact`
participates in deterministic traces without changing state.

## Validation

Validation checks:

- World schema version
- Scene identity uniqueness
- Entity and object identity uniqueness inside scenes
- Transform vector shape
- Relation endpoint existence
- Event target existence

Conformance tests live in `world_sdk_phase1_tests/`.
