from __future__ import annotations

from pathlib import Path

from toolchain.code_viewer import Stage, ViewerState, project, render, to_plain_text
from toolchain.code_viewer.filetree import ancestor_directories, scan_project_tree
from toolchain.code_viewer.render import MIN_HEIGHT, MIN_WIDTH, StyleRole


ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_SOURCE = ROOT / "examples" / "v0_5" / "003_calculation_dependency.rsn"
GOLDEN = ROOT / "golden" / "code_viewer" / "calculation_dependency.plain.txt"


def _document():
    # Project with a relative path so the rendered header (and the golden
    # fixture compared against it) doesn't embed a machine-specific
    # absolute path.
    relative_path = Path("examples") / "v0_5" / "003_calculation_dependency.rsn"
    return project(DEPENDENCY_SOURCE.read_text(encoding="utf-8"), relative_path)


def test_render_produces_exactly_height_rows():
    document = _document()
    state = ViewerState(document=document, active_stage=Stage.IR, cursor_line=2)
    frame = render(state, width=80, height=24)
    assert len(frame) == 24


def test_render_clamps_below_minimum_size():
    document = _document()
    state = ViewerState(document=document)
    frame = render(state, width=1, height=1)
    assert len(frame) == MIN_HEIGHT
    for line in frame:
        text = "".join(span.text for span in line)
        assert len(text) <= MIN_WIDTH


def test_render_marks_correlated_declaration_and_stage_nodes():
    # Cursor inside `calculation Base` should light up both the source line
    # and the IR transition whose effect.calculation == "Base" — this is
    # the render-layer proof of the same correlation verified at the
    # projection layer in test_projection.py.
    document = _document()
    state = ViewerState(document=document, active_stage=Stage.IR, cursor_line=2)
    text = to_plain_text(render(state, width=100, height=30))

    rows = [line.split(" | ", 1) for line in text.splitlines()]
    left_column = [row[0] for row in rows]
    right_column = [row[1] if len(row) > 1 else "" for row in rows]

    base_source_line = next(line for line in left_column if "calculation Base" in line)
    assert base_source_line.startswith("▸")

    marked_stage_rows = [index for index, cell in enumerate(right_column) if cell.strip().startswith("▸")]
    assert marked_stage_rows, "expected at least one stage-tree row correlated to the cursor"
    assert any("Base-1-result" in right_column[index + 1] for index in marked_stage_rows)


def test_render_shows_diagnostics_when_stage_unavailable():
    source = "module Broken {\n  calculation X {\n    result = \n  }\n}\n"
    document = project(source, Path("broken.rsn"))
    state = ViewerState(document=document, active_stage=Stage.IR)
    text = to_plain_text(render(state, width=80, height=24))
    assert "SyntaxError" in text


def test_render_matches_golden_layout():
    document = _document()
    state = ViewerState(document=document, active_stage=Stage.IR, cursor_line=2)
    text = to_plain_text(render(state, width=80, height=24))
    expected = GOLDEN.read_text(encoding="utf-8").rstrip("\n")
    assert text == expected


def test_render_help_overlay_replaces_the_normal_layout():
    document = _document()
    state = ViewerState(document=document, show_help=True)
    frame = render(state, width=80, height=20)

    assert len(frame) == 20
    text = to_plain_text(frame)
    assert "keybindings" in text
    assert "q, Ctrl-c" in text
    # Toggling help must not touch anything the plain/--json paths rely on.
    assert "module:" not in text


def test_render_styles_cursor_and_correlated_columns_independently():
    # Regression test for a real bug found during manual P3 testing: the two
    # panes scroll independently, so styling a whole combined row from
    # either half's marker made an unrelated source line "light up" purely
    # because an unrelated stage-tree row happened to share its row index.
    document = _document()
    state = ViewerState(document=document, active_stage=Stage.PLAN, cursor_line=2)
    frame = render(state, width=100, height=15)

    cursor_rows = [
        (row_index, span)
        for row_index, line in enumerate(frame)
        for span in line
        if span.style is StyleRole.CURSOR
    ]
    assert len(cursor_rows) == 1
    _, cursor_span = cursor_rows[0]
    assert "calculation Base" in cursor_span.text

    correlated_rows = [
        (row_index, span)
        for row_index, line in enumerate(frame)
        for span in line
        if span.style is StyleRole.CORRELATED
    ]
    assert correlated_rows, "expected the Base-1-result plan step to be marked CORRELATED"
    for _, span in correlated_rows:
        # None of the correlated spans should be on the same row as the
        # cursor's *left*-column span unless they are themselves the
        # right-column span of that same row (left/right styled apart).
        assert "result = 21" not in span.text


def test_render_diagnostic_style_only_covers_the_stage_pane():
    source = "module Broken {\n  calculation X {\n    result = \n  }\n}\n"
    document = project(source, Path("broken.rsn"))
    state = ViewerState(document=document, active_stage=Stage.IR)
    frame = render(state, width=80, height=24)

    for line in frame:
        for span in line:
            if span.style is StyleRole.DIAGNOSTIC:
                assert "SyntaxError" in span.text or span.text.strip() == ""


