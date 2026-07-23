# ReasonScript Language Surface LS-2 Namespace and Import Resolution v0.1

Status: Draft for Validation

Compatible:

- `reasonscript-language-surface/0.1`
- `reasonscript-ast/0.1`
- `parser/0.1`
- `compiler/0.1`
- `reason-ir/0.1`
- `execution-plan/0.1`

## 1. Scope

LS-2 defines module-scoped namespaces, import and alias resolution, symbol
visibility, qualified names, lookup precedence, and conflict detection.
Package registries, version resolution, remote modules, and dynamic loading
remain outside this phase.

## 2. Namespace and Symbols

Every declaration with a `name` is registered in one module namespace:

```text
finance::LoanApproval
finance::RiskScore
```

Concept, Object, Event, Action, Attribute, Goal, Constraint, Transition, and
Calculation names share the namespace. Duplicate names fail with `NS-001`.

## 3. Visibility

Calculation visibility is declared directly:

```text
calculation InternalRisk { ... }      // Private
pub calculation RiskScore { ... }    // Public
```

Other declaration kinds inherit their module visibility. Only public symbols
are exposed by imports. Importing a private symbol fails with `NS-050`.

## 4. Imports

An import can resolve a module or one symbol:

```text
import finance
import finance.RiskScore
import finance as loan
import finance.RiskScore as risk
```

Resolved `ImportNode` values contain an `ImportResolutionNode` with the
canonical namespace, optional symbol, and exposed unqualified names.

For Language Surface 0.1 compatibility, unresolved multi-segment imports are
preserved as external import metadata. Single-segment missing modules and all
imports that partially match a Program module fail with `NS-020`.

## 5. Lookup

Unqualified lookup order is:

1. Calculation local bindings
2. Current module namespace
3. Imported public symbols

Two imports exposing the same unqualified name fail with `NS-040`. Aliases
must not collide with another alias or local module symbol (`NS-021`).

## 6. Qualified Names

```text
finance::RiskScore
loan::RiskScore
```

The AST form is:

```text
QualifiedIdentifierNode {
    path
    symbol
    resolved_name
}
```

Resolution stores the fully qualified canonical name, for example
`finance::RiskScore`. Missing qualified targets fail with `NS-030`.

## 7. Validation Rules

| Rule | Contract |
|---|---|
| `NS-V001` | Namespace and path identifiers are valid |
| `NS-V002` | Module symbols are unique |
| `NS-V003` | Import target exists |
| `NS-V004` | Alias is unique |
| `NS-V005` | Qualified target exists |
| `NS-V006` | Imported target is public |
| `NS-V007` | Imported unqualified names are unambiguous |

## 8. Compiler Compatibility

Surface AST serialization preserves qualified identifiers and import
resolution metadata. Semantic AST metadata contains the module namespace and
resolved imports. Calculation transition effects preserve canonical qualified
references. Reason IR and ExecutionPlan schemas remain unchanged.

