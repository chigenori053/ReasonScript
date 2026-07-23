# ReasonScript Update ZIP Executable Restoration v0.1 Report

## Completion Summary

The v0.5.2.1 ZIP update path now preserves packaged executable intent and
updates a v0.5.1 installation without post-activation rollback.

## Implemented Features

- Provenance-driven restoration of every executable payload file.
- Safe staging-root containment checks for restored paths.
- Pre-activation VisionRuntime and Native ReasonUnit Runtime probes.
- Bounded packaged-CLI compatibility repair for the v0.5.1 updater.
- Structured post-install failure details in validation and rollback reports.

## Validation Results

- Install/update focused tests: 77 passed.
- Legacy v0.5.1 updater to v0.5.2.1 isolated update: PASS.
- Post-install version, doctor, install-info, install-validate, scalar, Tensor,
  loop, and project probes: PASS.
- `reason ci --json`: PASS, 1088 tests.

## Generated Artifacts

- `dist/v0.5.2.1/reasonscript-0.5.2.1-macos-arm64.zip`
- Archive SHA-256 sidecar and provenance manifest sidecars.

## Compatibility Notes

The packaged CLI bootstrap is limited to the known native executables and only
runs for distributions containing the validation-profile marker. New updater
versions restore all provenance-declared executable files before activation.

## Remaining Work

None.