def test_render_diagnostics_overlay_lists_every_failing_stage():
    source = "module Broken {\n  calculation X {\n    result = \n  }\n}\n"
    document = project(source, Path("broken.rsn"))
    state = ViewerState(document=document, show_diagnostics=True)
    frame = render(state, width=80, height=20)

    assert len(frame) == 20
    text = to_plain_text(frame)
    assert "Diagnostics" in text
    assert "[Surface]" in text
    assert "SyntaxError" in text
    assert "Press any key to close" in text


def test_render_diagnostics_overlay_reports_when_everything_compiled_cleanly():
    document = _document()
    state = ViewerState(document=document, show_diagnostics=True)
    text = to_plain_text(render(state, width=80, height=15))
    assert "compiled cleanly" in text


def test_render_footer_shows_search_input_while_typing():
    document = _document()
    state = ViewerState(document=document, search_input="Ba")
    text = to_plain_text(render(state, width=80, height=24))
    assert text.splitlines()[-1].startswith("/Ba")


def test_render_footer_shows_status_message_and_active_search_query():
    document = _document()
    state = ViewerState(document=document, search_query="Base", status_message="2 match(es) for 'Base'")
    # Wide enough that neither piece competes with the other for truncation
    # budget — footer priority/truncation itself is covered separately.
    footer = to_plain_text(render(state, width=140, height=24)).splitlines()[-1]
    assert "2 match(es) for 'Base'" in footer
    assert "search 'Base' (n/p)" in footer


# --- file tree overlay (design doc §17) -----------------------------------


def _tree_project(tmp_path):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "water.rsn").write_text("module Water {}\n", encoding="utf-8")
    (tmp_path / "models" / "hydrogen.rsn").write_text("module Hydrogen {}\n", encoding="utf-8")
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "decay.rsn").write_text("module Decay {}\n", encoding="utf-8")
    return tmp_path


def test_render_file_tree_replaces_the_normal_layout(tmp_path):
    root = _tree_project(tmp_path)
    tree = scan_project_tree(root)
    document = _document()
    state = ViewerState(document=document, show_file_tree=True, tree_root=root, tree=tree)

    # tmp_path can be long (especially under macOS's default temp dir), so
    # use a wide render here — the header-truncation budget is already
    # covered by the shared _fit() tests elsewhere.
    frame = render(state, width=160, height=15)

    assert len(frame) == 15
    text = to_plain_text(frame)
    assert "File Tree" in text
    assert str(root) in text
    assert "models/" in text
    assert "rules/" in text
    # Collapsed by default: children aren't shown until expanded.
    assert "water.rsn" not in text
    assert "module:" not in text  # main layout must not leak through


def test_render_file_tree_expands_only_the_expanded_directory(tmp_path):
    root = _tree_project(tmp_path)
    tree = scan_project_tree(root)
    document = _document()
    models_path = (root / "models").resolve()
    state = ViewerState(
        document=document, show_file_tree=True, tree_root=root, tree=tree,
        tree_expanded=frozenset({models_path}),
    )

    text = to_plain_text(render(state, width=80, height=15))

    assert "water.rsn" in text
    assert "hydrogen.rsn" in text
    assert "decay.rsn" not in text  # rules/ is still collapsed


def test_render_file_tree_highlights_cursor_and_currently_open_file(tmp_path):
    root = _tree_project(tmp_path)
    tree = scan_project_tree(root)
    water_path = (root / "models" / "water.rsn").resolve()
    document = project(water_path.read_text(encoding="utf-8"), water_path)
    state = ViewerState(
        document=document, show_file_tree=True, tree_root=root, tree=tree,
        tree_expanded=frozenset({(root / "models").resolve()}), tree_cursor=1,
    )

    frame = render(state, width=80, height=15)
    styled = [(span.text.strip(), span.style) for line in frame for span in line if span.text.strip()]

    cursor_rows = [text for text, style in styled if style is StyleRole.CURSOR]
    assert any("hydrogen.rsn" in text for text in cursor_rows)  # row index 1 = hydrogen.rsn

    current_file_rows = [text for text, style in styled if style is StyleRole.CORRELATED]
    assert any("water.rsn" in text for text in current_file_rows)


def test_render_file_tree_shows_placeholder_when_no_rsn_files_found(tmp_path):
    document = _document()
    state = ViewerState(document=document, show_file_tree=True, tree_root=tmp_path, tree=None)

    text = to_plain_text(render(state, width=80, height=15))
    assert "no .rsn files found" in text


def test_ancestor_directories_can_seed_initial_tree_expansion(tmp_path):
    # Exercises the design doc §17.11 point 1 use case: auto-expand just
    # enough of the tree to reveal the file that's already open.
    root = _tree_project(tmp_path)
    tree = scan_project_tree(root)
    water_path = (root / "models" / "water.rsn").resolve()

    expanded = ancestor_directories(tree, water_path)
    document = project(water_path.read_text(encoding="utf-8"), water_path)
    state = ViewerState(document=document, show_file_tree=True, tree_root=root, tree=tree, tree_expanded=expanded)

    text = to_plain_text(render(state, width=80, height=15))
    assert "water.rsn" in text
    assert "decay.rsn" not in text  # rules/ wasn't on the path to water.rsn
