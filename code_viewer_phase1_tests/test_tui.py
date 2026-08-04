from __future__ import annotations

from pathlib import Path

import pytest

curses = pytest.importorskip("curses")

from toolchain.code_viewer import Stage, ViewerState, project
from toolchain.code_viewer.filetree import flatten_file_tree, scan_project_tree
from toolchain.code_viewer.tui import (
    _apply_pending_open,
    _copy_node,
    _cycle_stage,
    _follow_cursor,
    _handle_key,
    _jump_anchor,
    _move,
    _reveal_path,
    _search_matches,
)


ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_SOURCE = ROOT / "examples" / "v0_5" / "003_calculation_dependency.rsn"

CONTENT_HEIGHT = 20


def _state(**overrides) -> ViewerState:
    document = project(DEPENDENCY_SOURCE.read_text(encoding="utf-8"), DEPENDENCY_SOURCE)
    return ViewerState(document=document, **overrides)


def test_digit_keys_switch_stage_and_reset_stage_scroll():
    state = _state(active_stage=Stage.SOURCE, stage_scroll=5)
    new_state = _handle_key(state, ord("4"), CONTENT_HEIGHT)
    assert new_state.active_stage is Stage.IR
    assert new_state.stage_scroll == 0


def test_tab_cycles_forward_and_wraps():
    state = _state(active_stage=Stage.SOURCE)
    for stage in (Stage.SURFACE, Stage.SEMANTIC, Stage.IR, Stage.PLAN, Stage.SOURCE):
        state = _cycle_stage(state, 1)
        assert state.active_stage is stage


def test_shift_tab_cycles_backward():
    state = _state(active_stage=Stage.PLAN)
    state = _cycle_stage(state, -1)
    assert state.active_stage is Stage.IR


def test_j_and_k_move_cursor_within_source_bounds():
    state = _state(cursor_line=1)
    down = _handle_key(state, ord("j"), CONTENT_HEIGHT)
    assert down.cursor_line == 2

    top = _handle_key(state, ord("k"), CONTENT_HEIGHT)
    assert top.cursor_line == 1  # already at line 1, clamped


def test_cursor_cannot_move_past_last_source_line():
    document = project(DEPENDENCY_SOURCE.read_text(encoding="utf-8"), DEPENDENCY_SOURCE)
    last_line = len(document.source_lines)
    state = ViewerState(document=document, cursor_line=last_line)
    moved = _handle_key(state, ord("j"), CONTENT_HEIGHT)
    assert moved.cursor_line == last_line


def test_ctrl_d_and_ctrl_u_scroll_by_half_page():
    # The fixture source is short (9 lines), shorter than a half-page at
    # CONTENT_HEIGHT=20, so use a small viewport instead so the movement
    # isn't immediately clamped against the end of the file.
    small_viewport = 6
    state = _state(cursor_line=1)
    down = _handle_key(state, 4, small_viewport)  # Ctrl-D
    assert down.cursor_line == 1 + small_viewport // 2

    up = _handle_key(down, 21, small_viewport)  # Ctrl-U
    assert up.cursor_line == down.cursor_line - small_viewport // 2


def test_n_and_p_jump_between_declarations_in_source_order():
    state = _state(cursor_line=1)  # inside the module, before any calculation
    first = _handle_key(state, ord("n"), CONTENT_HEIGHT)
    second = _handle_key(first, ord("n"), CONTENT_HEIGHT)
    back = _handle_key(second, ord("p"), CONTENT_HEIGHT)

    assert [a.source_line for a in state.document.anchors] == sorted(
        a.source_line for a in state.document.anchors
    )
    assert first.cursor_line < second.cursor_line
    assert back.cursor_line == first.cursor_line


def test_n_wraps_to_first_anchor_past_the_last_one():
    document = project(DEPENDENCY_SOURCE.read_text(encoding="utf-8"), DEPENDENCY_SOURCE)
    last_anchor_line = max(a.source_line for a in document.anchors)
    state = ViewerState(document=document, cursor_line=last_anchor_line)
    wrapped = _handle_key(state, ord("n"), CONTENT_HEIGHT)
    assert wrapped.cursor_line == min(a.source_line for a in document.anchors)


