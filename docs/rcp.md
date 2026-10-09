# RCP Foundation — P1 UNKNOWN lifecycle

RCP exchanges complete RU, RUS and RUO records between registered reasoning
Cores. Foundation v0.1 provides deterministic, bounded, in-process Domain DSN
delivery. It does not open network connections. Construct and evaluate reasoning
information in ReasonScript; Rust handles JSON codecs, reference validation,
registries and dispatch. No new language syntax is required.

## Construct and send

Run the executable source example:

```sh
./reason workspace examples/rcp --json
(cd examples/rcp && ../../reason check --json && ../../reason build)
./reason run examples/rcp/foundation.rsn --entry SerializedRequest --json --trace=off
cargo build --release --manifest-path ReasonRuntime/Cargo.toml -p reasonscript-native-reasonunit-runtime
```

`SerializedRequest` contains a wire message built with ordinary `.rsn` structs
and the common `RCPMessage::Encode` builder. `FoundationChecks` exercises UNKNOWN
policy; `SerializedReevaluation` contains an append-only retry, rejection,
resolution, reopening and limit journal. Copy the
request into the `messages` array of a session, then pipe that session's JSON
to `ReasonRuntime/target/release/reasonunit-runtime-native rcp`, or save it as
`SESSION.json` and run `./reason rcp run SESSION.json --json`:

```json
{
  "cores": {"dsn:a": "core:a", "dsn:b": "core:b"},
  "limits": {"messages": 8, "requests": 8, "hops": 8, "bytes": 100000},
  "messages": []
}
```

Each Domain DSN and Core ID must be a unique, nonempty namespaced identity.
The native session adapter accepts at most 1 MiB. Output contains per-domain
`deliveries`; invalid sessions exit with status 1 and an `RCP-001` diagnostic.
A session owns all state for its lifetime; state does not persist across runs.

## Message and payload

The current wire contract is [rcp_message.schema.json](../schemas/rcp_message.schema.json).
Messages require schema `reasonscript-rcp-message/0.2`, protocol version `0.2`,
message ID, source/destination Domain DSNs, kind, correlation ID, nullable
causation ID, trace and payload. Kinds are `REQUEST`, `RESULT`, `UNKNOWN_REPORT`.
The payload contains `records` and `unknowns`. Each record holds a typed stable
reference (`RU`, `RUS`, `RUO`, `Relation`, `Evidence`, `Knowledge`,
`ExecutionState`, `ExecutionBinding`, `ExecutionRelation`, `NativeObject`,
`URU`, `URUS`, `URUO`, `UnknownRelation`), the complete
JSON object in `value`, and an explicit reference manifest. `value.id` must
match the record identity. Unknown transport fields and unsupported enum or
version values are rejected. Structural `value` bodies follow the
[RU/RUS/RUO model](reasoning-structure.md); domain-specific information is
preserved in `content`. Protocol 0.1 and its state/container encodings are rejected.

All reference targets must accompany the payload and match their declared kind.
`URU` references resolve to the authoritative `unknowns` bodies; optional same-ID
information records add known/missing data without copying history. `URUS` and
`URUO` records follow the [UNKNOWN structural model](unknown-reasoning-structure.md).
The additional kinds preserve valid earlier 0.2 messages; older receivers must
declare `reasonscript-unknown-structure/0.1` before accepting UNKNOWN structures.
Runtime embedded references must also appear in the manifest. KnowledgeSpace
information can be supplied as `Knowledge` records with its original contents;
Foundation does not define a new knowledge store or fetch external references.
Rust `RCPPayload::from_runtime_trace` accepts only the versioned
[structural trace schema](../schemas/reason_structure_trace.schema.json).
`context.reason_units = rus_with_state` produces structural RU/RUS plus
separate execution states, bindings and evidence relations. Record bodies
are transferred unchanged; old trace fields and runtime kinds are rejected.
`ReasonStructure::structural_payload()` exposes the same projection.
`from_native_object` and
`native_object` preserve and restore `NativeObject` logical containers; runtime handles
are never sent. JSON object keys are sorted on encoding and array order is
preserved. Domain extension values remain in their original bodies. The adapter transfers
semantic records; the runtime trace container and its summary hashes remain local.
State revisions never become RUS and containers never become 3D RUO implicitly.

