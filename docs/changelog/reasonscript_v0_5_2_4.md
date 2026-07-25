# ReasonScript v0.5.2.4

ReasonScript 0.5.2.4 corrects three defects found during generic structure
recognition:

- standalone and CI Golden validation now share the same corpus result, and a
  missing corpus reports `GT-011`;
- compact single-line struct declarations are accepted, including nested
  composite types, while malformed declarations report `PARSE-001`;
- `reason --help`, `reason -h`, and `reason help` print usage successfully.

Existing multiline struct declarations, dedicated Phase 8 validation,
unknown-command behavior, and runtime compatibility remain unchanged.
