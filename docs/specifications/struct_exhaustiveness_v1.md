# ReasonScript Struct Exhaustiveness Specification v1.0

Specification ID: `struct-exhaustiveness/1.0`

MSI-006A adds deterministic exhaustiveness analysis for struct matches. Struct value spaces are not enumerated. A struct match is complete when a `default` arm exists, a binding-only struct pattern exists, an empty struct pattern exists, or a nested struct pattern recursively contains only exhaustive field patterns.

Incomplete struct matches fail validation before Function IR generation with:

`TV-8 NonExhaustiveStructMatch`

Function IR records deterministic coverage metadata on `MatchExpressionIRNode.coverage`:

```json
{
  "struct_name": "Point",
  "binding_pattern_present": true,
  "empty_pattern_present": false,
  "default_present": false,
  "coverage": "complete"
}
```
