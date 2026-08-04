ReasonScript Language Layer Specification v0.6 Draft

Specification ID: reasonscript-language-layer/0.6
Status: DRAFT
Target Platform: ReasonScript Platform v0.5+ / v0.6 planning
Scope: Language architecture, layer responsibility boundaries, pipeline contracts
Non-goal: Individual syntax grammar, AST schema details, runtime implementation details

1. Purpose

This specification defines the official Language Layer architecture of ReasonScript.

ReasonScript is not a conventional source-to-execution language. It is a reasoning-state transition language whose pipeline preserves intermediate reasoning structures.

The canonical pipeline is:

Human Surface
  -> Surface AST
  -> Semantic AST
  -> Reason IR
  -> ExecutionPlan
  -> Semantic Simulation
  -> Knowledge Evidence
  -> Developer Projection

The purpose of this specification is to define:

- The responsibility of each language layer
- The boundary between human-facing syntax and reasoning core
- The canonical semantic representation
- The stability level of each layer
- The rules for future language extension
- The role of IDE / Playground projection
2. Layer Overview

ReasonScript consists of 8 language layers.

Layer	Name	Role
L0	Human Surface	Human-written source syntax
L1	Surface AST	Parsed syntactic structure
L2	Semantic AST	Resolved semantic structure
L3	Reason IR	Canonical reasoning representation
L4	ExecutionPlan	Planned reasoning path
L5	Semantic Simulation	Deterministic execution and validation
L6	Knowledge Evidence	Evidence-backed knowledge generation
L7	Developer Projection	Human-readable visualization and explanation

Canonical pipeline:

L0 Human Surface
  ↓ parse
L1 Surface AST
  ↓ semantic lowering
L2 Semantic AST
  ↓ reasoning lowering
L3 Reason IR
  ↓ planning
L4 ExecutionPlan
  ↓ simulation
L5 Semantic Simulation
  ↓ knowledge extraction
L6 Knowledge Evidence
  ↓ projection
L7 Developer Projection
3. Core Principle

ReasonScript separates language surface from reasoning core.

L0-L2: Language Surface
L3-L6: Reasoning Core
L7: Developer Projection
3.1 Language Surface

The Language Surface is responsible for human-authorable syntax and semantic validation.

L0 Human Surface
L1 Surface AST
L2 Semantic AST

This layer may evolve as the language becomes easier to write and understand.

3.2 Reasoning Core

The Reasoning Core is responsible for deterministic reasoning, planning, simulation, and evidence-backed knowledge generation.

L3 Reason IR
L4 ExecutionPlan
L5 Semantic Simulation
L6 Knowledge Evidence

This layer must remain stable, versioned, and machine-verifiable.

3.3 Developer Projection

Developer Projection is responsible for explaining reasoning state to humans.

L7 Developer Projection

This layer is not part of the core execution semantics, but it is part of the official developer experience.

4. L0 — Human Surface
4.1 Definition

L0 Human Surface is the syntax directly written by users.

Examples:

module Example {
  calculation A {
    result = 10
  }

  calculation B {
    result = A * 2
  }
}

Future syntax may use model, world, or system instead of module:

model Example {
  state Start
  state End

  transition Move {
    Start -> End
  }

  goal End
}
4.2 Responsibilities

L0 is responsible for:

- Human-readable source syntax
- Minimal and coherent keyword design
- Source-level declarations
- Source-level expressions
- Source-level statements
- Source-level diagnostics locations
- IDE-friendly authoring structure
4.3 Non-responsibilities

L0 must not be responsible for:

- Dependency graph resolution
- ExecutionPlan generation
- Simulation execution
- Knowledge extraction
- Evidence identity generation
- Runtime determinism guarantees
4.4 Stability

L0 is evolutionary.

Breaking changes are allowed during draft phases if they improve clarity, reduce conceptual overlap, or better align with ReasonScript’s reasoning model.

