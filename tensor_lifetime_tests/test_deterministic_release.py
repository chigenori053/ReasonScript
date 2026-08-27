import pytest

from frontend.language_surface import compile_program, parse
from frontend.tensor.runtime import TensorError, TensorPolicy, TensorRuntime


SOURCE = """module Lifetime {
  calculation Graph {
    let a = tensor.create([1.0], "f64")
    let b = tensor.create([2.0], "f64")
    let total = tensor.add(a, b)
    let scaled = tensor.multiply(a, 3.0)
    let answer = tensor.add(total, scaled)
    result = answer
  }
}
"""


def _plan():
    reason_ir = compile_program(parse(SOURCE))[0]
    return reason_ir["metadata"]["tensor_execution_plan"]["operations"]


def test_temporary_tensor_is_explicitly_released_and_traced():
    runtime = TensorRuntime()
    value = runtime.create([1.0])
    assert runtime.release(value)
    assert value.tensor_id not in runtime._refs
    assert runtime.lifecycle_trace[-1]["operation_type"] == "tensor_release"


def test_persistent_values_are_not_released_by_collection():
    runtime = TensorRuntime()
    value = runtime.classify(runtime.create([1.0]), "Persistent")
    assert runtime.collect() == 0
    assert value.tensor_id in runtime._refs


def test_uera_t007_reason_ir_computes_dependency_ref_counts_and_last_use():
    operations = _plan()
    assert [operation["dependencies"] for operation in operations] == [
        [],
        [],
        ["tensor_value_001", "tensor_value_002"],
        ["tensor_value_001"],
        ["tensor_value_003", "tensor_value_004"],
    ]
    assert [operation["ref_count"] for operation in operations] == [2, 1, 1, 1, 0]
    assert [operation["last_use_step"] for operation in operations] == [4, 3, 5, 5, 5]
    assert operations[2]["release_after"] == ["tensor_value_002"]
    assert operations[3]["release_after"] == ["tensor_value_001"]
    assert operations[4]["release_after"] == [
        "tensor_value_003",
        "tensor_value_004",
    ]
    assert operations[4]["lifecycle"] == "Observation"


def test_uera_t007_runtime_releases_a_dependency_only_after_its_last_use():
    operations = _plan()
    runtime = TensorRuntime()
    a = runtime.execute_planned(operations[0], [1.0], "f64")
    b = runtime.execute_planned(operations[1], [2.0], "f64")
    total = runtime.execute_planned(operations[2], a, b)
    assert b.tensor_id not in runtime._refs
    assert a.tensor_id in runtime._refs
    scaled = runtime.execute_planned(operations[3], a, 3.0)
    assert a.tensor_id not in runtime._refs
    answer = runtime.execute_planned(operations[4], total, scaled)

    assert runtime.to_array(answer) == [6.0]
    assert set(runtime._refs) == {answer.tensor_id}
    assert runtime.lifetime_metrics() == {
        "tensor_allocations": 5,
        "tensor_releases": 4,
        "live_tensors": 1,
        "peak_live_tensors": 3,
        "hard_limit": 1_000,
    }
    assert [event["reason"] for event in runtime.lifecycle_trace] == [
        "last_use_step:3",
        "last_use_step:4",
        "last_use_step:5",
        "last_use_step:5",
    ]


def test_only_the_final_generation_of_an_escaping_binding_is_observed():
    source = """module Reassignment {
      calculation Graph {
        let value = tensor.create([1.0])
        value = tensor.relu(value)
        result = value
      }
    }
    """
    operations = compile_program(parse(source))[0]["metadata"][
        "tensor_execution_plan"
    ]["operations"]
    assert [operation["lifecycle"] for operation in operations] == [
        "Intermediate",
        "Observation",
    ]
    assert operations[1]["release_after"] == ["tensor_value_001"]


def test_uera_t008_parameter_persistent_and_artifact_survive_collection(tmp_path):
    runtime = TensorRuntime()
    parameter = runtime.parameter(runtime.create([1.0], "f64"))
    persistent = runtime.classify(runtime.create([2.0]), "Persistent")
    artifact = runtime.create([3.0])
    runtime.artifact(artifact, tmp_path)

    runtime.collect()

    assert {parameter.tensor_id, persistent.tensor_id, artifact.tensor_id} <= set(
        runtime._refs
    )
    assert runtime._classifications[parameter.tensor_id] == "Parameter"
    assert runtime._classifications[persistent.tensor_id] == "Persistent"
    assert runtime._classifications[artifact.tensor_id] == "Artifact"


def test_uera_t008_hard_limit_is_configurable_last_resort():
    runtime = TensorRuntime(policy=TensorPolicy(max_live_tensors=1))
    runtime.create([1.0])
    with pytest.raises(TensorError) as captured:
        runtime.create([2.0])
    diagnostic = captured.value.diagnostic.to_dict()
    assert diagnostic["code"] == "TSF-013"
    assert diagnostic["details"] == {"live_tensors": 1, "hard_limit": 1}
