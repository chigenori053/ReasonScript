# ReasonScript Generic Structure Recognition Remediation v1.0

**Status:** IN_PROGRESS
**Specification ID:** `reasonscript-gsr-remediation/1.0`
**Target:** ReasonScript 0.5 maintenance line

## 1. Scope

This remediation defines the required behavior for the three defects reported
during generic structure recognition:

- consistency between standalone and canonical CI Golden validation;
- compact single-line `struct` declarations;
- successful global CLI help discovery.

The dynamic collection and cross-file reuse capability gaps from the report are
outside this bug-fix scope.

## 2. Golden corpus policy

`reason golden` and the Golden phase of `reason ci` shall use the same corpus
validation result.

- An existing corpus directory with zero cases is valid and reports zero
  failures.
- A missing corpus directory is invalid and reports `GT-011`.
- Corpus validation or case failures fail both entry points.
- Project-independent CI shall not unconditionally validate ReasonScript
  repository Phase 8 fixtures. Phase 8 remains available through its dedicated
  validator and regression tests.
- CI shall retain Golden summary and underlying Golden diagnostics in its phase
  metadata when reporting `CI-006`.

## 3. Compact struct declaration

The language surface shall accept compact declarations such as:

```reason
struct Point { x: int y: int }
```

The compact and multiline forms shall produce equivalent
`StructDeclarationNode` values. Field boundaries are top-level `identifier:`
markers. Delimiters nested inside array, tuple, `optional`, `set`, or `map`
types do not start a new field.

Malformed compact declarations shall report `PARSE-001` instead of degrading to
the generic `CLI-000` diagnostic.

## 4. Global help

The following commands shall print global usage and exit successfully:

```text
reason --help
reason -h
reason help
```

Invocation without arguments retains its existing usage-and-failure behavior.
Unknown commands remain failures.

## 5. Compatibility

The remediation is additive for valid source syntax. Existing multiline struct
ASTs, struct literals, Golden schemas, CI phase ordering, unknown-command
behavior, and the dedicated Phase 8 validator remain unchanged.

No Golden baseline may be updated solely to hide a regression.

## 6. Validation

Completion requires focused parser, Golden, CI, and CLI regression tests,
followed by the canonical:

```sh
reason ci --json
```
