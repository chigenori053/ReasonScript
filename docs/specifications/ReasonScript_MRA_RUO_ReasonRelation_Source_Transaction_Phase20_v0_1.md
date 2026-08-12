# Phase 20: ReasonScript ReasonGraph Metadata Transaction v0.1

`transact graph "proposal.json" "sha256:…" "ruo:transaction:…";` invokes
the Phase 16 native metadata transaction from an explicit ReasonGraph source.
Both `--allow-read` and `--allow-write` are required. Only
`graph_updates.metadata` is accepted; Unit/Relation mutation remains deferred.
