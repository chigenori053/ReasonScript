# ReasonScript 0.5.2.1 Release Notes

ReasonScript 0.5.2.1 is a maintenance release that completes numerical
execution for scalar calculations, arrays, user functions, structs, and
multi-frame results.

The install package now contains both native executables:

- `bin/reason-vision`
- `bin/reasonunit-runtime-native`

Both executables are verified during staged distribution validation. Built
packages support fresh installation without resolving Cargo or Rust on the
target machine.

Use the following to write only the numerical result:

```sh
reason run simulation.rsn --result-output frames.json
```

The release remains runtime-compatible with `>=0.5.0,<0.6.0`.

Validation: version consistency 6/6, canonical CI 1085 tests, installed
distribution 36/36, both native smoke probes PASS, and package SHA-256
verification PASS.
