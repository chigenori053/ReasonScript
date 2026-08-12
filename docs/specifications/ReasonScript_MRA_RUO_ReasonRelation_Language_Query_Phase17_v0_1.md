# Phase 17: ReasonScript ReasonGraph Query Surface v0.1

## Accepted scope

Phase 17 defines a small `.rsn` source subset for verified, read-only
ReasonGraph operations without modifying the generic `reason run` execution
pipeline.

```reasonscript
module GraphProbe {
reason_graph graph from "graph.rgraph" as "ruo:graph:example";
query graph neighbors "ruo:unit:example";
}
```

## Requirements

- `reason_graph` binds only a safe relative `.rgraph` path and may assert its
  expected graph ID.
- `query` supports `summary`, `entity`, `outgoing`, `incoming`, and
  `neighbors`.
- Execution requires explicit `filesystem_read` capability via `--allow-read`.
- Each result is checked for Native/Python query parity and is read-only.
- CLI boundaries are `source-check` and `source-run` under
  `reason reason-object-graph`.

## Deferred work

Generic `reason run` integration, ReasonScript graph mutation syntax, native
Unit/Relation mutation, graph execution, networked MIRP, and distributed
transactions remain outside this phase.
