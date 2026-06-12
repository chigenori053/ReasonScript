import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dto" / "python"))

from reasonscript_dto import (
    InferenceStatus,
    ReasonIR,
    StateDelta,
    StateSnapshot,
    Trace,
    TraceEvent,
    TransactionRecord,
    TransactionStatus,
    to_dict,
)


class CommonDtoRoundTripTests(unittest.TestCase):
    def test_valid_reason_ir_fixtures_round_trip(self):
        for path in sorted((ROOT / "fixtures" / "valid").glob("*.json")):
            source = json.loads(path.read_text(encoding="utf-8"))
            dto = ReasonIR.from_dict(source)
            restored = ReasonIR.from_dict(
                json.loads(json.dumps(dto.to_dict(), ensure_ascii=False))
            )
            self.assertEqual(restored, dto, path.name)

    def test_invalid_reason_ir_fixtures_are_rejected(self):
        for path in sorted((ROOT / "fixtures" / "invalid").glob("*.json")):
            source = json.loads(path.read_text(encoding="utf-8"))
            with self.assertRaises((KeyError, TypeError, ValueError), msg=path.name):
                ReasonIR.from_dict(source)

    def test_unknown_metadata_is_preserved(self):
        path = ROOT / "fixtures" / "valid" / "tool_integration.json"
        source = json.loads(path.read_text(encoding="utf-8"))
        source.setdefault("metadata", {})["sdk_extension"] = {
            "nested": [1, True, None]
        }
        restored = ReasonIR.from_dict(source).to_dict()
        self.assertEqual(
            restored["metadata"]["sdk_extension"], {"nested": [1, True, None]}
        )

    def test_uint64_timestamps_are_lossless(self):
        before = StateSnapshot("before", "symbolic", {})
        after = StateSnapshot("after", "symbolic", {})
        delta = StateDelta("delta-1", before, after, "t1", 2**64 - 1)
        record = TransactionRecord(
            "tx-1",
            "plan-1",
            "candidate-1",
            "delta-1",
            TransactionStatus.COMMITTED,
            2**64 - 1,
            (),
            None,
        )
        self.assertEqual(delta.timestamp, 18446744073709551615)
        self.assertEqual(record.commit_timestamp, 18446744073709551615)

    def test_all_dtos_use_json_compatible_enum_and_tagged_event_values(self):
        trace = Trace(
            "request-1",
            "reason-ir/0.1",
            None,
            "policy/0.1",
            (
                TraceEvent(
                    "state_delta_applied",
                    {
                        "delta_id": "delta-1",
                        "transition_id": "t1",
                        "transaction_id": None,
                    },
                ),
            ),
        )
        value = to_dict(trace)
        self.assertEqual(value["events"][0]["event_type"], "state_delta_applied")
        self.assertNotIn("payload", value["events"][0])
        self.assertEqual(to_dict(
            TransactionRecord(
                "tx-1",
                "plan-1",
                "candidate-1",
                None,
                TransactionStatus.PREPARED,
                None,
                (),
                None,
            )
        )["status"], "prepared")
        self.assertEqual(InferenceStatus.COMPLETED.value, "completed")


if __name__ == "__main__":
    unittest.main()
