# ReasonScript Tensor Call-Frame Liveness Remediation v0.1

Status: VALIDATED
Issue: [GitHub #9](https://github.com/chigenori053/ReasonScript/issues/9)
Target: the next compatible v0.5.5 patch release
Classification: Rust computation VM Tensor-lifetime correctness defect

## 1. Purpose

This specification defines the correction for `TSF-001 unknown Tensor handle`
raised by a valid forward computation when a Tensor-producing user function is
followed by Tensor operations in its caller.

The canonical reproduction is a LayerNorm-style user function followed by an
attention-style `tensor.linear` / `tensor.narrow` / `tensor.matmul` /
`tensor.softmax` chain. Static validation and build succeed, but native runtime
execution fails because a Tensor that remains reachable from the suspended
caller frame is removed from the Rust `TensorStore` while the callee executes.

This document refines the Tensor reachability requirements already established
by `ReasonScript Tensor Iteration Reliability Remediation v0.1`. It does not add
new language syntax, Tensor functions, or diagnostics.

## 2. Observed defect

The Rust computation VM performs Tensor collection after an instruction in a
user function. The collection root set is derived only from the environment of
the function currently executing.

During a call such as:

```reason
let normed = LayerNorm(h, gamma, beta)
let q = tensor.linear(normed, wq)
```

the callee environment contains `h`, `gamma`, `beta`, and its local values, but
does not contain caller-only values such as `wq` and `bias`. The caller frame is
still active and will use those values after `LayerNorm` returns. Collecting
against only the callee environment therefore removes live caller Tensors. The
later `tensor.linear` resolves a still-valid language-level handle whose backing
store entry has already been deleted and incorrectly emits `TSF-001`.

The defect is not exhaustion of `max_live_tensors`. Genuine resource exhaustion
continues to use `TSF-013`.

## 3. Normative lifetime model

### 3.1 Ownership

One native program execution owns one Tensor store. Entering a user function
does not create a Tensor ownership boundary and does not transfer ownership of
arguments from caller to callee.

A Tensor handle MUST remain resolvable while its Tensor is transitively
reachable from any runtime root defined in this section.

### 3.2 Runtime roots

At every Tensor collection safe point, the root set MUST be the union of:

1. every binding in every active call frame, including suspended callers;
2. the current calculation environment and retained prior calculation results;
3. arguments already evaluated for an in-progress call or operation;
4. intermediate values that remain live during expression evaluation;
5. a `return` or `result` value from its creation until the receiving context
   has installed or serialized it;
6. Tensor handles transitively contained in arrays and struct fields; and
7. runtime-owned autograd state and other explicitly retained native state.

Duplicate references MUST NOT alter the result. Recursive and mutually nested
function calls MUST use the same union-of-active-frames rule at every depth.

Reasoning objects, trace snapshots, and serialized Tensor metadata do not keep a
Tensor alive unless their runtime value model contains an actual Tensor handle.

### 3.3 Safe collection points

Collection MAY occur after a completed instruction, block transition, function
return handoff, or calculation boundary only when the VM can construct the
complete root set above.

Collection MUST NOT run with only the current callee environment when another
call frame is active. It MUST NOT run between producing a return value and
installing that value in the caller unless the pending return value is itself a
root.

Deferring every collection until program termination is conforming for lifetime
correctness but is not sufficient for acceptance because bounded iterative
programs must continue to release unreachable intermediate Tensors. The final
implementation MUST preserve incremental collection at safe points.

### 3.4 Transitive reachability

Root traversal MUST recursively inspect all supported runtime containers that
can contain `Value::Tensor`. At minimum this includes arrays and struct fields.
Aliased containers MUST be handled without changing aliasing semantics, and
cyclic or shared container graphs MUST not cause unbounded traversal.

### 3.5 Handle errors

`TSF-001` remains the diagnostic for a genuinely unknown, forged, expired, or
otherwise invalid Tensor handle. It MUST NOT be emitted for a Tensor reachable
from an active caller, callee, pending argument, pending return, calculation
result, or autograd root.

`TSF-013` remains the diagnostic when the number of genuinely live Tensors
exceeds the configured resource policy. This remediation MUST NOT convert
resource-limit failures into `TSF-001`, or hide them by disabling collection
and limit enforcement.

## 4. Required runtime behavior

The native computation VM SHALL maintain sufficient execution context to derive
the roots of all active frames. An implementation may use an explicit frame
stack, a scoped root guard, or an equivalent mechanism, provided that the
observable behavior satisfies this specification.

For a user-function call, the following handoff is atomic with respect to Tensor
collection:

1. evaluate arguments while caller roots remain active;
2. create the callee frame and bind its parameters;
3. execute the callee while both caller and callee roots remain active;
4. evaluate the return expression and retain the returned value;
5. remove the callee frame only after the return value is protected; and
6. install the return value in the caller before it may cease to be a temporary
   root.

Normal return, runtime error propagation, loop exit, and call-depth-limit paths
MUST release frame-root registrations deterministically. A failed call MUST NOT
leave stale roots that later cause false `TSF-013` failures.

## 5. Compatibility requirements

- The `.rsn` language surface and Computation IR schema remain unchanged.
- Tensor IDs, numerical values, dtype behavior, RNG determinism, and execution
  ordering remain unchanged.
- The public Tensor Standard Functions manifest remains unchanged.
- Existing `TSF-*`, `RT-*`, and `IR-*` diagnostic meanings remain unchanged.
- Python reference runtimes remain reference-only; production execution stays
  Rust-only and MUST NOT add a Python fallback.
- The existing long-loop liveness guarantee remains in force: unreachable
  overwritten Tensors must be reclaimed before they cause false `TSF-013`.
- Runtime trace enablement MUST NOT change Tensor lifetime or program outcome.

## 6. Required validation fixtures

### 6.1 Exact Issue #9 regression

The complete LayerNorm-then-attention program from GitHub Issue #9 SHALL be a
committed regression fixture. With the Rust computation VM it MUST satisfy:

- `reason check`: success;
- `reason build`: success;
- `reason run --allow-read --allow-write --json`: success;
- result: `true` for output shape `[16, 16]`;
- no `TSF-001` or `TSF-013`; and
- repeated execution produces the same result and diagnostic sequence.

The fixture MUST execute through `integrated-rust` /
`rust_computation_vm`; passing through a Python reference evaluator is not
acceptable evidence.

### 6.2 Caller-only root regression

A focused test SHALL keep at least one Tensor exclusively in the caller frame,
invoke a Tensor-producing user function that executes enough instructions to
trigger collection, then consume the caller-only Tensor after return. The test
MUST prove that the backing Tensor remains available.

### 6.3 Return-value handoff regression

A user function SHALL return:

1. a direct Tensor;
2. a Tensor produced by a nested Tensor expression;
3. an array containing a Tensor; and
4. a struct field containing a Tensor.

Each returned value MUST remain usable immediately after return and after the
next collection safe point.

### 6.4 Nested and recursive frames

Tests SHALL cover at least three active function frames and a bounded recursive
call. A Tensor used only by the outermost suspended frame MUST remain available
after all inner calls return.

### 6.5 Reclamation and limits

The existing 1,100-iteration Tensor liveness regression SHALL continue to pass.
Additional assertions SHALL demonstrate that:

- overwritten, unreachable intermediates are removed;
- active-frame Tensors are not removed;
- frame roots are released after normal return and runtime error; and
- a deliberately low `max_live_tensors` still produces `TSF-013` for genuinely
  live values.

### 6.6 Differential and trace modes

Where the program is supported by the Python reference evaluator, native output
and error-code behavior SHALL match the reference outcome. Each primary
regression SHALL run with Tensor trace both disabled and enabled.

## 7. Acceptance criteria

This remediation may be marked `VALIDATED` only when all of the following hold:

1. the exact Issue #9 reproduction completes with result `true` in the native
   Rust runtime;
2. all active-frame, nested-frame, return-handoff, container, and error-unwind
   lifetime tests pass;
3. unreachable Tensor reclamation and `max_live_tensors` enforcement remain
   effective;
4. no production Python-runtime fallback is introduced;
5. Tensor manifest and runtime-consolidation manifest checks show no unintended
   contract drift;
6. `reason project-validate` passes the Issue #9 fixture, including runtime and
   determinism validation;
7. generated artifacts validate and intentional golden outputs are documented;
   and
8. the canonical `reason ci` pipeline passes.

The Issue SHALL remain open until these acceptance criteria are recorded in a
completion report with the tested ReasonScript and Runtime versions.

## 8. Non-goals

This remediation does not specify:

- Tensor buffer reuse or arena compaction;
- a new public garbage-collection API;
- changes to autograd graph semantics;
- Tensor ID reuse;
- attention or LayerNorm as new standard functions;
- changes to Tensor resource-policy defaults; or
- performance optimizations unrelated to lifetime correctness.

## 9. Completion report requirements

The implementation completion report MUST include:

- the selected active-frame root-management design;
- files and runtime components changed;
- exact Issue #9 command results;
- focused lifetime and reclamation test results;
- `reason project-validate` determinism results;
- `reason ci` results;
- artifact and golden-test status;
- compatibility notes; and
- any remaining lifetime limitations.
