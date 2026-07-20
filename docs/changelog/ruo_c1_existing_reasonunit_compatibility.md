# RUO-C1 Existing ReasonUnit Compatibility

Date: 2026-07-20

- Added the in-memory `ReasonUnitObject` compatibility reference model without
  adding a language or Runtime type.
- Added lossless Legacy Adapter wrapping, validation, Runtime projection,
  unwrapping, and semantic comparison operations.
- Added Object transaction atomicity, dependency closure, lifecycle selection,
  stale projection detection, and Tensor index-to-Unit mapping behavior.
- Added deterministic generation and offline validation for the 26 RUO-C1
  canonical artifacts and the T001–T056 validation matrix.
- Added `reason reasonunit-compatibility generate|validate`.
- Preserved existing lexer, parser, compiler, Runtime, Cluster, Tensor,
  diagnostic, Golden, RUO-C0, and external project behavior.
