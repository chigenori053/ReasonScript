# Vision and geometry

`reason geometry run` converts a validated Vision 0.1 observation into a
versioned spatial observation and geometric state. The input must contain
authored detections; the test Vision backend does not recognize arbitrary
images. Coordinates use an explicit image system: origin `TOP_LEFT`, x to the
right, y down, in pixels. Spatial relations are derived by GeometryRuntime,
not asserted by VisionRuntime.

```sh
./reason geometry observe tests/fixtures/vision_runtime/solar_observation.json --json
./reason geometry run tests/fixtures/vision_runtime/solar_observation.json --json
```

`run` returns `observation`, `geometry_state`, a valid MIRP ReasonGraph
fragment, `semantic_state`, and a trace. The geometry state keeps primitive
provenance, unresolved values in `unknowns`, and contradictory positions in
`conflicts`. The runtime derives `LEFT_OF`, `RIGHT_OF`, `ABOVE`, `BELOW`,
containment, overlap, touch, intersection, near/far, and alignment relations.
Near uses a 100 pixel threshold; comparison uses the explicit default
tolerance policy in the native Geometry runtime.

To execute an explicit reasoning sequence, save `geometry_state` from `run`
as JSON and prepare a steps file:

```json
[
  {"ru": "DistanceRU", "arguments": ["A:centroid", "B:centroid"]},
  {"ru": "SpatialRelationRU", "arguments": ["A", "B"]}
]
```

Run `./reason geometry rus geometry-state.json steps.json --json`. The result
contains each operation result, one RUS trace, and a versioned MIRP delta.
Other supported units are `AngleRU`, `IntersectionRU`, `ContainmentRU`,
`OverlapRU`, and `TransformRU`. The last accepts a JSON encoded six value
affine matrix as its second argument.

To dispatch Vision and Geometry tasks through the cluster runtime, supply a
JSON file with `tasks` and optional `limits` to `reason cluster dynamic visual`:

```json
{
  "tasks": [
    {
      "task_id": "vision-1",
      "runtime_type": "VISION",
      "input_state": {"schema_version": "reasonscript-vision-observation/0.1"},
      "goal": "EXTRACT_OBJECTS",
      "dependencies": [],
      "provenance": []
    },
    {
      "task_id": "geometry-1",
      "runtime_type": "GEOMETRY",
      "input_state": null,
      "goal": "CALCULATE_SPATIAL_RELATIONS",
      "dependencies": ["vision-1"],
      "provenance": []
    }
  ]
}
```

Replace the abbreviated Vision `input_state` with a full observation. The
cluster returns sorted task outputs, a merged GeometryState, and the same
semantic projection for local or parallel dispatch. `limits` accepts
`max_workers`, `max_operations`, `max_memory`, `timeout_ms`,
`max_state_size`, and `local_threshold`; omitted limits use the native
defaults. A failed budget returns `RESOURCE_LIMIT`.

Machine contracts are in
[`visual_spatial_observation.schema.json`](../../schemas/visual_spatial_observation.schema.json)
and [`geometry_state.schema.json`](../../schemas/geometry_state.schema.json).
The existing Vision 0.1 observation and MIRP 0.1 graph contracts remain valid.

## Generic runtime orchestration

`reason cluster dynamic runtime <tasks.json> --json` dispatches registered
runtimes through the same bounded scheduler. `dynamic visual` remains an alias.
Each task uses `schema_version: "reasonscript-runtime-task/1.0"`; older Vision
and Geometry task files without that field remain accepted by the native CLI.
`runtime_type` currently supports `VISION` and `GEOMETRY`. An unknown value
returns `UNSUPPORTED_RUNTIME` with status `UNSUPPORTED`.

The registry validates tasks and lets each adapter estimate work, decompose
units, execute, and canonicalize its output. The scheduler selects `CLUSTER`
when estimated operations exceed `local_threshold`, there is more than one
parallel unit, and `max_workers` exceeds one; otherwise it selects `LOCAL`.
The decision and workload are returned in `scheduling`. Workers use canonical
IDs `worker:<runtime_type>:<task_id>`, and results are merged by task identity.
Semantic output and trace do not depend on the number of workers or task input
order. A cluster worker is a local thread, not a remote machine.

`task_outputs` contain the versioned runtime envelope: status, domain
`output_state`, MIRP-compatible `semantic_state`, provenance, trace, and
operation metrics. `COMPLETED`, `UNKNOWN`, and `CONFLICT` remain distinct.
A limit or timeout returns `RESOURCE_LIMIT`, with `TIMEOUT` in the error for
timeouts. The machine contracts are
[`runtime_task.schema.json`](../../schemas/runtime_task.schema.json) and
[`runtime_output.schema.json`](../../schemas/runtime_output.schema.json).
