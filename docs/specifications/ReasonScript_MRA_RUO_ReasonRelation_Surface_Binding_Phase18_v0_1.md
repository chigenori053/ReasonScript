# Phase 18: ReasonGraph Surface Binding v0.1

## Accepted scope

Phase 18 integrates a read-only ReasonGraph binding into the existing
ReasonScript Surface AST and Reason IR pipeline.

```reasonscript
module GraphBinding {
reason_graph graph from "graph.rgraph" as "ruo:graph:example";
}
```

## Requirements

- Binding paths are safe relative lowercase `.rgraph` references.
- The optional assertion must be a `ruo:graph:` identity.
- The parser projects `ReasonGraphBindingIR` through
  `reason_graph_bindings` metadata with a `filesystem_read` requirement.
- A binding remains read-only and does not make generic `reason run` perform
  graph I/O or graph execution.

## Deferred work

Generic ReasonScript query execution, graph mutation syntax, Unit/Relation
mutation, graph execution semantics, networked MIRP, and distributed
transactions remain outside this phase.
