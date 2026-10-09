# Reasoning Unit Structural Model v0.1

RU, RUS and RUO classify reasoning information by its structure. RUS and RUO
are different forms built from RU; they are not successive execution states.

| Type | Name | Structure |
| --- | --- | --- |
| RU | Reason Unit | One proposition, condition, state, relation or operation; no spatial arrangement is required. |
| RUS | Reason Unit Structure | Multiple RU connected through non-spatial reasoning relations. |
| RUO | Reason Unit Object | RU and optional RUS with explicit three-dimensional placements and spatial relations. |

“Dimensionless” means that RUS needs no coordinates or geometric dimensions.
It does not mean a dimensionless physical quantity. A graph, hierarchy or
network does not acquire spatial meaning merely because it has a drawn layout.
RUO coordinates may describe either physical space or an abstract reasoning
space. An RU can contain data about a position; that does not give the RU its
own arrangement of member units.

## Types and invariants

The machine contract is [reasoning_structure.schema.json](../schemas/reasoning_structure.schema.json),
profile `reasonscript-reasoning-structure/0.1`. Rust types live in the native
ReasonUnit runtime's `structure` module. IDs are stable, namespaced and unique
within a payload; membership and endpoint references must resolve by kind.

- `ReasonUnit`: `id`, nonempty `kind`, and `content`. Content contains the
  domain's reasoning information, including extension data.
- `ReasonUnitStructure`: `id`, at least two distinct `unit_refs`, and distinct
  `relation_refs`. Members are RU; relations are `non_spatial` and both endpoints
  belong to the structure. Coordinates and placements are not RUS fields.
- `ReasonUnitObject`: `id`, `space` (`physical` or `abstract`), nonempty
  `coordinate_frame` and `coordinate_unit`, distinct `unit_refs`, `structure_refs`,
  `relation_refs`, and `placements`. Every RU and contained RUS has exactly one
  explicit placement. All RU in a contained RUS must also belong to the RUO.
- `Placement3D`: a typed RU/RUS `target`, a three-element finite numeric
  `position`, and nullable `direction`. A supplied direction is a finite,
  nonzero three-component vector; normalization is a domain decision.
- `ReasonRelation`: `id`, `domain`, `kind`, `source_ref`, `target_ref`, and
  domain `content`. Non-spatial kinds are `Dependency`, `Cause`, `Logical`,
  `Hierarchy`, `IsA`, `PartOf`, `Constraint`, `Similar`. Spatial kinds are
  `Position`, `Direction`, `Distance`, `Adjacent`, `Contains`, `Spatial`.
  RUO relation endpoints belong to its placed members and its relation domain
  is `spatial_3d`. A contained RUS retains its own non-spatial relations.

JSON Schema validates field shapes. The native validator additionally checks
identity, membership, manifests, relation domains, contained structures,
complete placement and nonzero directions. Source-level domain rules determine
whether propositions or spatial claims are true; structural validation does
not infer adjacency or accept a distance claim as proven.

RUS can exist without any RUO. To construct an RUO from RUS, provide the
coordinate frame, unit and placements explicitly. No default layout, implied
hierarchy, or automatic 2D-to-3D embedding is applied.

## Build and evaluate in ReasonScript

[reasoning_structure.rsn](../standard_library/reasoning_structure.rsn) exports
ordinary structs, constructors and record serializers. Its sample content is
string-valued; domains can use their own typed content structs with the same
wire fields. `Object3D` requires explicit placements. `SquaredDistance` is a
source-level spatial calculation. `RelationRecord` takes explicit typed
endpoint references, so it also supports relations to placed RUS members.

```sh
./reason check standard_library/reasoning_structure.rsn --json
./reason run standard_library/reasoning_structure.rsn --json
```

`SerializedStructureMessage` contains RU, RUS, a containing abstract RUO and
both relation domains. `StructuralChecks` checks the 3D distance calculation.
The module exports its constructors for inclusion in a compilation unit; it
is not an automatically imported namespace or a new language construct.
Rust handles encoding, integrity validation, storage and delivery.

## Runtime representation and migration

Runtime traces use [reason_structure_trace.schema.json](../schemas/reason_structure_trace.schema.json).
`reason_units` contains canonical RU bodies; `reason_structures` contains RUS
membership and non-spatial relations; `spatial_objects` contains explicitly
constructed RUO. Runtime semantic events do not supply a spatial layout, so their
`spatial_objects` array is empty. Event order alone does not assert causality.

Execution records are separate: `execution_states` contains immutable state
revisions, `execution_bindings` links RU/state/evidence/lifecycle information,
and `execution_relations` links units to evidence. These records never become
RUS or RUO. Structural `relations` explicitly distinguish `non_spatial` from
`spatial_3d` domains.

The old runtime representation is removed. Callers must migrate explicitly:

| Removed interface | Current interface |
| --- | --- |
| `context.reason_units = ru_rus` | `rus` for structures; `rus_with_state` when state snapshots are required |
| `context.reason_units = ru_rus_ruo` | `rus_with_state`; construct 3D RUO separately with explicit layout |
| `reason_unit_states` and `rus:*` state IDs | `execution_states` and `state:*` IDs |
| `reason_unit_objects` and lifecycle fields on RU | `execution_bindings` and `binding:*` IDs |
| Runtime evidence links under `relations` | `execution_relations` and `ExecutionRelation` references |
| State/object sequence metrics and hashes named RUS/RUO | Separate structural and execution metrics/hashes |

`off` remains the default; `ru` emits atomic units, `rus` also emits RUS when
at least two units exist, and `rus_with_state` additionally emits execution
snapshots and bindings. Removed mode strings and trace fields are rejected,
without compatibility aliases. `ReasonStructure::structural_payload()` and
`RCPPayload::from_runtime_trace()` preserve the current record bodies.

The existing canonical `.ruo`, `NativeReasonUnitObject`, `ReasonObject` and
`ruo.*` APIs remain universal information containers. RCP transports these as
`NativeObject`. Converting them or Geometry State 1.0 into structural 3D RUO
requires a domain-supplied layout; coordinates are never invented.

## RCP wire contract and UNKNOWN

Messages require `reasonscript-rcp-message/0.2` and protocol `0.2`.
The [wire schema](../schemas/rcp_message.schema.json) enforces structural bodies
and separate `ExecutionState`, `ExecutionBinding`, `ExecutionRelation` kinds.
Protocol 0.1, its old state/container bodies, and `RuntimeState`, `RuntimeObject`,
`RuntimeRelation` kinds are rejected. Changing an envelope's version does not
migrate its records.

UNKNOWN can originate from any structural RU, RUS or RUO. Execution snapshots
must be associated with their source RU; they are not structural origins.
MIRP, native object storage and frozen compatibility baselines retain their
current meanings. Existing files are not rewritten automatically.
