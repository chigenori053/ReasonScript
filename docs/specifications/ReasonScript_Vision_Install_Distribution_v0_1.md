# ReasonScript Vision Install Distribution v0.1

Specification ID: `reasonscript-vision-install-distribution/0.1`
Status: VALIDATED

## Purpose

The source installer and update-package builder distribute VisionRuntime as a
complete, repository-independent component. An installed ReasonScript CLI must
execute `vision.infer` and `vision.build_ruo` without resolving modules or native
executables from the source repository.

## Distribution Contract

The required payload contains:

- `VisionRuntime/` Rust source and Cargo metadata;
- `frontend.vision` language/runtime integration;
- the platform-native `bin/reason-vision` executable;
- the Vision observation schema and normal ReasonScript/RUO dependencies.

Package construction builds `reason-vision` in safe Rust for the target platform
and records it in payload checksums and provenance. Source installation performs
the same release build before atomic activation. Build caches and Cargo `target/`
directories are not copied into the installed source tree.

## Validation

Pre-activation distribution validation imports the Vision Python closure only
from the staged root and runs `reason-vision verify-native`. Installed regression
coverage runs a complete `.rsn` Vision pipeline and validates successful canonical
`.ruo` publication. Update-package coverage verifies both Rust source and the
native executable are present in the checksummed payload.
