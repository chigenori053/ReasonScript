# ReasonScript v0.5.2.2

ReasonScript 0.5.2.2 corrects RUO native interoperability:

- installed Object and expert RUO commands resolve the native ReasonUnit
  Runtime from the active distribution, independently of the project cwd;
- the Rust RUO-F1 reader hashes canonical raw record-body bytes rather than
  re-serializing parsed JSON;
- Python-written exponent-form numeric records and Vision-derived RUO files
  are covered by cross-runtime tests;
- body tampering remains rejected as `RUO-N1-007`.

Runtime and language compatibility remain `>=0.5.0,<0.6.0`.
