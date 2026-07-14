from pathlib import Path

import pytest

from toolchain.install_update.platform import PlatformAdapter, adapter_for


@pytest.mark.parametrize("name", ["macos", "linux", "windows"])
def test_adapter_contract_and_atomic_activation(name: str, tmp_path: Path) -> None:
    adapter = adapter_for(name, "x86_64")
    root = tmp_path / name
    (root / "versions/0.5.1").mkdir(parents=True)
    adapter.prepare_install_root(root)
    adapter.activate_version(root, "0.5.1", "0.5.0")
    current = root / "metadata/current.json"
    assert current.is_file()
    assert adapter.name == name
    assert adapter.launcher_path(root).parent == root / "bin"
    assert adapter.validate_permissions(root)
    (root / "versions/0.5.2").mkdir()
    adapter.activate_version(root, "0.5.2", "0.5.1")
    assert current.read_text(encoding="utf-8").find('"active_version": "0.5.2"') >= 0


def test_adapter_rejects_unknown_platform() -> None:
    with pytest.raises(ValueError):
        adapter_for("plan9", "x86_64")