def test_enter_focuses_stage_pane_and_esc_returns_focus_to_source():
    state = _state(focus="source")
    focused = _handle_key(state, curses.KEY_ENTER, CONTENT_HEIGHT)
    assert focused.focus == "stage"

    back = _handle_key(focused, 27, CONTENT_HEIGHT)  # Esc
    assert back.focus == "source"


def test_movement_targets_stage_cursor_when_focus_is_stage():
    # P4 gives the stage pane its own selectable row (stage_cursor), needed
    # so `y` has something addressable to copy — plain scrolling (P3) had
    # no notion of "the selected node".
    state = _state(active_stage=Stage.IR, focus="stage", stage_cursor=0)
    moved = _handle_key(state, ord("j"), CONTENT_HEIGHT)
    assert moved.stage_cursor == 1
    assert moved.cursor_line == state.cursor_line  # source cursor untouched


def test_stage_cursor_is_clamped_to_available_nodes():
    state = _state(active_stage=Stage.PLAN, focus="stage", stage_cursor=0)
    node_count = len(state.document.stages[Stage.PLAN].nodes)
    over_moved = _move(state, node_count + 50, CONTENT_HEIGHT)
    assert over_moved.stage_cursor == node_count - 1


def test_stage_scroll_follows_stage_cursor_out_of_the_visible_window():
    small_viewport = 3
    state = _state(active_stage=Stage.PLAN, focus="stage", stage_cursor=0, stage_scroll=0)
    moved = _move(state, small_viewport + 2, small_viewport)
    assert moved.stage_cursor - moved.stage_scroll < small_viewport
    assert moved.stage_cursor - moved.stage_scroll >= 0


def test_digit_and_tab_reset_stage_cursor_along_with_stage_scroll():
    state = _state(active_stage=Stage.SOURCE, stage_cursor=3, stage_scroll=5)
    switched = _handle_key(state, ord("4"), CONTENT_HEIGHT)
    assert switched.stage_cursor == 0
    assert switched.stage_scroll == 0


def test_question_mark_toggles_help_and_any_key_closes_it():
    state = _state(show_help=False)
    opened = _handle_key(state, ord("?"), CONTENT_HEIGHT)
    assert opened.show_help is True

    closed = _handle_key(opened, ord("j"), CONTENT_HEIGHT)
    assert closed.show_help is False
    # closing help must not also apply the "j" as a cursor move
    assert closed.cursor_line == opened.cursor_line


def test_follow_cursor_scrolls_only_when_cursor_leaves_the_visible_window():
    assert _follow_cursor(scroll=0, cursor_line=5, content_height=10) == 0
    assert _follow_cursor(scroll=0, cursor_line=11, content_height=10) == 1
    assert _follow_cursor(scroll=5, cursor_line=3, content_height=10) == 2


def test_jump_anchor_updates_source_scroll_to_keep_target_visible():
    document = project(DEPENDENCY_SOURCE.read_text(encoding="utf-8"), DEPENDENCY_SOURCE)
    state = ViewerState(document=document, cursor_line=1, source_scroll=0)
    small_viewport = 2
    jumped = _jump_anchor(state, 1, small_viewport)
    assert jumped.cursor_line - jumped.source_scroll <= small_viewport
    assert jumped.cursor_line - jumped.source_scroll >= 1


# --- P4: search ("/") ---------------------------------------------------


def test_slash_enters_search_typing_mode():
    state = _state()
    typing = _handle_key(state, ord("/"), CONTENT_HEIGHT)
    assert typing.search_input == ""
    assert typing.search_query is None


def test_typing_appends_to_search_buffer_and_backspace_removes():
    state = _handle_key(_state(), ord("/"), CONTENT_HEIGHT)
    for char in "Base":
        state = _handle_key(state, ord(char), CONTENT_HEIGHT)
    assert state.search_input == "Base"

    backspaced = _handle_key(state, curses.KEY_BACKSPACE, CONTENT_HEIGHT)
    assert backspaced.search_input == "Bas"


def test_esc_while_typing_cancels_the_search_without_committing():
    state = _handle_key(_state(), ord("/"), CONTENT_HEIGHT)
    state = _handle_key(state, ord("x"), CONTENT_HEIGHT)
    cancelled = _handle_key(state, 27, CONTENT_HEIGHT)  # Esc
    assert cancelled.search_input is None
    assert cancelled.search_query is None


