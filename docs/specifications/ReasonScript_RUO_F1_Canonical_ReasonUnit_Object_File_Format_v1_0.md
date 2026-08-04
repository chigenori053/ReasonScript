# ReasonScript RUO-F1 Canonical ReasonUnit Object File Format v1.0

Status: IMPLEMENTED

Date: 2026-07-20

This repository implements the normative RUO-F1 specification supplied for Phase RUO-F1. The `.ruo` format is a canonical UTF-8 JSON Lines record stream over the immutable RUO-U1 logical model. It provides deterministic record ordering, body and section digests, a final content seal, logical Object integrity, external resources, partial selection, unknown extension retention, bounded streaming validation, path safety, and atomic publication.

The reference tooling is available through:

```sh
reason reasonunit-file write INPUT_JSON --output OBJECT.ruo
reason reasonunit-file validate OBJECT.ruo
reason reasonunit-file inspect OBJECT.ruo
reason reasonunit-file read OBJECT.ruo --output OUTPUT_JSON
reason reasonunit-file select OBJECT.ruo --selector SELECTOR_JSON --output PARTIAL.ruo
reason reasonunit-file verify-resources OBJECT.ruo --resource-root ROOT
reason reasonunit-file generate
reason reasonunit-file validate-phase
```

RUO-F1 defines persistence and exchange only. Tensor-native layout, Runtime integration, language syntax, migration, authentication, encryption, networking, and WorldModel integration remain deferred.
