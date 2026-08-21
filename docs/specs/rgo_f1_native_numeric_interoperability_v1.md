# RGO-F1 Native Numeric Interoperability v1.0

Specification ID: `rgo-f1-native-numeric-interoperability/1.0`

RGO-F1 record and graph digests are calculated from the canonical UTF-8 JSON
body bytes emitted by the writer. Native readers must parse those bytes for
semantic validation but must not re-serialize parsed JSON to decide
canonicality or recompute a digest. JSON runtimes may spell an equivalent f64
using a different shortest decimal or exponent format.

Python-writer RGO-F1 files containing finite 16- or 17-digit f64 values,
including exponent notation, must load in the native Rust reader. Invalid JSON,
body-digest tampering, content-seal tampering, and graph-digest tampering remain
integrity failures.
