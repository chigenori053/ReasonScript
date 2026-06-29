# Runtime View Model Contract

The Playground derives structured views from runtime artifacts. Raw JSON remains available for every major artifact.

Required view keys in `/api/analyze`:

- `views.pipeline`
- `views.source_model`
- `views.execution_plan`
- `views.simulation`
- `views.knowledge`
- `views.runtime_operations`
- `views.output`
- `views.diagnostics`

`views.execution_plan` exposes goal, distance, reachability, ordered steps, selected branch data, alternative paths, and an unreachable reason when available.

`views.simulation` exposes success, goal reached, ordered trace, final state, and raw `simulation.json` fallback.

`views.knowledge` exposes knowledge item count and evidence-bearing knowledge items.

`views.runtime_operations` groups runtime operations by kind. The minimum required runtime IO kinds are `input` and `print`.

`views.output` contains print output events and an event count. It is empty when the program has no print operations.
