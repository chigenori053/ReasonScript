# MRA RUO / ReasonRelation Phase 16

## Added

- Native atomic RGO-F1 metadata transactions with compare-and-commit hashes.
- Rejected-transaction source-byte invariance verification.
- `reason reason-object-graph native-transact` command.

## Compatibility

The native mutation boundary is intentionally restricted to graph metadata;
existing RGO-F1, RUO, and Python transaction behavior remains unchanged.
