# ReasonScript Standard Library

## Data Analysis Foundation v0.1

The `data.*`, `table.*`, and `value.*` contracts are implemented by the
backend-independent `runtime.data.DataBackend` API. See
See the public function overview in `docs/standard-library.md`.

This directory is the stable distribution root for core ReasonScript standard-library resources. Optional numerical, image, and ML backends are intentionally excluded from the core installation contract.

## Reasoning structures

`reasoning_structure.rsn` exports RU, RUS, RUO, typed endpoint/placement records,
constructors and serializers using ordinary ReasonScript. See the
[structural model](../docs/reasoning-structure.md) for invariants and compatibility.

## RCP communication

`rcp/*.rsn` exports message/reference builders, UNKNOWN journals, structural
transition checks and a domain validation-decision interface. Include these
ordinary modules in a package source graph; see the [RCP API](../docs/rcp.md).
