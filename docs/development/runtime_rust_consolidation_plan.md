# ReasonScript Rust Runtime Consolidation Plan

## Status

`IN_PROGRESS` — Phases 0–3 completed; Phase 4 Tensor completeness.

## Objective

Converge product execution on one installed Rust runtime host while retaining
the Python parser, validator, analyzer, and lowering frontend. Runtime domains
remain separate Rust crates behind the host; this is execution-path
consolidation, not a monolithic crate rewrite.

## Target layout

```text
ReasonRuntime/
  crates/
    runtime-types/
    computation-ir/
    computation-vm/
    tensor-core/
    reason-object-core/
    reasoning-core/
    vision-core/
    runtime-host/
```

Cluster workers and the Install Foundation Updater retain justified process
boundaries. Reason IR and Computation IR remain distinct schemas connected by
an explicit adapter.

## Phases

1. **Phase 0 — baseline:** freeze the execution topology, namespace coverage,
   fallback reasons, removal candidates, and deletion gates with
   `reason runtime-manifest`.
2. **Phase 1 — protocol and host:** define versioned request/result envelopes,
   install the Rust host, and make binary discovery work in source and installed
   layouts.
3. **Phase 2 — dispatch convergence:** route standalone and project execution
   through the same adapter and execute built Computation IR.
4. **Phase 3 — VM completeness:** add unsupported core values and language
   operations, structured diagnostics, source spans, and trace parity.
5. **Phase 4 — Tensor completeness:** implement every frozen Tensor function
   and VJP plus resource, filesystem, capability, metadata, and trace parity.
6. **Phase 5 — RUO and Vision:** move all RUO operations and Vision publication
   into Rust libraries called in-process by the VM.
7. **Phase 6 — reasoning:** connect search/simulate/predict/plan to a canonical
   Rust reasoning core and make manifest backend selection effective.
8. **Phase 7 — Python runtime retirement:** remove production fallback and move
   Python evaluators to reference-only tests before deletion.
9. **Phase 8 — workspace consolidation:** move retained Rust crates into the
   target workspace and delete superseded directories.
10. **Phase 9 — cleanup:** remove obsolete tests, fixtures, build entries,
    flags, package rules, and documentation.

## Deletion policy

A file may be removed only after its Rust replacement exists; result,
diagnostic, source-location, and trace parity pass; production imports are
zero; standalone, project, and installed-package smoke tests pass; and
`reason ci` passes with Python fallback disabled. Deletion is split into
feature-scoped commits in this order: fallback branches, Python production
runtimes, old Rust layouts, then obsolete fixtures/configuration/documentation.

The frozen current-state baseline is
`docs/reports/runtime_consolidation_manifest.json`. Any intentional change to
that file requires a matching implementation and changelog/report update.
