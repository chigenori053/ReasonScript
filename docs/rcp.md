# RCP Foundation v0.1

RCP exchanges complete RU, RUS and RUO records between registered reasoning
Cores. Foundation v0.1 provides deterministic, bounded, in-process Domain DSN
delivery. It does not open network connections. Construct and evaluate reasoning
information in ReasonScript; Rust handles JSON codecs, reference validation,
registries and dispatch. No new language syntax is required.

## Construct and send

Run the executable source example:

```sh
./reason workspace examples/rcp --json
./reason check examples/rcp/foundation.rsn --json
./reason run examples/rcp/foundation.rsn --json
cargo build --manifest-path ReasonRuntime/Cargo.toml -p reasonscript-native-reasonunit-runtime
```

`SerializedRequest` contains a wire message built with ordinary `.rsn` structs
and `serialize.json`. `FoundationChecks` exercises UNKNOWN policy. Copy the
request into the `messages` array of a session, then pipe that session's JSON
to `ReasonRuntime/target/debug/reasonunit-runtime-native rcp`, or save it as
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

The wire contract is [rcp_message.schema.json](../schemas/rcp_message.schema.json).
Messages require schema `reasonscript-rcp-message/0.1`, protocol version `0.1`,
message ID, source/destination Domain DSNs, kind, correlation ID, nullable
causation ID, trace and payload. Kinds are `REQUEST`, `RESULT`, `UNKNOWN_REPORT`.
The payload contains `records` and `unknowns`. Each record holds a typed stable
reference (`RU`, `RUS`, `RUO`, `Relation`, `Evidence`, `Knowledge`), the complete
JSON object in `value`, and an explicit reference manifest. `value.id` must
match the record identity. Unknown transport fields and unsupported enum or
version values are rejected. Domain-specific fields inside `value` are preserved.

All reference targets must accompany the payload and match their declared kind.
Runtime embedded references must also appear in the manifest. KnowledgeSpace
information can be supplied as `Knowledge` records with its original contents;
Foundation does not define a new knowledge store or fetch external references.
Rust `RCPPayload::from_runtime_trace` adapts existing ReasonRuntime semantic
traces (`context.reason_units = ru_rus_ruo`). `from_native_object` and
`native_object` preserve and restore native RUO logical objects; runtime handles
are never sent. JSON object keys are sorted on encoding and array order is
preserved. Domain extension values remain in their original bodies. The adapter transfers
semantic records; the runtime trace container and its summary hashes remain local.

## UNKNOWN lifecycle

UNKNOWN has an independent ID, RU/RUS/RUO origins, cause, grounds, dependency
IDs and an append-only history. Causes are `MissingKnowledge`, `MissingEvidence`,
`Ambiguous`, `Conflict`, `Dependency`. State transitions are exactly
`OPEN -> IN_PROGRESS -> CANDIDATE -> RESOLVED`. Each candidate/resolution needs
both a candidate value and evidence. A resolution preserves the candidate.

The `.rsn` example exports construction, candidate evaluation and transition
functions. Rejected transitions return the unchanged unit. Its sample evaluator
accepts nonempty string candidates with evidence; applications supply their own
semantic evaluator. The native `UnknownRegistry::commit` accepts source-produced
revisions, validates references against a supplied payload, preserves the origin
and earlier revisions, and calls a domain `CandidateValidator` at candidate and
resolution boundaries. Failed validation leaves the registry unchanged. Dependencies
must already be registered; resolution requires resolved dependencies. Payload
validation rejects missing and cyclic UNKNOWN dependencies.

## Routing and causality

`RCPRouter` registers Domain DSN/Core pairs. `RCPDispatcher` validates messages,
resolves both endpoints and appends each delivery to the destination inbox.
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
