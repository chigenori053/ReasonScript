# AST Validation Report v0.1

Status: Passed

## Scope

Phase 0 validates AST core nodes, hierarchy, Reason IR lowering, six required
use cases, and the seven AST invariants.

## Implemented Artifacts

- Semantic AST definitions in `frontend/ast/`
- Deterministic lowering to `reason-ir/0.1`
- Validation suite in `ast_validation_tests/`
- Normative draft in `docs/AST_Validation_Specification_v0.1.md`

## Validation Matrix

| Requirement | Evidence | Result |
|---|---|---|
| Basic inference | `test_case_1_basic_inference` | Pass |
| Constraint | `test_case_2_constraint` | Pass |
| Context reference | `test_case_3_context_reference` | Pass |
| Tool integration | `test_case_4_tool_integration` | Pass |
| WorldModel transition | `test_case_5_world_model_transition` | Pass |
| DBM planning | `test_case_6_dbm_planning` | Pass |
| Reason IR mapping | schema and semantic validator checks | Pass |
| JSON representation | JSON round-trip test | Pass |
| Unique node IDs | duplicate rejection tests | Pass |
| Runtime/SDK/graph independence | dependency and representation checks | Pass |

## Execution Results

Executed on 2026-06-13:

```text
python3 -m unittest discover -s ast_validation_tests -p 'test_*.py' -v
Ran 12 tests: OK

python3 conformance/run_conformance.py
Layer 0: PASS
Layer 1: PASS
Layer 2: PASS
Layer 3: PASS
Layer 4: PASS
```

## Decision

Phase 0 success and exit criteria are satisfied. Core nodes, hierarchy,
mapping rules, validation cases, invariants, and the recommended AST structure
are implemented and verified. The project can proceed to Phase 1 AST Schema
Validation.
