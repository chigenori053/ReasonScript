# Cluster Reasoning Runtime Extension v0.1

- Added the optional Rust `reasonscript-cluster-runtime` crate.
- Added deterministic planning, logical-step scheduling, barrier synchronization, Rust worker processes, retry/de-duplication, and single-node fallback.
- Added SHA-256 message and artifact validation plus all nine Cluster Runtime artifacts.
- Added `reason cluster` plan, run, simulate, validate, compare, and test-model commands through a thin source-compilation adapter.
- Added the CRR diagnostic catalogue, six JSON schemas, eight Dynamic ReasonUnit scenarios, and a molecular boundary-interaction scenario.
- Preserved existing parser, Reason IR, ExecutionPlan, single-node runtime, and non-cluster artifact behavior.