def test_enter_commits_search_and_jumps_to_first_match_at_or_after_cursor():
    # "Base" appears on source line 2 (the declaration) and line 7 (a
    # reference inside `calculation Answer`).
    state = _state(cursor_line=3)  # already past line 2's match
    state = _handle_key(state, ord("/"), CONTENT_HEIGHT)
    for char in "Base":
        state = _handle_key(state, ord(char), CONTENT_HEIGHT)
    committed = _handle_key(state, ord("\n"), CONTENT_HEIGHT)

    assert committed.search_input is None
    assert committed.search_query == "Base"
    assert committed.cursor_line == 7  # first match at/after line 3
    assert committed.focus == "source"
    assert committed.status_message is not None


def test_empty_search_commit_clears_query_instead_of_matching_everything():
    state = _handle_key(_state(), ord("/"), CONTENT_HEIGHT)
    committed = _handle_key(state, ord("\n"), CONTENT_HEIGHT)
    assert committed.search_input is None
    assert committed.search_query is None


def test_n_and_p_step_through_search_matches_once_a_search_is_active():
    state = _state(cursor_line=1, search_query="result")
    # "result" appears on source lines 3 and 7.
    forward = _handle_key(state, ord("n"), CONTENT_HEIGHT)
    assert forward.cursor_line == 3
    forward_again = _handle_key(forward, ord("n"), CONTENT_HEIGHT)
    assert forward_again.cursor_line == 7
    wrapped = _handle_key(forward_again, ord("n"), CONTENT_HEIGHT)
    assert wrapped.cursor_line == 3  # wraps back to the first match

    backward = _handle_key(forward_again, ord("p"), CONTENT_HEIGHT)
    assert backward.cursor_line == 3


def test_n_falls_back_to_anchor_jump_when_no_search_is_active():
    state = _state(cursor_line=1, search_query=None)
    stepped = _handle_key(state, ord("n"), CONTENT_HEIGHT)
    # Anchors, not "result" lines — matches test_n_and_p_jump_between_declarations.
    assert stepped.cursor_line in {a.source_line for a in state.document.anchors}


def test_esc_clears_an_active_search_before_touching_focus():
    state = _state(search_query="Base", focus="stage")
    cleared = _handle_key(state, 27, CONTENT_HEIGHT)  # Esc
    assert cleared.search_query is None
    assert cleared.focus == "stage"  # first Esc only clears the search

    unfocused = _handle_key(cleared, 27, CONTENT_HEIGHT)  # Esc again
    assert unfocused.focus == "source"


def test_search_matches_is_case_insensitive():
    document = project(DEPENDENCY_SOURCE.read_text(encoding="utf-8"), DEPENDENCY_SOURCE)
    assert _search_matches(document, "base") == [2, 7]
    assert _search_matches(document, "BASE") == [2, 7]


def test_search_with_no_matches_reports_status_without_moving_cursor():
    state = _state(cursor_line=1)
    state = _handle_key(state, ord("/"), CONTENT_HEIGHT)
    for char in "nope":
        state = _handle_key(state, ord(char), CONTENT_HEIGHT)
    committed = _handle_key(state, ord("\n"), CONTENT_HEIGHT)
    assert committed.cursor_line == 1
    assert committed.search_query is None
    assert "no matches" in (committed.status_message or "")


# --- P4: diagnostics overlay ("d") ---------------------------------------


def test_d_toggles_diagnostics_and_is_mutually_exclusive_with_help():
    state = _state(show_help=True)
    toggled = _handle_key(state, ord("d"), CONTENT_HEIGHT)
    assert toggled.show_diagnostics is True
    assert toggled.show_help is False

    closed = _handle_key(toggled, ord("j"), CONTENT_HEIGHT)
    assert closed.show_diagnostics is False


# --- P4: copy ("y") -------------------------------------------------------


def test_y_reports_a_hint_when_focus_is_not_the_stage_pane():
    state = _state(focus="source")
    result = _copy_node(state)
    assert result.status_message is not None
    assert "focus" in result.status_message.lower()


