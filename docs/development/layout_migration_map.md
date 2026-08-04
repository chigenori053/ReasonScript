# Layout Migration Map

Status: Phase 3.5 DRAFT FOR ADOPTION

| Existing Tab | New Location |
| --- | --- |
| Pipeline | Overview |
| Summary | Overview |
| Diagnostics | Overview summary + Bottom Problems |
| AST | Artifacts |
| Semantic AST | Artifacts |
| Reason IR | Artifacts |
| ExecPlan | Plan |
| Simulation | Simulation |
| Knowledge | Knowledge |
| Validation | Artifacts / Bottom Problems |
| Output | Bottom Output |
| Dep Graph | Artifacts dependency section or Overview summary |
| Runtime | Simulation / Bottom Output |
| Input | Simulation optional section |
| Calculation | Plan optional section |
| Cycle | Plan optional section / Bottom Problems |
| Trace | Simulation |
| Strict | Bottom Problems |
| Ownership | Optional metrics section |
| Types | Optional metrics section |
| Exhaustive | Bottom Problems / Optional metrics section |
| Determinism | Overview optional section |
| Complexity | Optional metrics section |
| Quality | Optional metrics section |
| Artifacts | Artifacts |
| Diff | Bottom Tests or future Audit section |
| Regression | Bottom Tests |
| Baseline | Bottom Tests |
| Audit | Top Bar action + future Audit section |

Existing functionality is preserved through relocation, grouping, or
collapsible detail sections.
