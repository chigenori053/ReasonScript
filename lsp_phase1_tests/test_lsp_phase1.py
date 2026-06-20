from __future__ import annotations

from pathlib import Path

from frontend.lsp import SCHEMA, ReasonScriptLanguageServer


MAIN_URI = "file:///workspace/main.rsn"
NAV_URI = "file:///workspace/nav.rsn"


MAIN_SOURCE = """package world
module navigation {
export struct Route {
distance: int
}
export enum Direction {
North
South
}
export const max_steps: int = 10
export fn plan_route(destination): int {
return max_steps
}
goal ReachDestination {
description: arrive
}
state Start
state Arrived
constraint DoorOpen {
Start == Start
}
reason_graph NavigationGraph {
state Start
state Arrived
transition Start -> Arrived
}
execution_plan RoutePlan {
step Start -> Arrived
}
}
"""


NAV_SOURCE = """package world
module agent {
import world.navigation
fn choose(): int {
return plan_route("home")
}
goal ReachDestination
}
"""


def _server() -> ReasonScriptLanguageServer:
    server = ReasonScriptLanguageServer()
    server.open_document(MAIN_URI, MAIN_SOURCE, 1)
    server.open_document(NAV_URI, NAV_SOURCE, 1)
    return server


def _position(source: str, text: str) -> tuple[int, int]:
    for line, value in enumerate(source.splitlines()):
        column = value.find(text)
        if column >= 0:
            return line, column
    raise AssertionError(text)


def test_lsp1_001_diagnostics_and_schema_metadata():
    server = _server()
    assert server.schema == SCHEMA == "reasonscript-lsp/0.1"
    assert server.diagnostics(MAIN_URI) == ()


def test_lsp1_002_syntax_diagnostics_are_structured():
    server = ReasonScriptLanguageServer()
    server.open_document("file:///broken.rsn", "module Broken {\nfn nope(\n", 1)
    diagnostic = server.diagnostics("file:///broken.rsn")[0]
    assert diagnostic.code == "SyntaxError"
    assert diagnostic.severity.value == "Error"
    assert diagnostic.location.uri == "file:///broken.rsn"


def test_lsp1_003_hover_function():
    server = _server()
    line, character = _position(MAIN_SOURCE, "plan_route")
    hover = server.hover(MAIN_URI, line, character)
    assert hover is not None
    assert "Function" in hover.contents
    assert "Name: plan_route" in hover.contents


def test_lsp1_004_hover_goal():
    server = _server()
    line, character = _position(MAIN_SOURCE, "ReachDestination")
    hover = server.hover(MAIN_URI, line, character)
    assert hover is not None
    assert "Goal" in hover.contents
    assert "Module: world.navigation" in hover.contents


def test_lsp1_005_completion_keywords():
    labels = {item.label for item in _server().completion(MAIN_URI, 0, 0)}
    assert {"goal", "state", "reason_graph", "execution_plan"}.issubset(labels)


def test_lsp1_006_completion_runtime_api():
    labels = {item.label for item in _server().completion(MAIN_URI, 0, 0)}
    assert {"runtime.search", "runtime.plan", "runtime.predict", "runtime.simulate"}.issubset(labels)


def test_lsp1_007_completion_world_types():
    labels = {item.label for item in _server().completion(MAIN_URI, 0, 0)}
    assert {"World", "Scene", "Entity", "Object", "Relation", "Snapshot", "SceneTemplate"}.issubset(labels)


def test_lsp1_008_go_to_definition_function():
    server = _server()
    line, character = _position(NAV_SOURCE, "plan_route")
    location = server.definition(NAV_URI, line, character)
    assert location is not None
    assert location.uri == MAIN_URI
    assert location.range.start.line == _position(MAIN_SOURCE, "plan_route")[0]


def test_lsp1_009_go_to_definition_module():
    server = _server()
    line, character = _position(NAV_SOURCE, "navigation")
    location = server.definition(NAV_URI, line, character)
    assert location is not None
    assert location.uri == MAIN_URI


def test_lsp1_010_find_references_function():
    server = _server()
    line, character = _position(MAIN_SOURCE, "plan_route")
    references = server.references(MAIN_URI, line, character)
    assert {item.uri for item in references} == {MAIN_URI, NAV_URI}
    assert len(references) == 2


def test_lsp1_011_find_references_goal():
    server = _server()
    line, character = _position(MAIN_SOURCE, "ReachDestination")
    references = server.references(MAIN_URI, line, character)
    assert len([item for item in references if item.uri in {MAIN_URI, NAV_URI}]) == 2


def test_lsp1_012_symbol_index_function():
    symbols = _server().workspace_symbols()
    assert any(symbol.kind == "Function" and symbol.name == "plan_route" for symbol in symbols)


def test_lsp1_013_symbol_index_world_types():
    symbols = _server().workspace_symbols()
    assert any(symbol.kind == "WorldType" and symbol.name == "Scene" for symbol in symbols)


def test_lsp1_014_multi_module_navigation():
    server = _server()
    line, character = _position(NAV_SOURCE, "plan_route")
    location = server.definition(NAV_URI, line, character)
    assert location is not None
    assert location.uri == MAIN_URI


def test_lsp1_015_runtime_namespace_support():
    server = _server()
    source = "module RuntimeUse {\nfn search(): int {\nruntime.search(\"dog\")\nreturn 1\n}\n}\n"
    uri = "file:///runtime.rsn"
    server.open_document(uri, source, 1)
    line, character = _position(source, "runtime.search")
    hover = server.hover(uri, line, character)
    assert hover is not None
    assert "RuntimeAPI" in hover.contents


def test_lsp1_016_world_sdk_support():
    server = _server()
    symbol = next(item for item in server.workspace_symbols() if item.name == "SimulationTrace")
    assert symbol.kind == "WorldType"
    assert symbol.visibility == "Public"


def test_lsp1_017_incremental_analysis():
    server = _server()
    changed = MAIN_SOURCE.replace("state Arrived", "state Completed")
    state = server.change_document(MAIN_URI, changed, 2)
    assert state.version == 2
    assert any(symbol.name == "Completed" for symbol in server.workspace_symbols())
    assert not any(symbol.location.uri == MAIN_URI and symbol.name == "Arrived" for symbol in server.workspace_symbols())


def test_lsp1_018_cache_validation():
    server = _server()
    state = server.documents[MAIN_URI]
    assert state.ast is not None
    assert state.symbols
    assert state.diagnostics == ()
    assert server.save_document(MAIN_URI) is state


def test_lsp1_019_error_recovery():
    server = ReasonScriptLanguageServer()
    source = "module Broken {\nfn nope(\ngoal Recoverable\n"
    server.open_document("file:///recover.rsn", source, 1)
    assert server.diagnostics("file:///recover.rsn")
    assert any(symbol.name == "Recoverable" for symbol in server.workspace_symbols())


def test_lsp1_020_workspace_scan(tmp_path: Path):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "a.rsn").write_text(MAIN_SOURCE, encoding="utf-8")
    (root / "b.rsn").write_text(NAV_SOURCE, encoding="utf-8")
    symbols = ReasonScriptLanguageServer().scan_workspace(root)
    assert any(symbol.name == "plan_route" for symbol in symbols)
    assert any(symbol.name == "choose" for symbol in symbols)
