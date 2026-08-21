# ReasonScript 0.5.4.9 Release Notes

ReasonScript 0.5.4.9 corrects three language-surface type inconsistencies found
during Transformer validation and adds an Agent-oriented project template.

## Language validation corrections

- `tensor.scalar` is represented as an external scalar with an unknown static
  primitive type instead of being misclassified as `Tensor`.
- `/` now has static Float result semantics that match runtime true division.
- Unknown assignment compatibility is symmetric for legacy function results.

## Agent project template

`reason init <name> --template agent` adds tool-neutral `AGENTS.md` instructions
and a `DRAFT` project specification under `SPECIFICATIONS/`. The existing
default and explicit minimal templates remain unchanged.

## Package

The local macOS arm64 development update package is:

`release/v0.5.4.9/reasonscript-0.5.4.9-macos-arm64.zip`

Runtime compatibility remains `>=0.5.0,<0.6.0`.
