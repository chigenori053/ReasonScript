"""Phase 18: Surface AST and Reason IR graph-binding integration."""

from frontend.language_surface import compile_program, parse


def test_phase18_reason_graph_binding_projects_to_reason_ir() -> None:
    source = '''module GraphBinding {
reason_graph graph from "graph.rgraph" as "ruo:graph:phase2-fixture";
}
'''
    program = parse(source)
    ir = compile_program(program)[0]

    binding = ir["metadata"]["reason_graph_bindings"][0]
    assert binding["node_type"] == "ReasonGraphBindingIR"
    assert binding["logical_source_ref"] == "graph.rgraph"
    assert binding["read_only"] is True
