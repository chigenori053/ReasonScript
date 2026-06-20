# ReasoningTrace Proposal

Classification: Missing

ReasoningTrace should become the platform-wide trace envelope. It should not
replace engine-specific traces; it should adapt them into a shared event stream.

## Proposed Shape

```text
ReasoningTrace {
    schema
    trace_id
    source
    events
    evidence
    diagnostics
    metadata
}
```

## Event Sources

- `core`
- `execution_coordinator`
- `runtime`
- `world_simulation`
- `reconstruction`
- `transaction`
- `toolchain`

## Review Answers

- TR-001: Traces can be unified through an envelope and source-specific payloads.
- TR-002: Evidence can be standardized as immutable event attachments with
  source, timestamp/order, subject, and confidence/proof metadata.
- TR-003: ReasoningTrace should become a platform-wide type before Beta.

## Required Beta Work

- Define `reasoning-trace/0.1` schema.
- Add adapters for ExecutionCoordinator, runtime operations, world simulation,
  reconstruction, and transactions.
- Require trace IDs to propagate through Toolchain and IDE structured results.
