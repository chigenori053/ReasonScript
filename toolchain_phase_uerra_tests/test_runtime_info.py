import json

from toolchain.runtime_cmd import run


def test_runtime_info_exposes_logical_backend_and_engine(capsys):
    assert run(["info", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    backends = {item["backend_id"]: item for item in payload["backends"]}
    assert backends["RuntimeReal"]["execution_engine"] == "rust"
    assert backends["TensorRuntime"]["tensor_support"] is True