4.5 Design Rule

L0 syntax must be allowed to change without changing L3 Reason IR semantics.

Human Surface may evolve.
Reason IR must remain canonical.
5. L1 — Surface AST
5.1 Definition

L1 Surface AST is the parsed representation of L0 source.

It preserves syntactic structure without performing full semantic resolution.

5.2 Responsibilities

L1 is responsible for:

- Parse tree / AST generation
- Source order preservation
- Node kind preservation
- Token span / source location tracking
- Basic syntactic validation
- Surface AST schema validation
- Round-trip-compatible structural representation
5.3 Representative Nodes

L1 may include:

ModuleDeclarationNode
FunctionDeclarationNode
CalculationDeclarationNode
StructDeclarationNode
EnumDeclarationNode
StateDeclarationNode
GoalDeclarationNode
TransitionDeclarationNode
ConstraintDeclarationNode
ExpressionNode
StatementNode
PatternNode
RuntimeCallExpressionNode
5.4 Non-responsibilities

L1 must not resolve:

- Type correctness
- Name binding
- Import/export visibility
- Execution reachability
- Calculation dependency ordering
- Branch evidence
- Knowledge identity
5.5 Stability

L1 is schema-versioned but still allowed to evolve with the Human Surface.

Any L1 schema change must be accompanied by:

- Schema version update
- Compatibility tests
- Migration note if applicable
6. L2 — Semantic AST
6.1 Definition

L2 Semantic AST is the semantically resolved form of the Surface AST.

It determines whether the program is meaningful before lowering into Reason IR.

6.2 Responsibilities

L2 is responsible for:

- Name resolution
- Scope resolution
- Symbol table construction
- Type resolution
- Function signature validation
- Return path validation
- Struct and enum validation
- Optional type validation
- Pattern validation
- Match exhaustiveness validation
- Import/export resolution
- Visibility validation
- Runtime call type validation
- Semantic diagnostics generation
6.3 Representative Outputs

L2 may produce:

SemanticModule
SemanticFunction
SemanticCalculation
SemanticState
SemanticTransition
SemanticGoal
SemanticConstraint
SemanticSymbolTable
ResolvedReference
TypeInfo
VisibilityInfo
RuntimeCallInfo
6.4 Non-responsibilities

L2 must not be responsible for:

- Final reasoning graph construction
- ExecutionPlan ordering
- Simulation trace generation
- Knowledge extraction
- Runtime side-effect execution
6.5 Stability

L2 is compatibility-versioned.

L2 may evolve as the language grows, but semantic validation rules must be deterministic and covered by regression tests.

7. L3 — Reason IR
7.1 Definition

L3 Reason IR is the canonical semantic representation of ReasonScript.

ReasonScript program meaning is defined by Reason IR, not by the raw Human Surface syntax.

Reason IR is canonical.
7.2 Responsibilities

Reason IR is responsible for:

- Canonical reasoning graph representation
- State representation
- Transition representation
- Calculation lowering
- Function-call lowering where applicable
- Runtime operation representation
- Dependency graph representation
- Evidence source preservation
- Deterministic serialization
- Cross-language DTO compatibility
7.3 Required Properties

Reason IR must be:

- Deterministic
- Serializable
- Versioned
- Replayable
- Testable
- Stable across Human Surface changes where semantics are unchanged
7.4 Lowering Rule

Multiple Human Surface forms may lower into the same Reason IR.

Example:

module Example { ... }

and future syntax:

model Example { ... }

may both lower into:

ReasonGraph(namespace="Example")

if their semantics are equivalent.

7.5 Non-responsibilities

Reason IR must not be responsible for:

- Human-friendly presentation
- IDE panel layout
- Final execution order selection when multiple valid plans exist
- Runtime execution
- Knowledge materialization
7.6 Stability

L3 has high stability.

Any breaking change to Reason IR requires:

