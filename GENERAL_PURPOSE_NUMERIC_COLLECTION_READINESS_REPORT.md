# General-purpose numeric and collection readiness

Validation date: 2026-09-28; repository commit:
`b534e0887c10b6fc80d417ea76b9f53bb4c0c15e`;
ReasonScript: `0.5.6.2`; ReasonRuntime: `0.5.6.2`.

This is a capability assessment, not a language extension. The executable
probe is [`tests/readiness/numeric_collection.rsn`](tests/readiness/numeric_collection.rsn);
[`tests/readiness/test_numeric_collection_readiness.py`](tests/readiness/test_numeric_collection_readiness.py)
checks its native CLI results, generated-size variation, determinism, and
error boundaries. No production runtime or compiler code was changed.

## Primary gates

| Gate | Result | Evidence and limit |
| --- | --- | --- |
| GNC-1 Real numeric model | PARTIAL | Finite `float` literals, arithmetic, ordering and exact equality run natively. `0.1 + 0.2 == 0.3` is `false`. `2 + 0.5 * 4` passes `check` but fails at runtime with `IR-EXEC-008`; overflow fails during IR decoding (`IR-DECODE-001`), underflow yields `0.0`, and division by zero returns `RT-ARITH-001`. |
| GNC-2 Numeric functions | PARTIAL | Arithmetic works. Unqualified `abs`, `sqrt`, and `sin` fail with `RT-CALL-001`. Tensor has native `abs`, `sqrt`, `exp`, `log`, `min`, and `max`, but those operate on Tensor rather than general scalar values. No scalar `floor`, `ceil`, `round`, or trigonometric API was established. |
| GNC-3 Sequence generation | PARTIAL | `while` plus `array.builder()` generates 200 floats and 100 value sequences. `range(0,10,1)` fails with `RT-CALL-001`. There is no defined reusable range API with end, step-direction, zero-step, and floating accumulation semantics. A non-progressing loop stops at the runtime iteration limit. |
| GNC-4 Collections | SUPPORTED | Native ordered arrays, empty and nested arrays, indexing, length, builder append/finish, and iteration work. `xs[10]` for a three-element array returns `RT-INDEX-002`. Generic heterogeneous `Collection<T>` was not established; structs and tuples supply structured elements. |
| GNC-5 Collection operations | SUPPORTED | `for`, conditions, arithmetic and `array.builder()` produce mapped `[1,4,9,16]`, filtered `[4,5]` in original order, and deterministic reductions. These are operation equivalents; generic higher-order `map/filter/reduce` functions are not required by the specification. |
| GNC-6 Iteration | SUPPORTED | Native loops execute 10, 100 and 1,000 iterations. The 1,000-iteration sum is `499500`; infinite `while` exits with `RT-LOOP-001` at 10,000 iterations. Runtime metrics expose iteration count and peak managed bytes. |
| GNC-7 Reusable evaluation | SUPPORTED | The typed `Square(float) -> float` function is called over 100 generated inputs. `sin` over 100 inputs is unavailable because scalar `sin` is unavailable; this does not negate reusable function evaluation. |
| GNC-8 Structured data | SUPPORTED | `Point`, `Metadata`, and nested `Dataset` structs with arrays compile and run natively. Field contents and ordering are repeatable. |
| GNC-9 Strings and serialization | PARTIAL | String literals, escaping, concatenation, `string.from_int`, and `string.from_float` work. Direct string ordering (`"A" < "B"`) is rejected (`CV-2`). The CLI serializes structured runtime results to JSON deterministically at the `runtime_result` level, but no in-language generic `Serialize(Value)` operation was established. |
| GNC-10 Artifact output | UNSUPPORTED | `reason artifacts` creates valid compiler artifacts, and `tensor.save` supports Tensor files with explicit write permission. Neither is a generic in-language `Dataset -> serialize -> file` operation. Redirecting CLI JSON through a shell would make the external process perform artifact creation and is not native support. |

## Canonical scenarios

| Scenario | Result | Observation |
| --- | --- | --- |
| R-01 Real arithmetic | SUPPORTED | Native result of exact comparison is `false`; approximation needs a defined API. |
| R-02 Floating range | PARTIAL | A loop generates 200 values from `-10.0` through approximately `9.9`; reusable `range(start,end,step)` is absent. |
| R-03 Numeric collection | SUPPORTED | 100 real values retained in an array. |
| R-04 Point collection | SUPPORTED | 100 generic `Point` values generated, with `Point(37,1369)`. |
| R-05 Collection iteration | SUPPORTED | `for` visits array values in order. |
| R-06 Repeated expression | SUPPORTED | `Square(x)` evaluates 100 generated inputs. |
| R-07 Scientific expression | UNSUPPORTED | Scalar `sin(x)` returns `RT-CALL-001`; reusable evaluation itself is supported. |
| R-08 Nested object | SUPPORTED | `Dataset` contains name, two real arrays, and nested metadata. |
| R-09 Canonical serialization | PARTIAL | Three independent native CLI `runtime_result` JSON segments match byte for byte; generic serialization is not callable from source. Other CLI artifact/trace sections were not shown to be byte stable. |
| R-10 Artifact generation | UNSUPPORTED | No native generic value-to-file operation for R-08. Compiler artifacts validate but do not contain a serialized Dataset file. |

