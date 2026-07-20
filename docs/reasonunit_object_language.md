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