- Version bump
- Migration strategy
- Golden fixture update
- Compatibility report
8. L4 — ExecutionPlan
8.1 Definition

L4 ExecutionPlan is the planned reasoning path generated from Reason IR.

It determines how ReasonScript reaches a target goal or evaluates a reasoning graph.

8.2 Responsibilities

ExecutionPlan is responsible for:

- Goal selection
- Start state selection
- Target state selection
- Dependency ordering
- Topological sorting
- Transition path selection
- Branch planning
- Alternative path representation
- Cycle detection
- Unreachable goal detection
- Execution distance calculation
- Selected branch signature generation
8.3 Required Properties

ExecutionPlan must be:

- Deterministic for identical Reason IR and planner configuration
- Serializable
- Auditable
- Traceable to Reason IR nodes
- Able to represent failure states
8.4 Non-responsibilities

ExecutionPlan must not be responsible for:

- Mutating runtime state
- Executing runtime operations
- Producing final Knowledge
- Formatting human explanation
8.5 Stability

L4 has high stability.

Planner behavior may evolve, but changes must be reflected in:

- Planner version
- Golden tests
- Regression tests
- ExecutionPlan compatibility report
9. L5 — Semantic Simulation
9.1 Definition

L5 Semantic Simulation executes or validates an ExecutionPlan deterministically.

It verifies whether the planned reasoning path actually holds.

9.2 Responsibilities

Semantic Simulation is responsible for:

- Plan execution
- State transition validation
- Runtime operation execution
- Input state resolution
- Output event generation
- Branch selection event generation
- Simulation trace generation
- Deterministic replay support
- Failure reason preservation
9.3 Representative Outputs

L5 may produce:

SimulationResult
SimulationTrace
SimulationStep
RuntimeOperationResult
InputState
OutputEvent
BranchSelectionEvent
FailureReason
9.4 Required Properties

Simulation must be:

- Deterministic
- Replayable
- Traceable
- Non-ambiguous
- Evidence-preserving
9.5 Non-responsibilities

Simulation must not be responsible for:

- Choosing the original plan
- Defining source syntax
- Constructing semantic symbols
- Presenting IDE views
9.6 Stability

L5 has high stability.

Simulation semantics must be versioned and covered by deterministic replay tests.

10. L6 — Knowledge Evidence
10.1 Definition

L6 Knowledge Evidence extracts evidence-backed knowledge from Simulation results.

Knowledge is not merely a computed value. It is a value or relation supported by a traceable reasoning path.

10.2 Responsibilities

Knowledge Evidence is responsible for:

- Knowledge generation
- Evidence preservation
- Evidence path construction
- Branch signature preservation
- Source relation tracking
- Confidence / validity tracking where applicable
- Deterministic knowledge identity
- Duplicate knowledge handling
10.3 Representative Outputs

L6 may produce:

KnowledgeNode
KnowledgeEdge
Evidence
EvidencePath
PathSignature
BranchId
SourceTrace
KnowledgeIdentity
10.4 Knowledge Identity Rule

Knowledge identity should include enough information to distinguish different reasoning paths.

Minimum identity components:

source
relation
target
evidence_path
path_signature

This prevents semantically different branch-derived knowledge from being incorrectly merged.

10.5 Required Properties

Knowledge Evidence must be:

- Deterministic
- Evidence-backed
- Traceable to Simulation
- Traceable to ExecutionPlan
- Traceable to Reason IR
- Serializable
10.6 Non-responsibilities

Knowledge Evidence must not be responsible for:

- Source parsing
- Type checking
- Plan generation
- Runtime operation execution
- IDE visual layout
10.7 Stability

L6 has high stability.

Any change to Knowledge identity or evidence semantics requires:

- Version bump
- Migration note
- Golden fixture update
- Evidence compatibility test
11. L7 — Developer Projection
11.1 Definition

L7 Developer Projection is the human-facing explanation and visualization layer.

