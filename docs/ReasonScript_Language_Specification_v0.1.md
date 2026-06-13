# ReasonScript Language Specification v0.1

Status: VALIDATED

Language version: `reasonscript-language/0.1`

Related interfaces: `reasonscript-ast/0.1`, `reason-ir/0.1`

## 1. Scope

This specification defines the minimum semantic model, execution unit, module
boundary, namespace, and import behavior of ReasonScript v0.1. RuntimeReal,
MemorySpace, DBM, WorldModel, distributed execution, optimization, macros, and
the type system are outside this specification.

Normative terms `MUST`, `MUST NOT`, `SHOULD`, and `MAY` are requirements.

## 2. Core Language Model

The v0.1 core model contains exactly six orthogonal concepts:

```text
Goal
State
Transition
Constraint
Context
Metadata
```

`Module` organizes these concepts but is not an executable domain concept.
`ExecutionPlan` is a compiled execution artifact rather than a seventh source
concept.

### 2.1 Goal

A Goal declares the desired terminal condition of one module execution.

- A module MUST contain exactly one Goal.
- A Goal is required to plan or judge successful completion.
- A Goal does not mutate State and is not itself executed.
- `kind` identifies the goal interpretation and `target` identifies its
  desired result.

### 2.2 State

State is an owned, serializable snapshot of the system at an execution point.

- A module MUST contain exactly one initial State.
- A State consists of identity, domain type, and JSON-compatible data.
- Later states MAY be named by Transition endpoints without separate source
  declarations.
- State changes only through an applied plan step and its StateDelta.

### 2.3 Transition

A Transition declares one possible transformation from a source state identity
to a target state identity.

- A Transition contains identity, source, relation, target, cost, and optional
  guard and effect.
- A Transition is a planning candidate, not the top-level execution unit.
- Transitions are not inherently deterministic. Ambiguity MUST be resolved by
  explicit planner policy or reported as a decision requirement.
- Declaration order is preserved but MUST NOT be the sole ambiguity rule.

### 2.4 Constraint

A Constraint is a side-effect-free predicate or policy evaluated during
planning, step validation, or commit according to execution policy.

- A Constraint MAY reject a candidate or execution.
- A Constraint MUST NOT mutate State, Context, or another Constraint.
- A Constraint that requires a change does so by permitting or rejecting a
  Transition; it never applies the change itself.

### 2.5 Context

Context is external, non-owned information available by reference.

- Context is optional.
- Context MUST be represented as a typed reference with stable identity.
- Context is not State: State is owned execution data, while Context can have
  independent lifetime, authority, and retrieval behavior.
- Resolving a Context reference MUST NOT silently mutate State.

### 2.6 Metadata

Metadata is optional JSON-compatible annotation for documentation, provenance,
compiler tooling, and diagnostics.

- Metadata MUST NOT change planning, constraint evaluation, transition
  selection, or state mutation in Language v0.1.
- Unknown metadata keys MUST be ignored by execution consumers and SHOULD be
  preserved by round trips.
- Any execution-affecting value belongs in Goal, State, Transition,
  Constraint, Context, or explicit policy, not Metadata.

## 3. Execution Model

The fundamental executor input is an immutable `ExecutionPlan`.

```text
Module
  -> Semantic AST
  -> ReasonIR planning request
  -> planner
  -> ExecutionPlan
  -> executor
  -> StateDelta(s) and InferenceResult
```

The three candidates are resolved as follows:

| Candidate | Decision |
|---|---|
| Goal | Rejected: defines success but lacks initial state and operations |
| Transition | Rejected: represents one candidate step, not a complete run |
| ExecutionPlan | Selected: ordered, validated, immutable executable steps |

`ReasonIR` is the complete planning request and carries the six core concepts.
The planner MAY produce an empty plan when the initial State already satisfies
the Goal. The executor MUST validate each selected step against current State
and Constraints before commit. An `ExecutionPlan` MUST NOT be modified after
creation.

## 4. Module Specification

A Module is the mandatory semantic and compilation root.

1. Every successful parse or AST construction MUST produce one `ModuleNode`.
2. A compilation unit contains exactly one Module.
3. A Module MAY be synthesized by a parser; source-level `module` syntax is not
   required in v0.1.
4. Nested Modules are not supported.
5. A source file commonly maps to one Module, but file layout is host-defined.
6. A host assigns each compilation unit one canonical module name.
7. Canonical names match
   `[A-Za-z_][A-Za-z0-9_]*(.[A-Za-z_][A-Za-z0-9_]*)*`.
   Dots are canonical name separators and do not create nested Module nodes.
8. All core declarations are public in v0.1 because no visibility modifier is
   defined. Metadata is not a symbol.
9. A Module and its closed, acyclic import graph form the compilation boundary.
10. Each Module lowers independently to Reason IR; imports are compile-time
    information and are not emitted into Reason IR 0.1.

## 5. Namespace Specification

Each Module owns one flat namespace. The exported symbol names are:

| Concept | Symbol name |
|---|---|
| Goal | reserved name `goal` |
| State | `state_id` |
| Transition | `transition_id` |
| Constraint | `constraint_id` |
| Context | `context_id` |

Names MUST be unique across concept kinds in a Module. The globally unique
identity is `<canonical-module-name>.<symbol-name>`.

Lookup is deterministic:

1. An unqualified reference searches only the current Module.
2. A self-qualified reference searches the current Module.
3. An imported symbol MUST use its full canonical module qualification.
4. Imports do not inject unqualified names.
5. If canonical module names share a prefix, lookup uses the longest matching
   imported module name.
6. A missing or duplicate symbol is a compile-time error.
7. Transition `source` and `target` values are domain state identities, not
   namespace imports, unless a future type system explicitly declares them so.

Thus `User.Active` and `Order.Active` are distinct and `Active` in an importing
Module is unresolved unless declared locally.

## 6. Import Specification

An import declares a compile-time dependency by exact canonical module name.

```text
import User
import tools.weather
```

1. Imports are optional and declaration order is preserved.
2. Duplicate imports are invalid.
3. The referenced Module MUST exist in the compiler's closed module registry.
4. Cyclic imports, including self-imports, are invalid.
5. Wildcard, alias, relative, and selective imports are not supported.
6. Import resolution MUST complete before lowering the importing Module.
7. Imported declarations are read-only and are never copied into the
   importing Module's AST or Reason IR.
8. Failure to resolve a Module or symbol is a compile-time error and MUST NOT
   be deferred to Runtime.

## 7. Required Invariants

A conforming Language v0.1 implementation MUST enforce:

- exactly one Goal and one initial State per Module;
- stable, unique AST node IDs;
- unique namespace symbols across concept kinds;
- JSON-compatible State, effects, and Metadata;
- finite, non-negative transition costs;
- absolute Context URIs;
- immutable ExecutionPlan after planning;
- acyclic, closed import graphs;
- deterministic local and qualified symbol lookup;
- Metadata independence from executable fields.

## 8. Conformance

Reference validation:

```sh
python3 -m unittest discover \
  -s language_spec_validation_tests -p 'test_*.py' -v
```

The reference namespace resolver is
`frontend/language/module_system.py`. Existing AST, compiler, Reason IR, and
Runtime conformance suites remain authoritative for their respective layers.
