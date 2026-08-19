# ReasonScript Documentation

This directory contains the normative specifications and reference
documentation for the ReasonScript language and platform.

## Current Release

- `../release/RELEASE_NOTES_v0_5_4_9.md` — ReasonScript v0.5.4.9 release
  scope, compatibility notes, and package location.
- `changelog/reasonscript_v0_5_4_9.md` — concise v0.5.4.9 changelog.
- `installation/ReasonScript_v0_5_4_9_Installation.md` — official macOS arm64
  package update and validation procedure.
- `specifications/ReasonScript_Transformer_Validation_Remediation_v0_1.md` and
  `specifications/ReasonScript_Agent_Project_Template_v0_1.md` — accepted
  specifications for the v0.5.4.9 corrections and Agent project template.

## Language

- `specifications/ReasonScript_Language_Specification_v0.1.md` — Language
  v0.1 core model and module system.
- `grammar.md` — Surface grammar reference.
- `semantics.md` — Semantics overview.
- `specifications/ReasonScript_Operational_Semantics_v0.1.md` — Operational
  semantics and runtime contract.
- `specifications/ReasonScript_Computation_Model_v0.1.md` — Computation model.
- `specifications/ReasonScript_Calculation_Semantics_v0.1.md` — Calculation
  semantics.

## Language Surface

- `specifications/ReasonScript_Language_Surface_v0.1_Release_Specification.md`
  — Normative Language Surface v0.1 release specification.
- `specifications/ReasonScript_Language_Surface_Core_v0.1_RC.md` — Language
  Surface core release candidate specification.
- `specifications/ReasonScript_Language_Surface_AST_Mapping_v0.1.md`
- `specifications/ReasonScript_Language_Surface_Expression_Pattern_v0.1.md`
- `specifications/ReasonScript_Language_Surface_Statement_v0.1.md`
- `specifications/ReasonScript_Language_Surface_Calculation_Integration_v0.1.md`
- `specifications/ReasonScript_Language_Surface_Namespace_Import_Resolution_v0.1.md`
- `specifications/ReasonScript_Language_Surface_Type_Specification_v0.1.md`

## Semantic Language Core

- `specifications/ReasonScript_Semantic_Language_Core_v0.2.md` — Normative
  Semantic Language v0.2 Core specification (frozen 2026-06-15).
- `specifications/Reasoning_Space_Specification_v0.1-draft.md`
- `specifications/SCV-1_Structural_Constraint_Validation_Specification_v0.1-draft.md`
- `specifications/SSV-1_Semantic_Simulation_Validation_Specification_v0.1-draft.md`
- `specifications/KEV-1_Knowledge_Emergence_Validation_Specification_v0.1-draft.md`

## Platform Contracts

- `specifications/ReasonScript_Platform_v0.1_Alpha_Release_Specification.md`
  — Platform v0.1 Alpha release specification.
- `specifications/ReasonScript_ABI_Specification_v0.1.md` — ABI contract.
- `specifications/Common_DTO_Specification_v0.1.md` — Common DTO contract for
  the Rust, Python, TypeScript, Go, and Java bindings.
- `specifications/Transaction_Protocol_Specification_v0.1.md` — Transaction
  protocol.
- `specifications/Conformance_Framework_Specification_v0.1.md` — Conformance
  framework.
- `specifications/AST_Validation_Specification_v0.1.md`
- `specifications/AST_Schema_Validation_Specification_v0.1.md`
- `specifications/Parser_Validation_Specification_v0.1.md`
- `specifications/Compiler_Validation_Specification_v0.1.md`

## Tooling

- `specifications/LSP_Phase_1_Specification.md` — Language Server Protocol
  integration.
- `specifications/World_SDK_Phase_1_Specification.md` — World Model SDK.

## Feature Specifications

`specs/` contains versioned feature specifications for individual language
features (pattern matching, exhaustiveness, guards, enum resolution, and
others). Additional versioned specifications live in `specifications/`.

- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Integrated_Model_v0_1.md`
  — accepted Phase 1 contract for the graph-native ReasonUnit / ReasonRelation
  data model.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_RUO_U1_Integration_Phase8_v0_1.md`
  — accepted Phase 8 read-only RUO-U1 integration boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_RUO_F1_Integration_Phase9_v0_1.md`
  — accepted Phase 9 read-only RUO-F1 file integration boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Native_Runtime_Handoff_Phase10_v0_1.md`
  — accepted Phase 10 Native Runtime / ReasonGraph read-only handoff.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Query_Phase11_v0_1.md`
  — accepted Phase 11 deterministic ReasonGraph query boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_MIRP_Transport_Phase12_v0_1.md`
  — accepted Phase 12 canonical local MIRP exchange boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Persistence_Transaction_Phase13_v0_1.md`
  — accepted Phase 13 atomic RGO-F1 transaction boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Native_Graph_Loader_Phase14_v0_1.md`
  — accepted Phase 14 immutable Native Runtime RGO-F1 loader boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Native_Graph_Query_Phase15_v0_1.md`
  — accepted Phase 15 Native Runtime read-only query parity boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Native_Graph_Transaction_Phase16_v0_1.md`
  — accepted Phase 16 Native Runtime atomic metadata transaction boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Language_Query_Phase17_v0_1.md`
  — accepted Phase 17 capability-gated ReasonScript graph query boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Surface_Binding_Phase18_v0_1.md`
  — accepted Phase 18 Surface AST and Reason IR graph-binding boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Generic_Run_Phase19_v0_1.md`
  — accepted Phase 19 generic `reason run` graph-query boundary.
- `specifications/ReasonScript_MRA_RUO_ReasonRelation_Source_Transaction_Phase20_v0_1.md`
  — accepted Phase 20 capability-gated source metadata transaction boundary.

## Other Directories

- `guides/` — User-facing guides.
- `installation/` — Install and distribution documentation.
- `development/` — Development environment and workspace contracts.
- `reference/` — Reference material.
- `releases/` — Release notes.
- `changelog/` — Component changelogs.
- `reports/` — Feature validation reports.

## Roadmap

- `roadmap.md` — Development roadmap.
