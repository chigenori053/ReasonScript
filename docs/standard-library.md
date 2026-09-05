# ReasonScript standard library

Standard-library calls are namespaced and validated before native execution.
This page is a practical index; exact Tensor signatures are available from
`reason tensor-manifest --json` and the frozen baseline in
`contracts/tensor_function_manifest.json`.

## Runtime

| Call | Purpose |
| --- | --- |
| `runtime.input()` | Read the configured runtime input. |
| `runtime.print(value)` | Emit a value through the runtime output channel. |
| `runtime.search(...)` | Execute deterministic reasoning search. |
| `runtime.simulate(...)` | Simulate a reasoning model. |
| `runtime.predict(...)` | Produce a deterministic prediction. |
| `runtime.plan(...)` | Construct an execution plan. |

The reasoning calls operate on typed `Goal`, `State`, `Constraint`,
`ReasonGraph`, and `ExecutionPlan` bindings.

## Tensor

Tensor dtypes are `bool`, `i32`, `i64`, `f32`, and `f64`; the current backend is
CPU. Major function groups are:

| Group | Functions |
| --- | --- |
| Creation | `create`, `zeros`, `ones`, `full` |
| Random | `random_uniform`, `random_normal`, `random_bernoulli`, `random_permutation` |
| Inspection | `shape`, `rank`, `size`, `dtype`, `dimension` |
| Shape/indexing | `reshape`, `flatten`, `transpose`, `squeeze`, `unsqueeze`, `concat`, `stack`, `slice`, `narrow`, `gather` |
| Binary math | `add`, `subtract`, `multiply`, `divide`, `power`, `maximum`, `minimum` |
| Comparison | `equal`, `not_equal`, `greater`, `greater_equal`, `less`, `less_equal` |
| Elementwise | `negate`, `abs`, `exp`, `log`, `sqrt`, `relu` |
| Reduction | `sum`, `mean`, `min`, `max`, `argmax`, `argmin` |
| Linear algebra | `dot`, `matmul`, `norm`, `linear` |
| Neural network | `softmax`, `conv2d`, `max_pool2d`, `avg_pool2d` |
| Autograd | `parameter`, `detach`, `requires_grad`, `grad` |
| Conversion/I/O | `cast`, `to_array`, `scalar`, `load`, `save` |

Example:

```reason
calculation Average -> float {
  let values = tensor.create([1.0, 2.0, 3.0], "f64")
  let mean = tensor.mean(values)
  result = tensor.scalar(mean)
}
```

Tensor file paths are relative to the source resource root. `tensor.load`
requires read capability; `tensor.save` requires write capability. Absolute and
root-escaping paths are rejected.

## Optimizer

Optimizer calls are pure functions that return a new, untracked Tensor. The
caller owns the state Tensor and positive integer step counter.

```text
optimizer.sgd(param, grad, lr)
optimizer.momentum_velocity(grad, velocity, momentum)
optimizer.momentum(param, grad, velocity, lr, momentum)
optimizer.adam_moment1(grad, m, beta1)
optimizer.adam_moment2(grad, v, beta2)
optimizer.adam(param, grad, m, v, step, lr, beta1, beta2, eps)
optimizer.adamw(param, grad, m, v, step, lr, beta1, beta2, eps, weight_decay)
```

All arguments are positional. There is no mutable optimizer-handle API.

## Relation

Relation functions operate on `Array<Struct>`. Field names are strings.

```text
relation.filter_eq(rows, field, value)
relation.filter_ne(rows, field, value)
relation.filter_gt(rows, field, value)
relation.filter_gte(rows, field, value)
relation.filter_lt(rows, field, value)
relation.filter_lte(rows, field, value)
relation.count(rows)
relation.distinct_by(rows, field)
relation.sort_by(rows, field, descending)
```

Calls are positional and return new values without mutating the input rows.

## String

```text
string.concat(left, right)
string.join(separator, values)
string.length(value)
string.from_int(value)
string.from_float(value)
string.slice(value, start, end)
```

String calls are pure and positional.

## Vision and ReasonUnit Objects

`vision.infer` and `vision.build_ruo` execute in the native host and can produce
Tensor and ReasonUnit Object resources. `ruo.*` provides typed, opaque access
to ReasonUnit Objects, including identity/metadata queries and snapshot-based
transactions. See [ReasonUnit Objects](reasonunit-object.md) for bindings,
capabilities, and CLI examples.

## Discovering exact contracts

```sh
reason tensor-manifest --json
reason runtime-manifest --json
reason help
```

Prefer these machine-readable commands when generating code or validating an
integration.
