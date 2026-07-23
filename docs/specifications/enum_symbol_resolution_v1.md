# ReasonScript Enum Symbol Resolution v1

Specification ID: `enum-symbol-resolution/1.0`

ESR-001 registers enum declarations and variants as semantic symbols and
resolves qualified enum variants such as `Color.Red`.

Implemented behavior:

- `EnumSymbol` and `EnumVariantSymbol` metadata are emitted.
- `Color.Red` and `Color.Blue` resolve as enum variants.
- Function return IR includes `EnumVariantIRNode`.
- Function call evaluation context encodes enum arguments as `{ "enum": "...", "variant": "..." }`.
- Unqualified enum variants such as `Red` are rejected with `ESR-003`.
- Unknown enum types use `ESR-002`; unknown variants use `ESR-001` with `ESR-004` compatibility text.

This is the prerequisite for MSI-002 enum pattern matching.
