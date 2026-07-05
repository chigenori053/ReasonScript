# ReasonScript Phase 8A — Reasoning Model Contract v1.0

## Status

VALIDATED

## Version

`reasonscript-reasoning-model/1.0`

## Summary

Phase 8A introduces the first versioned ReasoningModel artifact contract for ReasonScript. The contract defines an inspectable artifact layer above the existing pipeline without changing parser behavior, runtime execution semantics, or Reason IR execution behavior.

## Added

- Added `docs/specifications/ReasonScript_Reasoning_Model_Contract_v1_0.md`.
- Added `frontend/schemas/reasoning_model.schema.json`.
- Added `toolchain/reasoning_model_contract.py`.
- Added deterministic ReasoningModel serialization via `serialize_reasoning_model()`.
- Added ReasoningModel validation via `validate()`.
- Added `toolchain/reasoning_model_cmd.py`.
- Added CLI support for:

  ```bash
  reason reasoning-model validate <file> --json
  ```

- Added valid and invalid ReasoningModel fixtures.
- Added RM diagnostic families from `RM-001` through `RM-EVAL-004`.
- Added contract tests covering RM-T001 through RM-T117.
- Added `reasonscript-reasoning-model/1.0` to CI compatibility targets.

## Validation

- `python3 -m toolchain ci --json`
- `python3 -m toolchain ci-entry --json`
- `python3 -m pytest tests -q`
- Manual validation of valid and invalid ReasoningModel fixtures.

## Results

- `691 passed`
- `ci-entry ok: true`

## Compatibility

- Parser behavior is unchanged.
- Runtime execution behavior is unchanged.
- Reason IR execution semantics are unchanged.
- Existing pipeline phase order is unchanged.
- ReasoningModel validation is reachable through the canonical CI compatibility phase.
