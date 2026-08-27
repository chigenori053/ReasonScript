from frontend.reason_ir_optimization import PureReasonFunction, constant_fold, is_loop_invariant


def test_small_pure_function_is_fast_path_eligible():
    assert PureReasonFunction("score", 32).eligible_for_fast_path
    assert not PureReasonFunction("write", 2, writes_artifact=True).eligible_for_fast_path


def test_constant_folding_preserves_division_semantics():
    assert constant_fold({"operator": "/", "left": 1, "right": 4}) == {"kind": "literal", "value": 0.25}


def test_loop_invariant_rejects_mutable_and_observation_values():
    assert is_loop_invariant({"kind": "identifier", "name": "scale"}, {"index"})
    assert not is_loop_invariant({"kind": "identifier", "name": "index"}, {"index"})
    assert not is_loop_invariant({"observation_dependency": True}, set())
