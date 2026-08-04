# Coding Agent Development Guide v0.5

## Purpose

This guide defines the safe workflow for Coding Agent changes in ReasonScript v0.5.

## Required Workflow

1. Read the target specification.
2. Identify in-scope and out-of-scope files.
3. Implement contract-first.
4. Add or update JSON schema when required.
5. Add validator coverage when required.
6. Add a CLI wrapper when required.
7. Add fixtures.
8. Add tests.
9. Update changelog and release documentation.
10. Run targeted tests.
11. Run `./reason ci --json`.
12. Preserve parser, runtime, Reason IR, ExecutionPlan, Simulation, and Knowledge compatibility unless explicitly scoped.

## Forbidden Behavior

- Do not silently change parser semantics.
- Do not silently change runtime execution semantics.
- Do not alter Reason IR behavior without a specification.
- Do not bypass `./reason ci --json`.
- Do not mix IDE experimental changes into v0.5 core commits.
- Do not regenerate golden artifacts without explicit reason.

## Commit Boundaries

Keep release stabilization documentation separate from feature work, golden artifact regeneration, IDE experimental work, Input Semantic Decomposition, WorldModel integration, and unrelated formatting.

## Validation

At minimum, run:

```sh
./reason ci --json
```

For Phase 8 reasoning artifact work, also run:

```sh
./reason phase8-golden validate --json
python3 -m pytest tests/golden/test_phase8_golden_validation.py tests/reasoning_model/test_reasoning_runtime_prototype.py -q
```
