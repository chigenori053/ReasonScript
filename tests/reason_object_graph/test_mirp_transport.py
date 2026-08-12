"""Phase 12: canonical MIRP-T1 local exchange tests."""

import pytest

from toolchain.reason_object_graph import (
    MIRPTransportError,
    decode_fragment,
    encode_fragment,
    export_graph,
    project_mirp_fragment,
    read_message,
    reference_graph,
)
from toolchain.reason_object_graph_cmd import run


def test_phase12_mirp_message_is_deterministic_and_roundtrips() -> None:
    fragment = project_mirp_fragment(reference_graph())
    payload = encode_fragment(fragment)
    assert payload == encode_fragment(fragment)
    assert decode_fragment(payload) == fragment


def test_phase12_mirp_message_rejects_tampering() -> None:
    payload = bytearray(encode_fragment(project_mirp_fragment(reference_graph())))
    payload[payload.index(b"causes")] = ord("x")
    with pytest.raises(MIRPTransportError, match="canonical|digest|invalid"):
        decode_fragment(bytes(payload))


def test_phase12_atomic_export_and_cli_import(tmp_path, capsys) -> None:
    message, restored = tmp_path / "graph.mirp", tmp_path / "restored.rgraph"
    export_graph(reference_graph(), message)
    assert read_message(message)["graph"] == reference_graph()
    assert run(["import-mirp", str(message), "--output", str(restored), "--json"], tmp_path) == 0
    assert __import__("json").loads(capsys.readouterr().out)["ok"] is True
