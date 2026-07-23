# ReasonUnit Object

## A Note on Terminology

"ReasonUnit Object" is not a formally specified type in any normative
document under `docs/specifications/` — a repository-wide search finds no
spec or code that defines it as a named concept. What *does* exist, and
what this page documents, is the informal **`ru_obj` test family** in
`RuntimeReal/tests/`: a validated pattern for projecting a `ReasonUnit`
graph into a renderable 2D/3D scene (an "object" composed of ReasonUnits).
If you came here expecting a distinct API or type named `ReasonUnitObject`,
it does not exist yet — treat this page as documenting the closest real
thing, not confirming a spec you may have seen elsewhere.

## What It Actually Is: Graph-to-Scene Projection

`RuntimeReal/tests/ru_obj_2d_*.rs` (`ru_obj_2d_001`...`ru_obj_2d_009`) and
`ru_obj_3d_*.rs` (`ru_obj_3d_001`...`ru_obj_3d_005`) validate that a
`ReasonGraph` built from `ReasonUnit`s and `SemanticRelation` edges (see
[reasonunit.md](reasonunit.md)) can be deterministically projected into a
scene and rendered:

- Example: `ru_obj_2d_001_rectangle_graph_projects_to_visible_png` renders a
  `ReasonGraph` to a PNG scene.
- Generated fixtures live under `RuntimeReal/artifacts/ru_obj_*/`: scene
  JSON, layout JSON, and PNG renders, plus `RuntimeReal/output/`.

In other words: a `ReasonUnit` graph (nodes typed as `Concept`/`Object`/
`Event`/... with typed edges) is not inherently spatial. The `ru_obj`
pattern is how the runtime validates that such a graph *can* be laid out
and rendered as a concrete 2D or 3D object/scene — the bridge between
abstract reasoning state and a visualizable geometry.

## Relationship to WorldModel

This low-level graph-to-scene projection is a runtime-internal validation
pattern (Rust tests, not a public API). The supported, documented way to
build spatial/geometric compositions is the **WorldModel spatial layer**
(`sdk/world/spatial.py`) — see [worldmodel.md](worldmodel.md#spatial-layer).
It provides `Geometry`, transform hierarchies (`attach_child`/
`set_parent`), deterministic layout solving, and conflict detection as a
stable Python SDK surface, rather than the ad hoc Rust test fixtures
described above.

## If You Need Object/Scene Composition Today

Use the WorldModel SDK (`sdk/world/builder.py`, `sdk/world/spatial.py`) —
see [worldmodel.md](worldmodel.md) and
[World_SDK_Phase_1_Specification.md](../specifications/World_SDK_Phase_1_Specification.md).
The `ru_obj` tests are useful as evidence of what the underlying runtime
supports and as a reference for the kind of graph structures that project
cleanly to scenes, but they are not an API contract you should depend on.
