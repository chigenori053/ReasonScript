# ReasonScript Update ZIP Executable Restoration v0.1

Specification ID: `reasonscript-update-zip-executable-restoration/0.1`
Status: VALIDATED
Date: 2026-07-23

## Problem

ZIP extraction does not reliably preserve Unix executable mode bits. The
update path previously restored executability only for `reason` and
`bin/reason-runtime`. Packaged native executables therefore reached
post-install validation as mode `0644`, causing `doctor` and
`install-validate` to fail and triggering INS-UPD-010/INS-UPD-011.

## Required behavior

1. After payload extraction, the updater restores executable mode for every
   file recorded as `executable: true` in the validated provenance manifest.
2. Restored paths must remain inside the staging root.
3. Staging validation runs both native `verify-native` probes before
   activation.
4. Missing, non-executable, invalid, or unsafe native executables fail as
   INS-UPD-008 during `validating_staging`.
5. Post-install command details, including exit status and stable diagnostic
   codes, are retained and exposed when automatic rollback occurs.
6. ZIP update tests cover mode loss, restoration, successful activation, and
   actionable failure reporting.
7. The packaged CLI repairs the bounded native executable set at startup so
   installations using the pre-v0.5.2.1 updater can pass their first
   post-activation validation. New updater code remains responsible for
   provenance-driven restoration before activation.

## Acceptance

- A 0.5.1 installation updates to 0.5.2.1 from the ZIP without a development
  override when using a clean release-class package.
- `doctor`, `install-validate`, scalar/Tensor/loop/project probes, and both
  native probes pass.
- The resulting package has `package_class: release`, `dirty: false`, and a
  source commit equal to the clean build HEAD.
- `reason ci --json` passes.
