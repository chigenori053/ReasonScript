import json
from pathlib import Path

from scripts.benchmark_relation_matrix import SCHEMA, benchmark


def test_relation_matrix_benchmark_preserves_result_and_meets_target():
    root = Path(__file__).resolve().parents[1]
    payload = benchmark(root / "benchmarks" / "relation_matrix.rsn", samples=3)
    assert payload["schema"] == SCHEMA
    assert payload["parity"] is True
    assert payload["result"] == {"RelationMatrix": True}
    assert payload["target_met"] is True


def test_committed_relation_matrix_report_records_passing_evidence():
    root = Path(__file__).resolve().parents[1]
    report = json.loads(
        (root / "benchmarks" / "relation_matrix_optimization_benchmark.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["schema"] == SCHEMA
    assert report["parity"] is True
    assert report["target_met"] is True
    assert report["optimized_median_seconds"] <= report["target_seconds"]
