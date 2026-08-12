# Phase 19: Generic ReasonScript Graph Query Run v0.1

Phase 19 routes an explicit ReasonGraph query source through
`reason run SOURCE.rsn --allow-read`. The route is selected only when the
source contains the Phase 17 `reason_graph`/`query` surface. Other ReasonScript
programs retain their existing execution path. The operation remains
read-only; generic graph mutation and execution semantics are deferred.
