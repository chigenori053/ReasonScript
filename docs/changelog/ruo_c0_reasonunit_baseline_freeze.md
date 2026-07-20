# RUO-C0 ReasonUnit Baseline Freeze

Added a read-only ReasonUnit compatibility inventory and deterministic baseline
generator. The phase adds a versioned canonical-artifact schema, representative
valid and invalid fixtures, T001–T040 coverage, offline digest/tamper validation,
three-run determinism checks, risk and undefined-semantics registers, and a thin
`reason reasonunit-baseline` CLI. No language, Runtime, Cluster Runtime, Tensor,
diagnostic, existing artifact, or Golden behavior is changed.

RUO-G1/RUO-G1E evidence is deliberately not inferred. When those external
artifacts are unavailable, the generated phase status remains `NOT_VALIDATED`.

External vehicle evidence now uses independently digested role bundles. Semantic
validation rejects unrelated JSON, invalid phase/test results, incorrect geometry
and information-density claims, missing projections, and mismatched child digest
or byte-size records. Canonical output retains verified content digests but never
serializes local paths.
