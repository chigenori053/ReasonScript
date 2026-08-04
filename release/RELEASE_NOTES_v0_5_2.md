# ReasonScript 0.5.2 Release Notes

ReasonScript 0.5.2 adds the safe-Rust VisionRuntime and its typed ReasonScript
language integration.

## Included

- `vision.infer` and `vision.build_ruo` language functions;
- `VisionModel`, `VisionObservation`, and `VisionBuildResult` types;
- VisionCallIR and capability-aware ExecutionPlan operations;
- semantic ReasonUnit plus RUO-T1 detection and embedding Tensor output;
- atomic canonical `.ruo` publication;
- platform-native `reason-vision` runtime;
- Vision-aware source installation and update packages;
- LSP and Monaco completion/highlighting.

## Installation

The macOS arm64 bundle contains a checksummed `0.5.2` update-and-install
archive. For a new installation, extract the inner archive and run:

```sh
python3 payload/scripts/install_common.py --non-interactive --json
```

Source installation requires Python 3.11+, Git, and Rust/Cargo. Installation
from the packaged archive uses its prebuilt native VisionRuntime and updater,
so Rust/Cargo is not required on the target system.
