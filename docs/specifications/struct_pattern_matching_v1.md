# ReasonScript Struct Pattern Matching Specification v1.0

Specification ID: `struct-pattern-matching/1.0`

Struct patterns decompose user-defined struct values inside the existing match semantic pipeline. Supported forms are literal fields, field bindings, mixed fields, empty patterns, and nested struct fields.

Canonical match paths are deterministic. Literal fields include the field name, binding fields use `bind<name>`, and nested struct fields join with `|`, for example `Score.match.Point.x0_bindy` and `Score.match.Person.position|Position.x0`.

Selected branch bindings are local to the selected return path. Simulation emits `StructPatternEvaluation` before `BranchSelection`, and knowledge preserves `struct_match_evidence` with the struct name and matched fields.
