# Phase 14: Native RGO-F1 Graph Loader v0.1

## Accepted scope

Phase 14 adds a Native Runtime loader for complete, canonical RGO-F1 files.
It exposes an immutable `NativeReasonGraph` and does not add graph mutation,
transactions, execution, or network transport.

## Requirements

- The loader accepts exactly the three canonical RGO-F1 JSONL records.
- It verifies per-record body digests, content digest, graph digest, header
  compatibility, stable namespaces, duplicate identities, and relation endpoint
  resolution before exposing a graph.
- Native graph identity and entity identity must agree with the Python RGO-F1
  reader.
- The CLI boundary is `reason reason-object-graph native-load INPUT.rgraph`.
- Native graph data remains read-only.

## Deferred work

Native graph updates, execution semantics, distributed transactions, and
networked MIRP transport remain outside Phase 14.
