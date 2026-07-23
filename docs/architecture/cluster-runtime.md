# Cluster Runtime

## Status: Not Implemented

There is no "Cluster Runtime" in ReasonScript today. A repository-wide,
case-insensitive search for "Cluster Runtime" / "ClusterRuntime" /
"cluster_runtime" returns zero matches in code or docs. This page exists so
that anyone looking for distributed execution has an authoritative answer
rather than inferring one from the roadmap.

If you are evaluating ReasonScript for a multi-node or distributed
workload, **it is not there yet** — plan accordingly.

## What Does Exist: "Distributed Runtime" as an Explicit Exclusion

The closest related term in the codebase is "Distributed Runtime," and it
appears only as something explicitly **excluded** from the current release:

> "Macros, language server, formatter, optimizer, distributed Runtime,
> persistence, and event sourcing are not included."
>
> — [ReasonScript_Platform_v0.1_Alpha_Release_Specification.md](../specifications/ReasonScript_Platform_v0.1_Alpha_Release_Specification.md)

The same document restates it later: "Distributed Runtime, persistence, and
event sourcing are not implemented." This is a release-scoping statement,
not a roadmap commitment with a target phase — distributed execution does
not currently appear as a scheduled item in [ROADMAP.md](../../ROADMAP.md)
either.

## Historical Context: The Legacy Elixir Prototype

`Legacy/elixir_runtime/` contains an old Elixir/OTP-based runtime prototype
with distributed/supervision-tree concepts:
`lib/runtime/distributed_proof_barrier.ex`, `orchestrator_server.ex`,
`session_supervisor.ex`. This predates and is unrelated to the current Rust
runtimes (`RuntimeReal/`, `HybridRuntime/`, `RuntimeComplex/` — see
[runtime.md](runtime.md)). It is kept for historical reference only; it is
not on the current architecture's execution path, and no current
specification builds on it.

## What To Use Instead Today

For actual execution, use [`RuntimeReal`](runtime.md#runtimereal) or
[`HybridRuntime`](runtime.md#hybridruntime), both single-process. If your
use case needs multiple independent ReasonScript processes coordinating,
you would need to build that coordination yourself at the application
layer — the platform provides no distributed transaction, consensus, or
multi-node state-sync primitives.

## Tracking

There is no tracked spec or milestone for a Cluster Runtime. If this is a
capability you need, the right first step is to open a proposal per
[CONTRIBUTING.md](../../CONTRIBUTING.md#proposing-language-or-runtime-changes)
rather than assume unpublished work is underway.
