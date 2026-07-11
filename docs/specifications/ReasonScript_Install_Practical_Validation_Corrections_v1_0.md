# ReasonScript Install Foundation Practical Validation Corrections v1.0

- Specification ID: `reasonscript-install-practical-validation-corrections/1.0`
- Status: ACCEPTED
- Product: ReasonScript 0.5.x

## Contract

`VERSION` is the canonical product version. `pyproject.toml`, release-manifest reason/runtime/CLI versions, runtime compatibility, CLI output, installed manifests, version directories, and release tags must agree with it. `reason version-validate` emits `reasonscript-version-validation/1.0` and fails on inconsistency.

`reason init` preserves the filesystem project name while generating a distinct valid package identifier. Hyphens, whitespace, unsupported characters, leading digits, and reserved words are normalized. Generated minimal projects must immediately pass `check`, `run`, and `artifacts`.

`reason artifacts` resolves output in this order: explicit `--out`, project `[artifacts].directory`, then `artifacts`. Configured relative paths are rooted at the nearest project root and may not escape it.

Installed validation retains IF-VAL-001 through IF-VAL-020 and adds IF-PV-001 through IF-PV-006. Successful installed CLI smoke validation atomically changes `distribution_validation.installed_cli_smoke` and its aggregate status to `pass`; inability to persist this state produces warning IF-PV-006 without discarding successful validation results.

Historical release documents are excluded from current metadata consistency checks.