## ReasonScript common API

The ordinary modules in [standard_library/rcp](../standard_library/rcp/) are:

| Module | API |
| --- | --- |
| `RCPReference` (`reference.rsn`) | Typed `Reference` |
| `RCPUnknown` (`unknown.rsn`) | `UnknownUnit`, `UnknownRevision`, `CreateUnknown`, `CurrentState` |
| `RCPTransition` (`transition.rsn`) | `CanTransition`, `Advance`, `BlockIfLimit` |
| `RCPValidator` (`validator.rsn`) | `ValidationDecision`, `Decision` |
| `RCPMessage` (`message.rsn`) | `Record`, `Payload`, `Message`, `Build`, `Request`, `Encode` |

Include these source files in your package's `src/` graph, then import their
modules. The repository example links to the same library sources in `src/`.
Use qualified calls such as `RCPUnknown::CreateUnknown` and
`RCPMessage::Request`. `Record.value_json` holds canonical JSON serialized from
your domain's record type; the common API accepts RU, RUS, RUO and other record
bodies without redefining the structural model. `Encode` emits the RCP 0.2 wire
fields, including `value`, rather than the source helper field `value_json`.
Rust rejects malformed raw bodies or references at the protocol boundary.

## UNKNOWN lifecycle

UNKNOWN has an independent ID, immutable RU/RUS/RUO origins, cause, grounds,
dependency IDs and an append-only history. Causes are `MissingKnowledge`,
`MissingEvidence`, `Ambiguous`, `Conflict`, `Dependency`. Allowed edges are:

| Current | Next | Use |
| --- | --- | --- |
| `OPEN` | `IN_PROGRESS` | Start evaluation |
| `IN_PROGRESS` | `CANDIDATE` | Propose a candidate |
| `CANDIDATE` | `RESOLVED` | Accept the same candidate |
| `IN_PROGRESS` | `OPEN` | Retry |
| `CANDIDATE` | `OPEN` | Reject and reevaluate |
| `RESOLVED` | `REOPENED` | Invalidate evidence or request reevaluation |
| `REOPENED` | `OPEN` | Start another evaluation cycle |
| `OPEN`, `IN_PROGRESS` | `BLOCKED` | Execution limit reached |

`BLOCKED` is terminal for this Foundation API and never counts as resolved.
Direct `RESOLVED -> OPEN`, state skips and resumes from `BLOCKED` are rejected.
Each candidate/resolution revision needs a candidate value and nonempty Evidence
references. Resolution must retain the immediately preceding candidate; later
cycles may propose different candidates. Other revisions have a null candidate.
Old candidates, evidence and resolutions remain in earlier revisions, even when
evidence is no longer semantically valid. Historical evidence records must still
accompany the payload so their identities remain traceable. There is no four-
revision limit; the message/session byte limits bound transport size.

The Domain DSN decides semantic classification, candidate acceptance and evidence
validity. Pass its `ValidationDecision` to `RCPTransition::Advance`; rejected
candidates and illegal transitions return the unchanged unit. The example's
`Evaluate` function accepts only `"answer"` with evidence and is not library policy.
`BlockIfLimit` checks a caller-supplied nonnegative execution budget; it appends
`BLOCKED` only when reached and only from an allowed state. Router communication
limits remain independently enforced by Rust.

Rust `UnknownRegistry::commit` accepts one source-produced appended revision,
validates references and structural transition edges, and preserves identity,
origins, metadata and all earlier history. A supplied domain `CandidateValidator`
is called at candidate and resolution boundaries; there is no Rust default
semantic policy. Every rejected commit leaves the registry unchanged. Dependencies
must already be registered, and resolution requires resolved dependencies.
Reopen resolved dependents before reopening their dependency; this prevents
retaining a resolved unit whose dependency is no longer resolved. Rust does not
automatically choose or cascade domain reevaluation. Payload validation rejects
missing and cyclic UNKNOWN dependencies.

