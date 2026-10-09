# Unknown Reasoning Structural Model Foundation v0.1

UNKNOWN information has its own identity and refers to existing reasoning
information. It does not replace or change RU/RUS/RUO Structural Model v0.1.

| Form | Name | Purpose |
| --- | --- | --- |
| URU | Unknown Reason Unit | One unknown information unit, with origins and an append-only journal |
| URUS | Unknown Reason Unit Structure | Multiple URU and non-spatial dependency/causal relations |
| URUO | Unknown Reason Unit Object | Explicit known/unknown placements in a 3D coordinate system |

The machine contract is [unknown_reasoning_structure.schema.json](../schemas/unknown_reasoning_structure.schema.json),
profile `reasonscript-unknown-structure/0.1`. Native types are exported by the
`unknown_structure` module. The ordinary ReasonScript module is
[UnknownStructure](../standard_library/rcp/unknown_structure.rsn).

## URU and information records

`UnknownReasonUnit` reuses `UnknownUnit`: `id`, RU/RUS/RUO `origins`, `cause`,
`grounds`, `dependencies`, and `history`. Its six states and immutable journal
follow the [RCP UNKNOWN lifecycle](rcp.md#unknown-lifecycle). URU IDs must differ
from all original reasoning record IDs. Prefixes such as `uru:*` are conventional;
typed references determine identity roles.

The authoritative URU body remains in RCP `payload.unknowns` and in the existing
`UnknownRegistry`. There is no second registry or second copy of its lifecycle.
A typed `URU` reference resolves directly to that UNKNOWN body, even when no
information record is present.

An optional `URU` record describes the **same** identity with `UnknownInformation`:

- `id`: the existing URU/UnknownUnit ID.
- `known_information`, `missing_information`: domain JSON values, with no
  semantic policy imposed by Rust.
- `evidence_refs`, `knowledge_refs`: typed Evidence/Knowledge record identities.
- `causal_refs`: typed `Relation` or `UnknownRelation` references.

This same-ID pairing is allowed only between one URU information record and its
UNKNOWN body. An orphan description, duplicate description, or collision with
another record kind is rejected. The descriptor adds information without
replicating state/history; callers retain it with their payload/domain records.
URU origins and journal evidence always accompany the payload as well.

The source helper's information fields are strings for convenience. Domains can
serialize their own typed JSON bodies with the same wire fields. Use the existing
`RCPTransition::Advance` and a domain `ValidationDecision` to change the URU state.

## URUS relations and dependencies

`UnknownReasonUnitStructure` contains `id`, at least two distinct `uru_refs`,
and distinct `relation_refs` of kind `UnknownRelation`. Members are existing
Registry units. Each member's dependencies must also be members: a URUS is a
closed dependency graph. Relations use an independent ID and typed `source` /
`target` references. The source must be a URU.

| Relation kind | Target | Meaning |
| --- | --- | --- |
| `DEPENDS_ON` | URU | Declared dependency; must match the source URU's `dependencies` |
| `CAUSED_BY` | URU | Domain-declared cause of the unknown information |
| `BLOCKS` | URU, RU, RUS or RUO | Unknown information obstructs another reasoning unit |
| `RELATED_TO` | URU | Domain-declared association |
| `CONFLICTS_WITH` | URU | Domain-declared evidence/candidate conflict |

URU endpoints must belong to the URUS. A `BLOCKS` endpoint in the original
reasoning model resolves through the payload manifest. No spatial coordinates
are stored in URUS.

`UnknownUnit.dependencies` is the single authority for execution dependency.
Relations can describe those edges, but cannot introduce contradictory
`DEPENDS_ON` edges. Other relations preserve domain claims; they do not silently
add execution dependencies or establish that a claim is true. Declare any
scheduling dependency explicitly in the URU body.

The Rust structure API takes the existing `UnknownRegistry`:

- `reevaluation_order`: iterative topological order, with lexicographic stable-ID
  tie-breaking. Rejects missing/duplicate members, missing dependency closure,
  duplicate dependencies and cycles.
- `unresolved`: members in that order whose current state is not `RESOLVED`.
  `BLOCKED` is included as unresolved; inclusion is not permission to resume it.
- `impact`: all transitive dependents of a changed member, excluding that member,
  in reevaluation order. Direct and indirect affected resolved units are included.
- `resolved_impact`: the affected subset currently `RESOLVED`.

These methods inspect graph structure; they do not choose candidates or reopen
units. The domain chooses what to reevaluate. To invalidate a resolved dependency,
reopen resolved dependents in reverse dependency order first, as required by
`UnknownRegistry::commit`.

The same source helpers return `ReevaluationResult { valid, order }`; invalid
input returns `valid = false` and an empty order. Inspect `valid` before treating
an empty result as an empty unresolved/impact set. Source construction/classification
and reevaluation decisions remain ReasonScript/Domain DSN responsibilities.

## Minimal URUO

`UnknownReasonUnitObject` contains `id`, `space` (`physical` or `abstract`),
nonempty `coordinate_frame` and `coordinate_unit`, nullable three-axis
`coordinate_bounds`, distinct `uru_refs`, `urus_refs`, `ruo_refs`, `placements`,
and `constraints`.

Every contained URU and URUS has exactly one explicit placement:

```json
{"target":{"kind":"URU","id":"uru:measurement"},"status":"unknown","position":null}
```

`status = known` requires three finite numbers. `status = unknown` requires
`position = null`, rather than a placeholder origin or invented coordinate.
Each optional bounds pair is finite and ordered; known positions must be inside
all supplied bounds. Every URU in a contained URUS must be contained and placed
in the URUO. Linked original RUO records must share its space, coordinate frame
and unit; automatic coordinate transformation is outside Foundation.

Constraints have typed member `source` / `target`, kind `ADJACENT`, `CONTAINS`,
or `DISTANCE`, and nullable `distance`. A supplied distance is finite and
nonnegative; non-distance constraints use null. A null distance preserves an
unknown spatial constraint value. Structural validation checks these shapes and
references, without proving adjacency, containment or a measured distance.

URUO does not implement coordinate inference, GeometryRuntime integration or
3D visualization. URUO and URUS IDs remain separate from original RUO/RUS IDs.

## Construct and exchange

Include `standard_library/rcp/*.rsn` in your package's `src/` source graph. Import
`UnknownStructure` alongside the existing RCP modules. The runnable example
links to those shared files and exercises all five relations and both placement
states:

```sh
./reason workspace examples/unknown_structure --json
(cd examples/unknown_structure && ../../reason check --json && ../../reason build)
./reason run examples/unknown_structure/foundation.rsn --entry SerializedUnknownStructure --json --trace=off
```

Use `CreateURU`, `Describe`, `Structure`, `Relation`, `KnownPosition`,
`UnknownPosition`, and `Object3D` for construction. `InformationRecord`,
`RelationRecord`, `StructureRecord`, and `ObjectRecord` construct transport
records and their manifests. Supply the underlying URU bodies in
`RCPMessage::Payload.unknowns`, then use `RCPMessage::Build` / `Encode` as usual.

RCP 0.2 retains its envelope, `records` / `unknowns` payload, and existing state
semantics. This extension adds `URU`, `URUS`, `URUO`, `UnknownRelation` reference
kinds and typed bodies; existing valid 0.2 messages remain valid. Receivers built
before this extension reject the new kinds and must be upgraded to receive
UNKNOWN structures. RCP Router/Dispatcher, byte/count limits, duplicate and
causal-route checks are reused unchanged. RCP 0.1 remains rejected.

## Validation

```sh
cargo test --manifest-path ReasonRuntime/Cargo.toml -p reasonscript-native-reasonunit-runtime
python3 -m pytest tests/rcp
./reason ci --json
```

URS-T01–T10 cover identity/origins, six-state transitions and immutable history,
URUS relations and reference/cycle rejection, deterministic order and impact,
known/unknown coordinates, source constructors and lossless native routing.
Existing RCP P1, runtime and Golden checks remain regression gates. Resolver
Cores, external research, real network DSNs and spatial reasoning are subsequent
work.
