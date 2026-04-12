# ReasonScript AST Node Specification

## Core AST
Program
 └── Statement*

Statement
 ├── GoalNode
 ├── DeriveNode
 ├── ProveNode
 ├── ApplyNode
 ├── ConvergeNode
 └── RollbackNode

## Node Definitions

GoalNode:
- target: Symbol

DeriveNode:
- strategy: Symbol

ProveNode:
- invariant: Symbol

ApplyNode:
- action: Symbol

ConvergeNode:
- verification: Symbol

RollbackNode:
- fallback: Symbol
