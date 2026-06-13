from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compiler import compile_document
from .errors import CompilerError


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compile reasonscript-ast/0.1 JSON to reason-ir/0.1"
    )
    parser.add_argument("ast")
    args = parser.parse_args()
    try:
        source = json.loads(Path(args.ast).read_text(encoding="utf-8"))
        reason_ir = compile_document(source)
    except (CompilerError, OSError, json.JSONDecodeError) as error:
        if isinstance(error, CompilerError):
            payload = {
                "code": error.code.value,
                "node_id": error.node_id,
                "message": error.message,
                "severity": error.severity.value,
            }
        else:
            payload = {
                "code": "compiler.invalid_ast",
                "node_id": None,
                "message": str(error),
                "severity": "error",
            }
        print(json.dumps(payload))
        return 1
    print(json.dumps(reason_ir, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