def test_y_copies_the_selected_stage_nodes_json_pointer(monkeypatch):
    monkeypatch.setattr("toolchain.code_viewer.tui._copy_to_clipboard", lambda _: True)
    state = _state(active_stage=Stage.PLAN, focus="stage", stage_cursor=0)
    node = state.document.stages[Stage.PLAN].nodes[0]

    result = _copy_node(state)

    assert result.status_message == f"copied {node.json_pointer}"


def test_y_reports_failure_when_no_clipboard_tool_is_available(monkeypatch):
    monkeypatch.setattr("toolchain.code_viewer.tui._copy_to_clipboard", lambda _: False)
    state = _state(active_stage=Stage.PLAN, focus="stage", stage_cursor=0)

    result = _copy_node(state)

    assert result.status_message is not None
    assert "could not copy" in result.status_message


# --- P4: minimum terminal size (CV-004) -----------------------------------


def test_min_width_and_height_constants_match_the_documented_minimum():
    from toolchain.code_viewer.render import MIN_HEIGHT, MIN_WIDTH

    assert (MIN_WIDTH, MIN_HEIGHT) == (40, 10)


# --- file tree (design doc §17) --------------------------------------------


def _tree_state(tmp_path, **overrides):
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "water.rsn").write_text("module Water {}\n", encoding="utf-8")
    (tmp_path / "models" / "hydrogen.rsn").write_text("module Hydrogen {}\n", encoding="utf-8")
    (tmp_path / "rules").mkdir()
    (tmp_path / "rules" / "decay.rsn").write_text("module Decay {}\n", encoding="utf-8")
    tree = scan_project_tree(tmp_path)
    document = project(DEPENDENCY_SOURCE.read_text(encoding="utf-8"), DEPENDENCY_SOURCE)
    state = ViewerState(document=document, tree_root=tmp_path, tree=tree, **overrides)
    return state, tree


def test_e_toggles_file_tree_open_and_closed(tmp_path):
    state, _ = _tree_state(tmp_path)
    opened = _handle_key(state, ord("e"), CONTENT_HEIGHT)
    assert opened.show_file_tree is True

    closed = _handle_key(opened, ord("e"), CONTENT_HEIGHT)
    assert closed.show_file_tree is False


def test_e_reveals_the_currently_open_file_each_time_it_opens(tmp_path):
    state, tree = _tree_state(tmp_path)
    water = (tmp_path / "models" / "water.rsn").resolve()
    document = project(water.read_text(encoding="utf-8"), water)
    state = ViewerState(document=document, tree_root=tmp_path, tree=tree)

    opened = _handle_key(state, ord("e"), CONTENT_HEIGHT)

    rows = flatten_file_tree(tree, opened.tree_expanded)
    assert rows[opened.tree_cursor].path == water
    assert (tmp_path / "models").resolve() in opened.tree_expanded


def test_e_reports_status_when_no_project_root_is_configured():
    state = _state(tree_root=None)
    result = _handle_key(state, ord("e"), CONTENT_HEIGHT)
    assert result.show_file_tree is False
    assert result.status_message is not None


def test_tree_j_k_move_cursor_and_wrap_stops_at_bounds(tmp_path):
    state, _ = _tree_state(tmp_path)
    opened = _handle_key(state, ord("e"), CONTENT_HEIGHT)  # collapsed: 2 top-level rows (models/, rules/)

    down = _handle_key(opened, ord("j"), CONTENT_HEIGHT)
    assert down.tree_cursor == 1
    past_end = _handle_key(down, ord("j"), CONTENT_HEIGHT)
    assert past_end.tree_cursor == 1  # clamped, only 2 rows while collapsed

    up = _handle_key(past_end, ord("k"), CONTENT_HEIGHT)
    assert up.tree_cursor == 0
    past_start = _handle_key(up, ord("k"), CONTENT_HEIGHT)
    assert past_start.tree_cursor == 0


def test_tree_enter_on_directory_expands_it_without_closing_the_tree(tmp_path):
    state, _ = _tree_state(tmp_path)
    opened = _handle_key(state, ord("e"), CONTENT_HEIGHT)  # cursor on row 0: models/

    expanded = _handle_key(opened, ord("l"), CONTENT_HEIGHT)

    assert expanded.show_file_tree is True
    assert (tmp_path / "models").resolve() in expanded.tree_expanded


