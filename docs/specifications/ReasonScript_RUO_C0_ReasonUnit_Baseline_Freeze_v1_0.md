# ReasonScript Phase RUO-C0: ReasonUnit Baseline Freeze Specification v1.0

## Status

IMPLEMENTED

## Date

2026-07-20

## Purpose and scope

RUO-C0 freezes the observable compatibility baseline before ReasonUnit Object is
introduced. It inventories identity, type/role, ownership, state, relations,
constraints, evidence, confidence, lifecycle, revision, dependencies, execution,
resource policy, diagnostics, Dynamic Cluster behavior, Tensor associations, and
project-local adapter semantics. It does not add `ReasonUnitObject`, syntax,
`.ruo` serialization, migration, or behavior changes.

Semantic observations are classified as `language_native`, `runtime_native`,
`cluster_runtime_native`, `standard_schema`, `project_local`, `adapter_owned`,
`documentation_only`, `implicit_behavior`, or `undefined`. Undefined behavior is
recorded and is not normalized into a new contract.

## Frozen identity rules

```text
ReasonUnit identity != declaration order
ReasonUnit identity != Tensor index
ReasonUnit identity != worker assignment
ReasonUnit identity != temporary artifact path
```

Existing violations or missing contracts are compatibility risks. RUO-C0 may add
only read-only probes, schemas, deterministic manifests, fixtures, tests,
documentation, validation entry points, and canonical baseline artifacts.

## Required fixtures and artifacts

The baseline contains minimal atomic, related, stateful, evidence-carrying,
lifecycle, cluster-executed, Tensor-associated, and molecular fixtures, plus
duplicate identity, dangling relation, invalid state/lifecycle/evidence, conflict,
resource-limit, and digest-corruption cases.

The canonical output is the 20-artifact set named by the attached RUO-C0 v1.0
specification: 19 JSON documents from `environment_manifest.json` through
`run_manifest.json`, plus `final_report.md`. JSON uses a project-owned versioned
schema and deterministic UTF-8/LF serialization. `run_manifest.json` records the
digest and byte size of every non-self artifact and a defined pre-self-entry digest
for itself.

## Validation and acceptance

The implementation executes RUO-C0-T001 through RUO-C0-T040, three isolated
generations, byte comparison, offline tamper detection, protected-behavior checks,
artifact/schema validation, existing Golden tests, and canonical `reason ci`.
RUO-G1, RUO-G1E, molecular, Dynamic Cluster, and Reasoning Runtime Golden evidence
must be verified by logical ID and digest; absolute paths are non-canonical.

The phase is `VALIDATED` only when all 40 tests pass, schemas and digests validate,
three runs are byte-identical, protected behavior and existing Goldens are
unchanged, and no error/fatal diagnostic remains. Otherwise it is
`NOT_VALIDATED` and the transition is `DO_NOT_PROCEED_TO_RUO-C1`. The only
successful transition is `PROCEED_TO_RUO-C1`.

## External vehicle evidence input

RUO-G1 and RUO-G1E evidence is supplied as independently digested bundles. Each
entry uses logical IDs and a role-keyed `files` object:

```json
{
  "project_id": "vehicle-silhouette-ruo-g1",
  "artifact_id": "RUO-G1",
  "files": {
    "validation_summary": {"local_path": "g1/validation_summary.json", "sha256": "sha256:..."},
    "run_manifest": {"local_path": "g1/run_manifest.json", "sha256": "sha256:..."}
  }
}
```

RUO-G1E additionally requires `information_density_report`. Relative input paths
are resolved from the external evidence manifest directory. Paths are validation-
time metadata and are never serialized into canonical RUO-C0 artifacts.

Verification checks the expected schema and document role, validated phase and
complete test matrix, determinism and rollback results, information-density
claims, canonical child count, projection presence, child digests and sizes, and
aggregate byte count. A matching self-supplied digest alone is insufficient.

This repository document is the implementation profile of the complete user-
supplied “ReasonScript Phase RUO-C0: ReasonUnit Baseline Freeze Specification
v1.0”; its detailed inventory, diagnostics RUO-C0-001–018, test matrix, risk
fields, undefined-semantics fields, and RUO-C1 input contract are represented in
the generator and canonical artifacts without weakening any normative condition.
