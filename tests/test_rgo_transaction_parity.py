from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from toolchain.reason_object_graph.format import write_graph, read_graph
from toolchain.reason_object_graph.model import graph_hash, reference_graph
from toolchain.reason_object_graph.native_graph import transact_native_graph_file

class RgoTransactionParityTests(unittest.TestCase):
    def test_full_proposal_operations_python_and_native(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            graph_path = tmp / "test.rgraph"
            proposal_path = tmp / "proposal.json"

            initial_graph = reference_graph()
            write_graph(initial_graph, graph_path)
            expected_hash = graph_hash(initial_graph)

            proposal = {
                "graph_updates": {"metadata": {"new_key": "new_val", "parity_version": 2}}
            }
            proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

            res = transact_native_graph_file(
                graph_path,
                proposal_path,
                expected_graph_hash=expected_hash,
                transaction_id="ruo:transaction:tx1",
                root=Path(__file__).resolve().parent.parent,
            )

            tx = res["transaction"]
            self.assertTrue(tx["committed"])
            
            final_graph = read_graph(graph_path)
            self.assertEqual(final_graph["metadata"]["new_key"], "new_val")