## Extended matrix

| Group | Result | Group | Result | Group | Result |
| --- | --- | --- | --- | --- | --- |
| A Real literals | SUPPORTED | J Floating range | PARTIAL | S Iteration | SUPPORTED |
| B Real arithmetic | SUPPORTED | K Range boundaries | UNSUPPORTED | T Iteration bounds | SUPPORTED |
| C Mixed Integer/Real | PARTIAL | L Collection creation | SUPPORTED | U Expression representation | SUPPORTED |
| D Numeric comparison | SUPPORTED | M Collection access | SUPPORTED | V Repeated evaluation | SUPPORTED |
| E Approximation | PARTIAL | N Nested collection | SUPPORTED | W Structured data | SUPPORTED |
| F Invalid numeric states | PARTIAL | O Collection bounds | SUPPORTED | X String/formatting | PARTIAL |
| G Basic math functions | PARTIAL | P Map equivalent | SUPPORTED | Y Canonical serialization | PARTIAL |
| H Scientific functions | PARTIAL | Q Filter equivalent | SUPPORTED | Z Artifact output | UNSUPPORTED |
| I Integer range | PARTIAL | R Reduce equivalent | SUPPORTED | | |

`H` is partial because native Tensor `exp` and `log` exist, while general scalar
trigonometry does not. `E` is partial because tolerance comparison can be
expressed with ordinary arithmetic and conditions, but has no defined numeric
library function or edge semantics. `K` concerns reusable range semantics;
hand-written loop boundaries are available but do not define a language range.

## Native, determinism, resource, and anti-cheating evidence

`./reason run tests/readiness/numeric_collection.rsn --json` takes `.rsn`
through the normal frontend and computation IR into the production Rust
ReasonRuntime. `array.builder`, arithmetic, loops, functions, structs and
collection operations are dispatched by the native host. Python in the test
file only launches the CLI and inspects results; it does not generate the
collections or calculate the runtime values. A generated 73-element variant
confirms the program does not depend on the 100-element fixture or filename.
There are no test-only runtime branches or precomputed source samples.

Three independent executions return identical calculation values and
`runtime_result` JSON bytes. At the standard 100-element size, metrics recorded
1,414 loop iterations, 506 builder appends, and approximately 94 KiB peak
managed memory; these are deterministic managed proxies rather than a physical
memory benchmark. The 10,000-iteration guard returns `RT-LOOP-001` for an
unbounded loop. The floating sequence's last value is
`9.900000000000002`, showing binary floating representation rather than an
exact decimal endpoint.

## Required extensions and priority

| Priority | Language/library contract | Runtime work |
| --- | --- | --- |
| 1 | Define mixed integer/real coercion and explicit non-finite, overflow, and underflow semantics. | Repair mixed arithmetic lowering (`IR-EXEC-008`) and overflow IR decoding (`IR-DECODE-001`). |
| 2 | Define a bounded generic sequence API with exclusive/inclusive end, step direction, zero-step error, and floating evaluation rule. | Implement sequence generation in Rust with an element limit and resource diagnostic. |
| 3 | Define generic `Serialize(Value)` and artifact emission, including path, overwrite, UTF-8 encoding, and failure rules. | Reuse runtime write capabilities to persist serialized generic values. |
| 4 | Define scalar math and tolerance comparison; add scientific functions when needed. | Expose native scalar `abs`, `min`, `max`, `floor`, `ceil`, `round`, `sqrt`, and optionally `sin`, `cos`, `tan`, `log`, `exp`. |
| 5 | Document canonical numeric-to-string formatting and string comparison semantics. | Keep native string conversion and CLI JSON output aligned with the documented rules. |

The supported capabilities are arrays, ordered collection operations, bounded
iteration, reusable functions, and nested structs. Partial capabilities are
general floating numerics, scalar math, sequences, strings, and serialization.
Generic value artifact output is unsupported. The sequence API and generic
artifact path are the main blockers for reusable data-producing toolkits. No
compatibility baseline or Golden output was changed.

## Validation status

`reason check` and `reason run` passed for the positive source probe. All 11
focused readiness tests passed; artifact generation and `validate-artifacts`
passed; Golden corpus passed (2/2). Final `./reason ci --json` passed all
phases with 2,722 tests passed. The initial sandboxed CI run failed `CI-008`
because the existing environment-parity test could not create a temporary
`.git/worktrees/...` directory. Re-running the unchanged suite with permission
for that directory passed.
