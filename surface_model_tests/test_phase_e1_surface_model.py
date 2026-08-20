"""Phase E1 — Surface Model v0.1 tests (RS-RE-FSM-001 §13 Phase E1).

Covers `ru:`/`rus:`/`ruo:`/`derive:`/`<-` end to end: Parser (E1-1), name
resolution and validation (E1-2), Semantic AST / Reason IR / ExecutionPlan
projection (E1-3), and the Runtime (E1-4) -- including the RS-RE-FSM-001
Appendix A example, which requires D-7 (module-level bindings previously
invisible to calculation bodies) to actually execute.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conformance.schema_validator import SchemaValidator
from frontend.integrated_computation_runtime import execute_program
from frontend.language_surface.integration import compile_program, execution_plan_for, project_program
from frontend.language_surface.parser import parse
from toolchain.pipeline import PipelineError, compile_source, validate_source

SCHEMAS = SchemaValidator(Path(__file__).resolve().parents[1] / "schemas")
PATH = Path("phase_e1.rsn")

APPENDIX_A = """
module GreetingLearning {
  ru: learning_rate: float = 0.01
  ru: current_step: int = 0
  ru: loss: float = 0.0
  rus: greeting_relation = {
    ru: token_relation: float = 0.0
    ru: position_relation: float = 0.0
    ru: politeness_relation: float = 0.0
    ru: syntactic_relation: float = 0.0
    ru: context_relation: float = 0.0
  }
  derive: training_active = current_step < 5
  calculation Train {
    while training_active {
      loss <- loss + learning_rate
      current_step <- current_step + 1
    }
    result = loss
  }
}
"""


def compiles(source: str) -> None:
    validate_source(source, PATH)


def run_value(source: str):
    return execute_program(parse(source)).value


# --- E1-1/E1-2: normal fixtures (RS-RE-FSM-001 §15.1) -----------------------


def test_ru_declaration_reference_and_transition() -> None:
    assert run_value(
        """
        module M {
          ru: score: float = 0.5
          calculation C {
            score <- 0.8
            result = score
          }
        }
        """
    ) == 0.8


def test_ru_type_inferred_from_initializer() -> None:
    compiles(
        """
        module M {
          ru: score = 0.5
          calculation C {
            score <- 0.9
            result = score
          }
        }
        """
    )


def test_derive_dependency_evaluation() -> None:
    assert run_value(
        """
        module M {
          ru: step: int = 0
          derive: active = step < 3
          calculation C {
            step <- 3
            result = active
          }
        }
        """
    ) is False


def test_rus_containment_and_implicit_part_of_relation() -> None:
    program = parse(
        """
        module M {
          rus: bundle = {
            ru: a: float = 1.0
            ru: b: float = 2.0
          }
          calculation C {
            result = 1
          }
        }
        """
    )
    modules = project_program(program)
    entities = next(
        metadata.value for metadata in modules[0].metadata if metadata.key == "reason_entities"
    )
    assert len(entities["relations"]) == 2
    assert all(relation["relation_type"] == "PartOf" for relation in entities["relations"])


def test_ruo_explicit_declaration() -> None:
    compiles(
        """
        module M {
          ruo: learner = {
            ru: progress: float = 0.0
          }
          calculation C {
            result = 1
          }
        }
        """
    )


def test_multiple_sequential_transitions_accumulate() -> None:
    assert run_value(
        """
        module M {
          ru: x: float = 1.0
          calculation C {
            x <- x + 1.0
            x <- x + 1.0
            result = x
          }
        }
        """
    ) == 3.0


def test_derive_reevaluates_after_dependency_transitions() -> None:
    assert run_value(
        """
        module M {
          ru: step: int = 0
          derive: active = step < 5
          calculation C {
            step <- 5
            result = active
          }
        }
        """
    ) is False


def test_module_level_const_and_entity_coexist() -> None:
    assert run_value(
        """
        module M {
          const factor: float = 2.0
          ru: base: float = 3.0
          calculation C {
            base <- base * factor
            result = base
          }
        }
        """
    ) == 6.0


# --- E1-2: abnormal fixtures (RS-RE-FSM-001 §15.2) --------------------------


def test_duplicate_entity_declaration_is_rejected() -> None:
    with pytest.raises(PipelineError, match="RE-DECL-001"):
        compiles(
            """
            module M {
              ru: x: float = 1.0
              ru: x: float = 2.0
              calculation C {
                result = x
              }
            }
            """
        )


def test_transition_type_mismatch_is_rejected() -> None:
    with pytest.raises(PipelineError, match="RE-TYPE-002"):
        compiles(
            """
            module M {
              ru: x: float = 1.0
              calculation C {
                x <- "nope"
                result = x
              }
            }
            """
        )


def test_derive_direct_transition_is_rejected() -> None:
    with pytest.raises(PipelineError, match="RE-STATE-002"):
        compiles(
            """
            module M {
              ru: x: int = 0
              derive: active = x < 10
              calculation C {
                active <- true
                result = 1
              }
            }
            """
        )


def test_entity_reassignment_via_equals_is_rejected() -> None:
    with pytest.raises(PipelineError, match="RE-STATE-003"):
        compiles(
            """
            module M {
              ru: x: float = 1.0
              calculation C {
                x = 2.0
                result = x
              }
            }
            """
        )


def test_transition_on_undeclared_target_is_rejected() -> None:
    with pytest.raises(PipelineError, match="RE-STATE-001"):
        compiles(
            """
            module M {
              calculation C {
                y <- 1.0
                result = 1
              }
            }
            """
        )


def test_initializer_type_mismatch_is_rejected() -> None:
    with pytest.raises(PipelineError, match="RE-TYPE-001"):
        compiles(
            """
            module M {
              ru: x: int = 1.5
              calculation C {
                result = x
              }
            }
            """
        )


def test_entity_declaration_outside_module_scope_is_rejected() -> None:
    with pytest.raises(Exception, match="RE-LANG-001"):
        compiles(
            """
            module M {
              calculation C {
                ru: x: float = 1.0
                result = x
              }
            }
            """
        )


def test_state_transition_at_module_scope_is_rejected() -> None:
    with pytest.raises(Exception, match="RE-LANG-002"):
        compiles(
            """
            module M {
              x <- 1.0
              calculation C { result = 1 }
            }
            """
        )


# --- Appendix A: the concrete E1 acceptance criterion -----------------------


def test_appendix_a_compiles() -> None:
    compiles(APPENDIX_A)


def test_appendix_a_executes() -> None:
    # RS-RE-FSM-001 design doc §4 Phase E1: "仕様 Appendix A が実行できる
    # (D-7 の解消の実証)". 5 iterations of loss += learning_rate (0.01).
    assert run_value(APPENDIX_A) == pytest.approx(0.05)


def test_appendix_a_reason_ir_matches_schema() -> None:
    result = compile_source(APPENDIX_A, PATH)
    ir = result.reason_irs[0]
    entities = ir["metadata"]["reason_entities"]
    SCHEMAS.validate_file(entities, "reason_entity.schema.json")
    plan = execution_plan_for(ir)
    SCHEMAS.validate_file(plan, "execution_plan.schema.json")
    assert "entity_plan" in plan


def test_appendix_a_reason_ir_includes_propose_validate_commit_triples() -> None:
    program = parse(APPENDIX_A)
    reason_ir = compile_program(program)[0]
    instructions = reason_ir["metadata"]["reason_entities"]["instructions"]
    ops_by_entity: dict[str, list[str]] = {}
    for instruction in instructions:
        ops_by_entity.setdefault(instruction["entity"], []).append(instruction["op"])
    for ops in ops_by_entity.values():
        for start in range(len(ops) - 2):
            if ops[start] == "ProposeEntityTransition":
                assert ops[start:start + 3] == [
                    "ProposeEntityTransition", "ValidateEntityTransition", "CommitEntityTransition",
                ]


# --- Determinism (RS-RE-FSM-001 §6, §15.4) ----------------------------------


def test_three_independent_compilations_are_byte_identical() -> None:
    def canonical_bytes() -> bytes:
        program = parse(APPENDIX_A)
        reason_ir = compile_program(program)[0]
        plan = execution_plan_for(reason_ir)
        return json.dumps(
            {"reason_ir": reason_ir, "execution_plan": plan},
            ensure_ascii=False, sort_keys=True, indent=2,
        ).encode("utf-8")

    runs = [canonical_bytes() for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


def test_entity_free_program_projection_is_unaffected() -> None:
    # No `metadata.reason_entities` key at all for Entity-free modules --
    # existing canonical artifacts must stay byte-identical (design doc §8).
    program = parse(
        """
        module M {
          calculation C {
            let x = 1
            result = x
          }
        }
        """
    )
    reason_ir = compile_program(program)[0]
    assert "reason_entities" not in reason_ir.get("metadata", {})
    plan = execution_plan_for(reason_ir)
    assert "entity_plan" not in plan
