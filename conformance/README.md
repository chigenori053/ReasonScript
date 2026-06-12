# Common DTO Conformance

Run the language-independent fixture and binding checks:

```sh
python3 -m unittest discover -s conformance -p 'test_*.py'
```

Run the Rust binding round-trip tests:

```sh
cargo test --manifest-path dto/rust/Cargo.toml
```

The same `fixtures/valid` and `fixtures/invalid` directories are consumed by
all SDK bindings. A binding reaches compliance Level 4 when it supports every
public DTO listed in `docs/Common_DTO_Specification_v0.1.md`.
