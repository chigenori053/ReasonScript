from __future__ import annotations

import os
from pathlib import Path

from toolchain.code_viewer.filetree import (
    ancestor_directories,
    first_file,
    flatten_file_tree,
    scan_project_tree,
)


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def test_scan_finds_rsn_files_and_ignores_other_extensions(tmp_path):
    _touch(tmp_path / "models" / "water.rsn")
    _touch(tmp_path / "models" / "notes.txt")
    _touch(tmp_path / "README.md")

    tree = scan_project_tree(tmp_path)

    names = {child.name for child in tree.children}
    assert names == {"models"}
    models = next(child for child in tree.children if child.name == "models")
    assert {c.name for c in models.children} == {"water.rsn"}


def test_scan_prunes_directories_with_no_rsn_descendants(tmp_path):
    _touch(tmp_path / "docs" / "guide.md")
    _touch(tmp_path / "src" / "main.rsn")

    tree = scan_project_tree(tmp_path)

    assert {child.name for child in tree.children} == {"src"}


def test_scan_returns_none_when_no_rsn_files_exist(tmp_path):
    _touch(tmp_path / "README.md")
    assert scan_project_tree(tmp_path) is None


def test_scan_ignores_hidden_and_denylisted_directories(tmp_path):
    _touch(tmp_path / ".git" / "hooks" / "fake.rsn")
    _touch(tmp_path / ".hidden" / "fake.rsn")
    _touch(tmp_path / "__pycache__" / "fake.rsn")
    _touch(tmp_path / ".venv" / "fake.rsn")
    _touch(tmp_path / "node_modules" / "fake.rsn")
    _touch(tmp_path / "src" / "real.rsn")

    tree = scan_project_tree(tmp_path)

    assert {child.name for child in tree.children} == {"src"}


def test_scan_does_not_follow_symlinks(tmp_path):
    _touch(tmp_path / "src" / "real.rsn")
    target = tmp_path / "outside"
    _touch(target / "linked.rsn")
    os.symlink(target, tmp_path / "src" / "link_to_outside", target_is_directory=True)

    tree = scan_project_tree(tmp_path)

    src = next(child for child in tree.children if child.name == "src")
    assert {c.name for c in src.children} == {"real.rsn"}


def test_scan_sorts_directories_before_files_case_insensitively(tmp_path):
    _touch(tmp_path / "zzz.rsn")
    _touch(tmp_path / "aaa.rsn")
    _touch(tmp_path / "Middle" / "nested.rsn")

    tree = scan_project_tree(tmp_path)

    assert [child.name for child in tree.children] == ["Middle", "aaa.rsn", "zzz.rsn"]


def test_flatten_returns_empty_tuple_for_none_root():
    assert flatten_file_tree(None, frozenset()) == ()


def test_flatten_excludes_the_root_itself_and_starts_at_its_children(tmp_path):
    _touch(tmp_path / "models" / "water.rsn")
    tree = scan_project_tree(tmp_path)

    rows = flatten_file_tree(tree, frozenset())

    assert [row.path for row in rows] == [tmp_path.resolve() / "models"]


def test_flatten_only_descends_into_expanded_directories(tmp_path):
    _touch(tmp_path / "models" / "water.rsn")
    _touch(tmp_path / "models" / "hydrogen.rsn")
    tree = scan_project_tree(tmp_path)
    models_path = tmp_path.resolve() / "models"

    collapsed = flatten_file_tree(tree, frozenset())
    assert len(collapsed) == 1
    assert collapsed[0].is_directory is True
    assert collapsed[0].expanded is False

    expanded = flatten_file_tree(tree, frozenset({models_path}))
    assert [row.name for row in expanded] == ["models", "hydrogen.rsn", "water.rsn"]
    assert expanded[0].expanded is True
    assert expanded[1].depth == 1


def test_ancestor_directories_covers_the_path_to_a_nested_file(tmp_path):
    _touch(tmp_path / "a" / "b" / "c.rsn")
    tree = scan_project_tree(tmp_path)
    root = tmp_path.resolve()

    ancestors = ancestor_directories(tree, root / "a" / "b" / "c.rsn")

    assert ancestors == {root, root / "a", root / "a" / "b"}


def test_ancestor_directories_is_empty_when_target_is_not_in_the_tree(tmp_path):
    _touch(tmp_path / "a" / "real.rsn")
    tree = scan_project_tree(tmp_path)

    assert ancestor_directories(tree, tmp_path / "does" / "not" / "exist.rsn") == frozenset()


def test_first_file_prefers_a_file_at_the_current_level_over_descending(tmp_path):
    _touch(tmp_path / "nested" / "deep.rsn")
    _touch(tmp_path / "shallow.rsn")
    tree = scan_project_tree(tmp_path)

    found = first_file(tree)

    assert found is not None
    assert found.name == "shallow.rsn"


def test_first_file_descends_when_nothing_is_at_the_current_level(tmp_path):
    _touch(tmp_path / "nested" / "deep.rsn")
    tree = scan_project_tree(tmp_path)

    found = first_file(tree)

    assert found is not None
    assert found.name == "deep.rsn"


def test_first_file_returns_none_for_an_empty_tree(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    from toolchain.code_viewer.filetree import FileTreeNode

    empty = FileTreeNode(path=tmp_path, name=tmp_path.name, is_directory=True, children=())
    assert first_file(empty) is None
