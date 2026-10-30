from frontend.computation_ir.differential import assert_same_outcome
from frontend.language_surface import parse, validate
from frontend.computation_ir import lower_program
from frontend.computation_ir.rust_bridge import find_binary, run_ir


def test_string_ordering_uses_unicode_codepoints():
    source = '''module Strings {
 calculation Result {
   result = ["a" < "b", "界" > "z", "a" <= "a", "z" >= "界"]
 }
}'''
    validate(parse(source))
    assert assert_same_outcome(source).calculations["Result"] == [True, True, True, False]

    if find_binary() is not None:
        native = run_ir(lower_program(parse(source)))
        assert native.ok
        assert next(iter(native.calculation_results.values())) == [True, True, True, False]
