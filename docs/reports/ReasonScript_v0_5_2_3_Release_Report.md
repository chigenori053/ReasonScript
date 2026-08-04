# ReasonScript v0.5.2.3 Release Report

## Completion Summary

ReasonScript v0.5.2.3 packages the validated VisionWorldModel V0 compiler and
parser corrections as an update-and-install maintenance release for macOS
arm64.

## Implemented Features

- Inner-to-outer nested function-call lowering.
- Unique branch convergence through `FunctionCallMergeTransition`.
- Literal nested-call value propagation into outer branch evaluation.
- Multiline typed function parameter declarations.

## Validation Results

- Version consistency: 6/6 PASS.
- Focused function, compatibility, and distribution tests: 23 PASS.
- Source-tree `python3 -m toolchain ci --json`: PASS, 1095 tests.
- Workspace, diagnostics, artifacts, Golden, Agent Protocol, and 17
  compatibility targets: PASS.
- Release provenance checks: 13/13 PASS across 441 package files.
- Clean release provenance (`package_class: release`, `dirty: false`): PASS.
- Local update from installed 0.5.2.2 to 0.5.2.3: PASS.
- Atomic activation and rollback readiness: PASS; rollback not required.
- Post-install version, doctor, install-info, install-validate, scalar, Tensor,
  loop, and project probes: PASS.
- Installed external-project `reason check`, `reason build`, and `reason run`:
  PASS.
- Installed RS-VWM-001 probe: unique transition IDs, inner return value `2`
  supplied to `Outer`, and `Outer.return.true` selected.
- Installed RS-VWM-002 probe: multiline `Add` signature accepted and return
  value `3` generated.

## Generated Artifacts

- `dist/v0.5.2.3/reasonscript-0.5.2.3-macos-arm64.zip`
- `dist/v0.5.2.3/reasonscript-0.5.2.3-macos-arm64.zip.sha256`
- `dist/v0.5.2.3/reasonscript-0.5.2.3-macos-arm64.manifest.json`
- `dist/v0.5.2.3/reasonscript-0.5.2.3-macos-arm64.manifest.sha256`

Artifact integrity:

- Archive SHA-256:
  `a8300e175ceb84dabcae5b84616a36c5ff785bd230431f67ea2c8c77bd6df5fc`
- Manifest SHA-256:
  `37ec2f5700ee3ff67725b0d1afa34bcfd8951375ec51d81f1164e9d4565798aa`
- Payload SHA-256:
  `2be5d7bc37697ae21c9ec89734675cf4631eb8dc3c719cf36909c233c464da91`
- Source commit:
  `2c0df336dc137a8b43fffbf94294766a7e08e7bd`

## Compatibility Notes

The update floor remains 0.5.0 and runtime compatibility remains
`>=0.5.0,<0.6.0`. Canonical function return IDs and established single-call
branch evidence remain unchanged. Existing Golden baselines were not changed.

The installed launcher running `reason ci` from a source checkout still
reproduces the previously reported Phase 8 Golden mixed-distribution
`CI-006`. The source-tree CI entry point passes all phases; installation and
language regression validation are unaffected.

## Remaining Work

No implementation or packaging work remains for v0.5.2.3. The pre-existing
installed-launcher `reason ci` observation remains a separate tooling task.
