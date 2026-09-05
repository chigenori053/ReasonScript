# ReasonUnit Object language integration

Bind a canonical Object explicitly inside a model or compatibility module:

```reason
model VehicleAnalysis {
    reason_object vehicle from "objects/vehicle.ruo"
        resources "objects/resources"
        mode strict
        as "ruo:object:vehicle";
}
```

The binding name is not the Object ID. Paths are relative and require an
explicit read capability at execution. Saving additionally requires write
capability, an output path, and an overwrite decision. Use `reason object
check SOURCE.rsn` for static validation and `reason object run SOURCE.rsn
--allow-read` for verified native loading. Network and shell-expanded paths are
not supported.

`reason object` does not evaluate numerical physics expressions. Use
`reason run SOURCE.rsn` for scalar, array, Tensor, loop, function, and struct
computation. Object inspection reports structural validity; numerical semantic
evaluation is not applicable to that operation.

## First-class bindings

`ReasonObject` and the opaque values returned by `ruo.*` are valid function
parameter, return, and local-binding types. A bound Object can therefore be
aliased and passed through ordinary pure functions:

```reason
fn Identity(value: ReasonObject) -> ReasonObject {
    return value
}

calculation Probe {
    let current = Identity(vehicle)
    result = ruo.object_id(current)
}
```

Run this form with `reason run SOURCE.rsn --allow-read`. The calculation
runtime verifies and loads each declared Object under the source resource root.
Without `--allow-read`, execution fails with `RUO-N2-007`.

Opaque RUO values do not expose mutable fields. Object changes retain the
snapshot/transaction contract: `ruo.snapshot`, `ruo.begin`, `ruo.apply`, and
`ruo.commit` are used instead of assignment through a field. `ruo.*` validates
argument kinds statically when they are known and reports `RUO-N2-009` for a
type mismatch.