## Structural and runtime compatibility

Structural Model v0.1 remains fixed: RU is atomic, RUS is non-spatial, RUO has
explicit 3D placement. Structural schemas and typed definitions are unchanged.
The protocol remains RCP 0.2; existing forward-only UNKNOWN histories remain valid,
with `REOPENED` and `BLOCKED` added to its state vocabulary.

Removed runtime fields (`reason_unit_states`, `reason_unit_objects`), modes
(`ru_rus`, `ru_rus_ruo`), old runtime record kinds and RCP message protocol 0.1
remain rejected. Their remaining occurrences are migration documentation and
negative tests. Historical lightweight-state diagnostic codes `RUS-*` identify
a separate execution-state subsystem; they do not encode structural RUS.
MIRP, `NativeObject` and `.ruo` persistence are outside this revision. The native
session envelope's independent `reasonscript-rcp-session/0.1` label does not enable
RCP message protocol 0.1.

## Routing and causality

`RCPRouter` registers Domain DSN/Core pairs. `RCPDispatcher` validates messages,
resolves both endpoints and appends each delivery to the destination inbox.
Register a base receiver with `register`, or use `register_with_profiles` with a
set containing `UNKNOWN_STRUCTURE_PROFILE`. The session's optional `profiles`
map declares supported profiles by destination DSN, for example:
`"profiles": {"dsn:b": ["reasonscript-unknown-structure/0.1"]}`.
Omission means base RCP 0.2 only. Unsupported profile names and declarations
for unregistered domains are rejected. A receiver must actually implement every
profile it declares; this local declaration is not a remote capability handshake.

`RCPPayload::required_profiles` derives requirements from record kinds and typed
references, including UNKNOWN grounds and historical evidence. Bare existing
`unknowns` with base references need no new profile. Senders can call
`RCPRouter::check_profiles(destination, payload)` before encoding/sending;
dispatch repeats this check before mutating counters or inboxes. A new structure
sent to an undeclared receiver is rejected, even if its protocol version is 0.2.
Wire envelopes remain unchanged, so previous valid base messages still work.

Message IDs are unique throughout a dispatcher lifetime. Message count, REQUEST
count, trace hops and encoded byte limits are mandatory and enforced before
mutation. A rejected message consumes no limit and produces no delivery.

Root requests carry an empty trace. A forwarded request carries the received
trace, the parent message ID as causation and the same correlation ID. Repeated
domains are rejected. A RESULT replies directly to its causal REQUEST's sender;
this return is permitted with the request's received trace. Received
messages are delivery receipts, with the destination appended to the trace;
construct a new wire envelope to forward or reply. A forged/unknown cause, an
unregistered trace domain, a mismatched correlation or a RESULT answering a
non-REQUEST is rejected.

MIRP continues to provide existing reasoning projections and fragment transport.
RCP owns reasoning message envelopes, UNKNOWN tracking and Core delivery; it does
not reinterpret MIRP projections. Autonomous UNKNOWN resolution, Web research,
network transports and complex orchestration are outside Foundation v0.1.

## Validate

```sh
cargo test --manifest-path ReasonRuntime/Cargo.toml -p reasonscript-native-reasonunit-runtime
python3 -m pytest tests/rcp
./reason ci --json
```

RCP-T01 through T09 cover codecs, semantic/reference preservation, UNKNOWN
identity/lifecycle, REQUEST/RESULT delivery, duplicate/cycle/limit rejection,
determinism, malformed input and Domain DSN routing. Integration tests execute
`.rsn` construction and policy in the Rust runtime and deliver its output through
the native dispatcher.

P1-T01–T10 additionally cover retry, candidate rejection, evidence invalidation,
BLOCKED, immutable origins/history, domain-validator rejection, shared `.rsn`
imports/builders, lossless reevaluation transport and determinism. Real networked
Domain DSNs and Resolver Cores are not provided by the in-process test adapter.
