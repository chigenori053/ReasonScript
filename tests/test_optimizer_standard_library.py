import pytest

from frontend.integrated_computation_runtime import execute_program
from frontend.language_surface import parse


def test_adam_and_scheduler_are_functional_and_traceable():
    program = parse(
        """
        module Train {
          calculation Main {
            let parameter = tensor.parameter(tensor.create([1.0], dtype = "f64"))
            let gradient = tensor.create([0.5], dtype = "f64")
            let update = optimizer.adam([parameter], [gradient], null, 0.1)
            let decayed = scheduler.step_decay(0.1, 5, 5)
            result = [update.parameters[0], decayed]
          }
        }
        """
    )

    result = execute_program(program).to_dict()
    assert result["result"][0] == pytest.approx([0.900000002])
    assert result["result"][1] == pytest.approx(0.01)
    assert [entry["function_id"] for entry in result["tensor_trace"] if entry["operation_type"] == "optimizer_call"] == [
        "optimizer.adam", "scheduler.step_decay"
    ]


def test_sgd_and_momentum_return_next_parameters_and_explicit_state():
    program = parse(
        """
        module Train {
          calculation Main {
            let parameter = tensor.parameter(tensor.create([1.0], dtype = "f64"))
            let gradient = tensor.create([0.5], dtype = "f64")
            let sgd = optimizer.sgd([parameter], [gradient], 0.2)
            let momentum = optimizer.momentum(sgd, [gradient], null, 0.2)
            result = [momentum.parameters[0], momentum.state.velocity[0]]
          }
        }
        """
    )

    assert execute_program(program).to_dict()["result"] == [[0.8], [0.5]]
