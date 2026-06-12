#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dto" / "python"))

from reasonscript_dto import ReasonIR


def main() -> int:
    source = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(ReasonIR.from_dict(source).to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