It projects L0-L6 machine-readable structures into developer-readable views.

11.2 Responsibilities

Developer Projection is responsible for:

- Human-readable reasoning path display
- Dependency graph visualization
- Simulation trace explanation
- Knowledge evidence explanation
- Runtime IO display
- Diagnostics display
- Beginner / Developer / Researcher view separation
- Cognitive load reduction
11.3 Required Views

The Playground IDE should support at least these projection views:

- Result Summary View
- Reasoning Path View
- Dependency View
- ExecutionPlan View
- Simulation Trace View
- Knowledge Evidence View
- Runtime IO View
- Diagnostics View
11.4 View Levels

Developer Projection should support three levels.

Beginner View
- Did it run?
- What was produced?
- Why was it produced?
- Where did it fail?
Developer View
- AST
- Reason IR
- ExecutionPlan
- Runtime operations
- Diagnostics
Researcher View
- Branch evidence
- Knowledge identity
- Determinism
- Exhaustiveness
- Complexity
- Trace-level audit data
11.5 Non-responsibilities

L7 must not modify:

- Reason IR
- ExecutionPlan
- SimulationResult
- Knowledge identity

L7 is a projection layer only.

11.6 Stability

L7 is evolutionary.

UI and visualization formats may change independently, provided the underlying L0-L6 artifacts remain stable.

12. Layer Boundary Rules
12.1 Surface/Core Boundary

The boundary between L2 and L3 is the most important boundary in ReasonScript.

L0-L2: Human-facing language surface
L3-L6: Machine-verifiable reasoning core

Rule:

No Human Surface syntax decision should leak into Reason IR unless it affects semantics.
12.2 Plan/Simulation Boundary

ExecutionPlan and Simulation must remain separate.

ExecutionPlan = what should happen
Simulation    = what actually happens under the plan

Rule:

ExecutionPlan must not contain Simulation results.
Simulation must not rewrite the original plan.
12.3 Simulation/Knowledge Boundary

Simulation and Knowledge must remain separate.

Simulation = observed execution trace
Knowledge  = evidence-backed conclusion extracted from trace

Rule:

A computed result is not Knowledge until it has evidence.
12.4 Machine/Human Boundary

L0-L6 are machine-readable artifacts.

L7 is human-readable projection.

Rule:

Developer Projection must not become the source of truth.
13. Stability Policy
Layer	Stability	Versioning Requirement
L0 Human Surface	Low to Medium	Draft syntax versions
L1 Surface AST	Medium	AST schema version
L2 Semantic AST	Medium	Semantic validation version
L3 Reason IR	High	Required
L4 ExecutionPlan	High	Required
L5 Semantic Simulation	High	Required
L6 Knowledge Evidence	High	Required
L7 Developer Projection	Low to Medium	UI / Projection version
13.1 Canonical Stability Rule
L3-L6 must be more stable than L0-L2.
13.2 Surface Evolution Rule

L0 may evolve aggressively until Human Surface v1.0.

13.3 Core Compatibility Rule

L3-L6 must preserve compatibility whenever possible.

Breaking changes require explicit versioning and fixture migration.

14. Artifact Contract

Each layer should produce explicit artifacts.

L0: source.rsn
L1: surface_ast.json
L2: semantic_ast.json
L3: reason_ir.json
L4: execution_plan.json
L5: simulation.json
L6: knowledge.json
L7: projection.json / IDE views
14.1 Golden Test Requirement

Official examples should include expected artifacts.

Example:

examples/
  001_empty_model.rsn
  002_single_calculation.rsn
  003_dependency_chain.rsn
  004_function_call.rsn
  005_branch_knowledge.rsn
  006_runtime_input_print.rsn
  007_unreachable_goal.rsn
  008_cycle_error.rsn

expected/
  001_empty_model/
    surface_ast.json
    semantic_ast.json
    reason_ir.json
    execution_plan.json
    simulation.json
    knowledge.json
    diagnostics.json

