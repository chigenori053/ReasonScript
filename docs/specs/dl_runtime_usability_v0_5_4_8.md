# DL Runtime Usability v0.5.4.8

Status: IMPLEMENTED

## Package execution

`reason run` now compiles all `.rsn` sources in `src/` as one package graph and
executes that graph through the integrated computation runtime. Public functions
may therefore be imported from another source file and called with `module::fn`.
`--entry Module::Calculation` selects the JSON result of a named calculation.

## Sparse Tensor arguments

Tensor named arguments may be supplied in any order. Missing optional positions
are materialized from the public operation signature before semantic validation
and execution. `none` is accepted where the Tensor contract has a null default;
`null` remains accepted directly. Positional arguments must precede named ones.

## External result projection

The inline result limit remains 256 elements. A larger result Tensor is not an
execution failure: when a result artifact directory is configured it is emitted
as a JSON payload file with shape, dtype, byte size, SHA-256 checksum, and a
stable external reference. Package runs use `target/runtime/results/`.

The complete Tensor value remains verifiable through the checksum. The result
JSON contains metadata rather than duplicating a large numeric payload.

## Functional training library

The standard namespaces are:

- `optimizer.sgd(parameters, gradients, learning_rate, weight_decay?)`
- `optimizer.momentum(parameters, gradients, state, learning_rate, momentum?, weight_decay?)`
- `optimizer.adam(parameters, gradients, state, learning_rate, beta1?, beta2?, epsilon?, weight_decay?)`
- `optimizer.adamw(parameters, gradients, state, learning_rate, beta1?, beta2?, epsilon?, weight_decay?)`
- `scheduler.step_decay(learning_rate, epoch, step_size, gamma?)`
- `scheduler.cosine(learning_rate, step, total_steps, minimum?)`
- `scheduler.linear_warmup(learning_rate, step, warmup_steps)`

`sgd` returns the next parameter list. Stateful optimizers return
`{ parameters, state }`; the caller owns and passes `state` at the next step.
This preserves the language's no-hidden-state and reproducible execution model.

Optimizer and scheduler calls are recorded in `tensor_trace` with their complete
input/output Tensor identities. Optimizer output parameters are fresh
`tensor.parameter` values, ready for the next `tensor.grad` call.
