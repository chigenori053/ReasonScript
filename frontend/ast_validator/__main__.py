from __future__ import annotations

import argparse

from . import AstDocumentError, validate_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate reasonscript-ast/0.1 JSON")
    parser.add_argument("document")
    args = parser.parse_args()
    try:
        validate_file(args.document)
    except AstDocumentError as error:
        print(f"invalid: {error}")
        return 1
    print("valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
