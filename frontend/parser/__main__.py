from __future__ import annotations

import argparse
import json
from pathlib import Path

from frontend.ast import to_json_value

from .errors import ParserError
from .parser import parse


def main() -> int:
    argument_parser = argparse.ArgumentParser(
        description="Parse ReasonScript Phase 2 source into reasonscript-ast/0.1"
    )
    argument_parser.add_argument("source")
    args = argument_parser.parse_args()
    try:
        module = parse(Path(args.source).read_text(encoding="utf-8"))
    except ParserError as error:
        print(json.dumps({
            "code": error.code.value,
            "line": error.line,
            "column": error.column,
            "message": error.message,
            "severity": error.severity.value,
        }))
        return 1
    print(json.dumps(to_json_value(module), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