def test_tree_h_collapses_an_expanded_directory(tmp_path):
    state, _ = _tree_state(tmp_path)
    opened = _handle_key(state, ord("e"), CONTENT_HEIGHT)
    expanded = _handle_key(opened, ord("l"), CONTENT_HEIGHT)

    collapsed = _handle_key(expanded, ord("h"), CONTENT_HEIGHT)

    assert (tmp_path / "models").resolve() not in collapsed.tree_expanded


def test_tree_h_on_a_child_jumps_cursor_to_its_parent_directory(tmp_path):
    state, _ = _tree_state(tmp_path)
    opened = _handle_key(state, ord("e"), CONTENT_HEIGHT)
    expanded = _handle_key(opened, ord("l"), CONTENT_HEIGHT)  # models/ expanded
    down = _handle_key(expanded, ord("j"), CONTENT_HEIGHT)  # cursor -> hydrogen.rsn (row 1)

    jumped = _handle_key(down, ord("h"), CONTENT_HEIGHT)

    rows = flatten_file_tree(state.tree, jumped.tree_expanded)
    assert rows[jumped.tree_cursor].name == "models"


def test_tree_enter_on_a_file_sets_pending_open_and_closes_the_tree(tmp_path):
    state, _ = _tree_state(tmp_path)
    opened = _handle_key(state, ord("e"), CONTENT_HEIGHT)
    expanded = _handle_key(opened, ord("l"), CONTENT_HEIGHT)
    down = _handle_key(expanded, ord("j"), CONTENT_HEIGHT)  # cursor -> hydrogen.rsn

    selected = _handle_key(down, ord("\n"), CONTENT_HEIGHT)

    assert selected.show_file_tree is False
    assert selected.pending_open == (tmp_path / "models" / "hydrogen.rsn").resolve()
    assert selected.document is state.document  # not applied yet — that's _apply_pending_open's job


def test_tree_esc_closes_without_selecting_anything(tmp_path):
    state, _ = _tree_state(tmp_path)
    opened = _handle_key(state, ord("e"), CONTENT_HEIGHT)

    closed = _handle_key(opened, 27, CONTENT_HEIGHT)  # Esc

    assert closed.show_file_tree is False
    assert closed.pending_open is None
    assert closed.document is state.document


def test_apply_pending_open_switches_the_document_and_resets_cursor_state(tmp_path):
    state, _ = _tree_state(tmp_path)
    target = (tmp_path / "models" / "hydrogen.rsn").resolve()
    pending = ViewerState(
        document=state.document, tree_root=state.tree_root, tree=state.tree,
        pending_open=target, cursor_line=7, source_scroll=3, active_stage=Stage.IR,
    )

    applied = _apply_pending_open(pending)

    assert applied.pending_open is None
    assert applied.document.source_path == str(target)
    assert applied.cursor_line == 1
    assert applied.source_scroll == 0
    assert applied.active_stage == Stage.IR  # view mode carries over across files


def test_apply_pending_open_is_a_no_op_when_nothing_is_pending(tmp_path):
    state, _ = _tree_state(tmp_path)
    assert _apply_pending_open(state) is state


def test_apply_pending_open_reports_status_message_on_read_failure(tmp_path):
    state, _ = _tree_state(tmp_path)
    missing = ViewerState(document=state.document, pending_open=tmp_path / "does_not_exist.rsn")

    result = _apply_pending_open(missing)

    assert result.pending_open is None
    assert result.status_message is not None
    assert "could not open" in result.status_message
    assert result.document is state.document  # unchanged on failure


def test_reveal_path_expands_ancestors_and_locates_the_row(tmp_path):
    _, tree = _tree_state(tmp_path)
    target = (tmp_path / "models" / "hydrogen.rsn").resolve()

    expanded, cursor = _reveal_path(tree, frozenset(), target)

    assert (tmp_path / "models").resolve() in expanded
    rows = flatten_file_tree(tree, expanded)
    assert rows[cursor].path == target


def test_reveal_path_returns_zero_for_a_missing_tree():
    expanded, cursor = _reveal_path(None, frozenset(), Path("/nonexistent.rsn"))
    assert expanded == frozenset()
    assert cursor == 0
