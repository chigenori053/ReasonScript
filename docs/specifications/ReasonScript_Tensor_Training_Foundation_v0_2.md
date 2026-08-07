# ReasonScript Tensor Training Foundation v0.2

Specification ID: `reasonscript-tensor-training-foundation/0.2`
Status: VALIDATED
Target: ReasonScript v0.5.4.4

## 1. Purpose

Tensor Training Foundation v0.2 extends the backend-neutral Tensor runtime from
inference-only primitives to deterministic, file-backed, differentiable image
model training. It adds slicing and gather, seeded random creation, canonical
Tensor file I/O, reverse-mode automatic differentiation, Conv2d, MaxPool2d, and
AvgPool2d.

## 2. Public functions

Data selection:

- `tensor.slice(value, starts, ends, axes?, steps?)`
- `tensor.narrow(value, axis, start, length)`
- `tensor.gather(value, indices, axis?)`

Deterministic creation:

- `tensor.random_uniform(shape, low?, high?, seed?, stream?, dtype?)`
- `tensor.random_normal(shape, mean?, std?, seed?, stream?, dtype?)`
- `tensor.random_bernoulli(shape, probability?, seed?, stream?)`
- `tensor.random_permutation(size, seed?, stream?)`

File I/O:

- `tensor.load(path)`
- `tensor.save(value, path, overwrite?)`

Automatic differentiation:

- `tensor.parameter(value)`
- `tensor.detach(value)`
- `tensor.requires_grad(value)`
- `tensor.grad(loss, parameters)`

Spatial operators:

- `tensor.conv2d(input, weight, bias?, stride?, padding?, dilation?, groups?)`
- `tensor.max_pool2d(input, kernel, stride?, padding?)`
- `tensor.avg_pool2d(input, kernel, stride?, padding?, count_include_pad?)`

## 3. Determinism

Random functions are stateless. Their output is determined by the complete
tuple `(function, shape, dtype, seed, stream)` and does not depend on call order
or host entropy. Runtime file reads are verified by the Tensor container
checksum. Atomic file writes use canonical metadata and little-endian payloads.

## 4. Tensor file profile

The `.rstensor` profile is a single file:

1. eight-byte magic `RSNTNSR1`;
2. unsigned little-endian 32-bit canonical JSON header length;
3. canonical UTF-8 JSON header;
4. contiguous little-endian Tensor payload.

The header contains profile, shape, dtype, byte size, and SHA-256 of the
payload. Paths are relative to the configured resource root. Reads require
`filesystem_read`; writes require `filesystem_write`. Absolute paths, parent
segments, platform separators, and root escape are rejected.

## 5. Spatial semantics

Conv2d uses NCHW input and OIHW weight layout. Stride, symmetric padding, and
dilation are two-element positive integer arrays. Groups must divide both input
and output channels.

Pooling uses NCHW layout. MaxPool selects the first flattened kernel position
when maxima are equal. AvgPool excludes padded positions unless
`count_include_pad` is true.

## 6. Automatic differentiation

The runtime records a bounded reverse-mode tape only when an operation consumes
a parameter or another differentiable value. `tensor.grad` requires a scalar
floating-point loss and returns gradients in parameter order. Broadcast
gradients reduce to the original input shape. Gather and MaxPool gradients use
deterministic scatter-add.

The tape is an explicit Tensor lifecycle root. It is released after `grad`
unless retained by a future profile. `detach` removes the selected result's
recorded ancestry. Integer and Boolean Tensor values are not differentiable.

## 7. Safety policies

Tensor policy adds maximum autograd nodes and saved Tensor bytes. File payloads
remain subject to maximum artifact bytes. Invalid shapes, indices, convolution
parameters, pool parameters, graph state, paths, capabilities, formats, and
checksums use stable Tensor diagnostics without host tracebacks.

## 8. Acceptance

- A `.rstensor` round trip preserves shape, dtype, values, and checksum.
- Equal random arguments produce byte-identical values; a changed stream
  produces a different sequence.
- Slice and gather match reference values and gradients.
- Existing arithmetic and matrix functions pass finite-difference gradient
  checks.
- Conv2d and pooling forward results and gradients match fixed reference
  fixtures.
- A ReasonScript calculation can load image and label Tensors, initialize
  weights, select a minibatch, execute Conv2d/ReLU/Pool/Linear, compute a scalar
  loss, obtain gradients, update parameters, and save a checkpoint without
  embedding data or initial weights as literals.
- `reason ci --json` passes without updating unrelated golden baselines.
