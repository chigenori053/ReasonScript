# ReasonScript Installed Distribution ML Evaluation v0.2 Correction

Status: IMPLEMENTED

Specification ID: `reasonscript-ml-evaluation-visualization/0.2`

## Distribution contract

The installed distribution includes the complete repository-owned
`runtime/visualization/evaluation` package recursively, the complete v0.2 schema
family, and the public evaluation API exported by `runtime.visualization`.

The install manifest records every evaluation module with its relative path,
SHA-256 digest, byte size, and distribution version through the
`ml-evaluation-visualization-v0.2` component.

## Validation contract

`reason install-validate --json` reports `MLV-INSTALL-001` through
`MLV-INSTALL-010`. Validation runs from a repository-external temporary
directory with an empty `PYTHONPATH`, checks module path confinement, evaluates
continuous classification scores without importing Matplotlib, serializes the
evaluation with standard JSON, and verifies AUC 0.75 and average precision 5/6.

This correction changes distribution completeness only. ML Evaluation,
rendering, KDA-2, IR, metric, threshold, and artifact semantics are unchanged.
