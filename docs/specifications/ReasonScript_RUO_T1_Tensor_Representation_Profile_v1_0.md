# ReasonScript RUO-T1 Tensor Representation Profile v1.0

Status: IMPLEMENTED

This repository implements the normative RUO-T1 specification supplied for Phase RUO-T1. The canonical implementation is `toolchain.reasonunit_tensor`; the command surface is `reason reasonunit-tensor`; generated evidence is stored under `artifacts/reasonunit_tensor/ruo_t1`.

The implementation adds the `ruo.payload.tensor/1` profile without changing RUO-U1 identity semantics or RUO-F1 record encoding. It defines exact little-endian scalar codecs, canonical dense/COO/CSR and inline forms, stable axis mappings, masks, chunks, logical and physical digests, partial selection, lossless representation conversion, safe resource resolution, and deterministic validation artifacts.

Native Runtime Tensor types, operators, device execution, language syntax, migration, and WorldModel integration remain deferred.
