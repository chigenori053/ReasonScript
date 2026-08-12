"""RGO-F1 persistence tests for the validated ReasonGraph reference model."""

import copy

import pytest

from toolchain.reason_object_graph import (
    ReasonGraphFileError,
    decode_graph,
    encode_graph,
    read_graph,
    reference_graph,
    validate_graph_file,
    write_graph,
)


def test_rgo_f1_roundtrip_is_logical_and_byte_deterministic() -> None:
    graph = reference_graph()
    reordered = copy.deepcopy(graph); reordered["units"].reverse()
    payload = encode_graph(graph)
    assert payload == encode_graph(reordered)
    assert decode_graph(payload) == graph


def test_rgo_f1_rejects_tampering() -> None:
    payload = bytearray(encode_graph(reference_graph()))
    payload[payload.index(b"causes")] = ord("x")
    with pytest.raises(ReasonGraphFileError, match="canonical|digest|hash"):
        decode_graph(bytes(payload))


def test_rgo_f1_atomic_write_and_validation(tmp_path) -> None:
    target = tmp_path / "nested" / "graph.rgraph"
    written = write_graph(reference_graph(), target)
    assert written["bytes"] == target.stat().st_size
    assert read_graph(target) == reference_graph()
    assert validate_graph_file(target)["ok"]
    with pytest.raises(ReasonGraphFileError, match="overwrite"):
        write_graph(reference_graph(), target)


def test_rgo_f1_requires_extension_and_valid_graph(tmp_path) -> None:
    with pytest.raises(ReasonGraphFileError, match="extension"):
        write_graph(reference_graph(), tmp_path / "graph.json")
    invalid = reference_graph(); invalid["relations"][0]["target"]["entity_id"] = "ruo:unit:missing"
    with pytest.raises(ReasonGraphFileError, match="invalid ReasonGraph"):
        encode_graph(invalid)
