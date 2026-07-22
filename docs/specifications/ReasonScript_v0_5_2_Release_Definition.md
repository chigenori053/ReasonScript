# ReasonScript v0.5.2 Release Definition

Specification ID: `reasonscript-release/0.5.2`
Status: VALIDATED

ReasonScript 0.5.2 is the first installable release containing VisionRuntime,
the `vision.*` language namespace, RUO-T1 Vision Tensor projections, atomic RUO
publication, and the native `reason-vision` executable.

The canonical version is `0.5.2` across `VERSION`, Python package metadata,
release metadata, runtime metadata, and the validation profile. A new install
must activate `versions/0.5.2`, publish an install manifest with ReasonScript and
runtime version `0.5.2`, pass all 36 installed-distribution checks, execute
`reason-vision verify-native`, and complete a Vision `.rsn` to `.ruo` smoke test.

The macOS arm64 distribution is an update-and-install package with SHA-256 file
inventory, package provenance, a native executable, and an outer
`ReasonScriptV5.2.zip` delivery bundle.
