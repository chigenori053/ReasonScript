from frontend.computation_ir import rust_bridge


def test_release_host_preferred_with_debug_fallback_and_explicit_override(tmp_path, monkeypatch):
    monkeypatch.setattr(rust_bridge, "_CRATE_ROOT", tmp_path / "runtime")
    monkeypatch.setattr(rust_bridge, "_DISTRIBUTION_ROOT", tmp_path / "distribution")
    monkeypatch.delenv("REASONSCRIPT_HOME", raising=False)
    monkeypatch.delenv("REASONSCRIPT_RUNTIME_HOST", raising=False)
    monkeypatch.setattr(rust_bridge.shutil, "which", lambda name: None)
    name = rust_bridge.binary_name()
    release = tmp_path / "runtime/target/release" / name
    debug = tmp_path / "runtime/target/debug" / name
    for host in (release, debug):
        host.parent.mkdir(parents=True)
        host.touch()
    assert rust_bridge.find_binary() == release
    monkeypatch.setenv("REASONSCRIPT_RUNTIME_HOST", str(debug))
    assert rust_bridge.find_binary() == debug
    monkeypatch.delenv("REASONSCRIPT_RUNTIME_HOST")
    release.unlink()
    assert rust_bridge.find_binary() == debug