This makes third-party implementation and compatibility testing possible.

15. Diagnostics Policy

Diagnostics must be assigned to the correct layer.

Diagnostic Type	Layer
Syntax error	L1
Duplicate symbol	L2
Type mismatch	L2
Invalid return path	L2
Invalid runtime call type	L2
Dependency cycle	L4
Unreachable goal	L4
Runtime operation failure	L5
Simulation failure	L5
Knowledge evidence conflict	L6
Visualization issue	L7

Rule:

Diagnostics must not be reported from a lower layer if the error belongs to a higher layer.

Example:

Undefined variable
  -> L2 Semantic AST diagnostic

Unreachable target
  -> L4 ExecutionPlan diagnostic

Missing evidence path
  -> L6 Knowledge Evidence diagnostic
16. Extension Policy

New language features must declare which layers they affect.

For every new feature, the implementation proposal must include:

- L0 syntax impact
- L1 AST impact
- L2 semantic validation impact
- L3 Reason IR impact
- L4 planning impact
- L5 simulation impact
- L6 knowledge impact
- L7 projection impact
16.1 Required Extension Template
Feature Name:
Status:
Affected Layers:
  L0:
  L1:
  L2:
  L3:
  L4:
  L5:
  L6:
  L7:

Canonical Semantics:
Compatibility Risk:
Golden Tests:
Diagnostics:
16.2 Core Rule

A feature that only changes L0 syntax must not require L3-L6 changes unless its semantics change.

17. module / model / world Policy

Current ReasonScript uses module as a top-level namespace construct.

However, module is considered an L0 Human Surface construct.

It must not be treated as the permanent conceptual foundation of ReasonScript.

Future Human Surface may introduce:

model
world
system
component

These may lower into the same L3 Reason IR namespace or reasoning graph structure.

17.1 Normalization Rule

The following Human Surface forms may be semantically equivalent:

module Example {
  calculation A {
    result = 10
  }
}
model Example {
  calculation A {
    result = 10
  }
}

If equivalent, both should lower into the same canonical Reason IR structure.

18. Reason IR Canonical Rule

ReasonScript program meaning is defined by L3 Reason IR.

Source syntax is authoring form.
Reason IR is semantic form.
ExecutionPlan is planned reasoning form.
Simulation is validated execution form.
Knowledge is evidence-backed conclusion form.

This rule allows ReasonScript to evolve its Human Surface without destabilizing the reasoning core.

19. Minimal Compliance

A ReasonScript-compatible implementation must support at least:

L0 source input
L1 Surface AST generation
L2 semantic validation
L3 Reason IR generation
L4 ExecutionPlan generation
L5 deterministic Simulation
L6 Knowledge Evidence generation

L7 is required for the official Playground IDE, but not required for minimal compiler compatibility.

19.1 Minimal Compiler Compatibility

A compiler is minimally compatible if it can produce:

surface_ast.json
semantic_ast.json
reason_ir.json
execution_plan.json
simulation.json
knowledge.json
diagnostics.json

for official golden fixtures.

19.2 Minimal IDE Compatibility

An IDE is minimally compatible if it can display:

- diagnostics
- execution result
- reasoning path
- simulation trace
- knowledge evidence

without exposing raw JSON as the primary interface.

20. Third-Party Implementation Guidance

Third-party implementers should not start from the full Playground IDE.

Recommended implementation order:

1. L0 minimal source subset
2. L1 parser and Surface AST
3. L2 name/type validation
4. L3 Reason IR lowering
5. L4 simple ExecutionPlan
6. L5 deterministic Simulation
7. L6 minimal Knowledge Evidence
8. L7 human-readable projection

The first compatibility target should be:

calculation dependency chain

Example:

module Test {
  calculation A {
    result = 10
  }

  calculation B {
    result = A * 2
  }
}

Expected reasoning path:

A.state.result -> B.state.result

Expected knowledge:

B is derived from A through calculation B
21. Conformance Levels

ReasonScript compatibility may be divided into conformance levels.

Level 0 — Parser Compatible
Supports L0 -> L1
Level 1 — Semantic Compatible
Supports L0 -> L2
Level 2 — Reason IR Compatible
Supports L0 -> L3
Level 3 — Plan Compatible
Supports L0 -> L4
Level 4 — Simulation Compatible
Supports L0 -> L5
Level 5 — Knowledge Compatible
Supports L0 -> L6
Level 6 — IDE Projection Compatible
Supports L0 -> L7

Official ReasonScript Platform should target:

Conformance Level 6

Minimal third-party compiler should target:

Conformance Level 5
22. Current Status

As of this draft, the ReasonScript platform already contains working or partially validated forms of:

- Human Surface
- Surface AST
- Semantic AST
- Reason IR
- ExecutionPlan
- Semantic Simulation
- Knowledge generation
- Playground IDE projection

However, this specification formalizes the layer boundaries and should be used to prevent future architectural drift.

23. Open Issues

The following issues remain open.

LL-001B: model top-level alias and equivalence validation

Status:

  CI-VALIDATED after CI/CD confirmation. Locally validated by the v0.6-B
  compatibility and artifact contract suites.

Summary:

  module and model are source-distinct at L0/L1.
  module and model are semantically equivalent at L3-L6.
  source_kind preserves the original Human Surface spelling.
  diagnostics.json is part of the official artifact contract.

Validation:

  tests/compatibility/test_module_model_equivalence.py
  tests/playground/test_artifact_contract_v0_6.py

LL-001: Human Surface top-level keyword

Current:

module

Candidates:

model
world
system
component

Recommendation:

model

Reason:

- Better matches reasoning model construction
- Easier for third-party developers to understand
- Less tied to conventional programming-language module semantics
LL-002: Class-like structural system

ReasonScript may need a class-equivalent construct for UI, WorldModel, and SDK-oriented development.

This should be handled first as an L0/L2 design issue and should not destabilize L3 Reason IR.

LL-003: Projection schema

L7 Developer Projection should eventually define its own projection schema.

Candidate artifacts:

projection_summary.json
projection_reasoning_path.json
projection_knowledge_view.json
projection_diagnostics.json
LL-004: Human Surface v1.0

Before ReasonScript v1.0, Human Surface must be simplified and fixed.

Target:

- Fewer top-level concepts
- Clear distinction between fn and calculation
- Clear distinction between data structure and reasoning model
- Stable goal syntax
- Stable state / transition syntax
24. Final Definition

ReasonScript Language Layer v0.6 defines the language architecture as:

L0 Human Surface
  Human-written syntax

L1 Surface AST
  Parsed syntactic structure

L2 Semantic AST
  Resolved names, types, scopes, and semantic validity

L3 Reason IR
  Canonical reasoning representation

L4 ExecutionPlan
  Planned reasoning path

L5 Semantic Simulation
  Deterministic execution and validation

L6 Knowledge Evidence
  Evidence-backed knowledge generation

L7 Developer Projection
  Human-readable reasoning explanation

The central design rule is:

L0-L2 may evolve.
L3-L6 must remain stable and versioned.
L7 may evolve independently as a projection layer.

The canonical semantic rule is:

Reason IR is the source of semantic truth.

The knowledge rule is:

A computed result is not Knowledge until it has evidence.

The projection rule is:

Developer Projection must explain the reasoning pipeline without becoming the source of truth.
Recommended filename
docs/specs/reasonscript_language_layer_v0_6.md
Recommended next step

この仕様を採用する場合、次は LL-001: Human Surface top-level keyword を決めるのが妥当です。module を維持するか、model へ移行するかで、以降の構文整理方針が大きく変わります。
