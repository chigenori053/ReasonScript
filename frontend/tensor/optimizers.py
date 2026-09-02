"""Language-to-runtime integration for the `optimizer.*` namespace.

Implements the "Optimizer" scope that was previously deferred (see
AGENTS.md's earlier "Optimizers: Pending" note): SGD, Momentum, and
Adam/AdamW, expressed as pure step functions over Tensors, following the
same "backend neutral registry + numeric execution stays in
`.runtime`" split as `frontend.tensor.integration` for `tensor.*`.

Unlike `tensor.*`, every `optimizer.*` function returns a single new
Tensor (never a struct): ReasonScript's static type checker only
resolves `.field` access on a `NamedTypeNode` that has a matching
`StructDeclarationNode` in scope (see
`frontend/language_surface/validation.py`'s `_expression_type` for
`MemberAccessNode`), and there is no such declaration for a synthetic
"optimizer step result" type. Returning one Tensor per call sidesteps
that gap entirely rather than reintroducing it (the same gap is why
`tensor.save`'s `TensorArtifactReceipt` result can be stored but not
field-accessed today). Callers that need `param` and updated
optimizer state (velocity / first and second moment) call the relevant
functions for each value they want to keep, e.g.:

    let velocity = optimizer.momentum_velocity(grad, velocity, 0.9)
    let param = optimizer.momentum(param, grad, velocity, 0.01, 0.9)

This is a real (small) redundancy in the elementwise work between the
"state" and "param" calls for Momentum/Adam/AdamW -- both recompute the
same combined gradient term -- traded for a strictly simpler, statically
type-checkable language surface. Not implemented: a stateful
`optimizer.step(handle, ...)` object API (would need a new
mutable-handle runtime concept ReasonScript doesn't have), learning-rate
schedulers, and gradient clipping -- all out of scope for this pass.
"""

from __future__ import annotations

from typing import Any

from frontend.language_surface.nodes import CallExpressionNode, ExpressionNode, IdentifierNode, MemberAccessNode

from .integration import _UNKNOWN, _literal

# name -> exact argument count. Every argument beyond the Tensor operands
# (`lr`, `momentum`, `beta1`, `beta2`, `eps`, `weight_decay`, `step`) is a
# plain Int/Float scalar, exactly like `tensor.softmax(input, axis)`
# mixes a Tensor and an Int today.
OPTIMIZER_SIGNATURES: dict[str, int] = {
    "optimizer.sgd": 3,  # param, grad, lr
    "optimizer.momentum_velocity": 3,  # grad, velocity, momentum
    "optimizer.momentum": 5,  # param, grad, velocity, lr, momentum
    "optimizer.adam_moment1": 3,  # grad, m, beta1
    "optimizer.adam_moment2": 3,  # grad, v, beta2
    "optimizer.adam": 9,  # param, grad, m, v, step, lr, beta1, beta2, eps
    "optimizer.adamw": 10,  # ...adam args..., weight_decay
}

# Tensor-typed argument positions (0-indexed) per function -- everything
# else is a plain Int/Float scalar. Used only for the same "literal
# passed where a Tensor is required" static check `tensor.*` already
# does (TSF-015's Optimizer counterpart).
_TENSOR_ARGUMENT_POSITIONS: dict[str, tuple[int, ...]] = {
    "optimizer.sgd": (0, 1),
    "optimizer.momentum_velocity": (0, 1),
    "optimizer.momentum": (0, 1, 2),
    "optimizer.adam_moment1": (0, 1),
    "optimizer.adam_moment2": (0, 1),
    "optimizer.adam": (0, 1, 2, 3),
    "optimizer.adamw": (0, 1, 2, 3),
}


class OptimizerSemanticError(ValueError):
    """Stable semantic diagnostic raised before Reason IR lowering."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code} {message}")


def optimizer_call_name(value: Any) -> str | None:
    """Resolve ``optimizer.name(...)`` without treating ``optimizer`` as a module."""
    value = value.expression if isinstance(value, ExpressionNode) else value
    if not isinstance(value, CallExpressionNode):
        return None
    callee = value.callee
    if (
        isinstance(callee, MemberAccessNode)
        and isinstance(callee.object, IdentifierNode)
        and callee.object.name == "optimizer"
    ):
        return f"optimizer.{callee.member}"
    return None


def validate_optimizer_call(value: CallExpressionNode) -> None:
    name = optimizer_call_name(value)
    if name is None:
        return
    if name not in OPTIMIZER_SIGNATURES:
        raise OptimizerSemanticError("OPT-001", f"unknown Optimizer function: {name}")
    expected = OPTIMIZER_SIGNATURES[name]
    if len(value.arguments) != expected:
        raise OptimizerSemanticError(
            "OPT-002",
            f"Optimizer function argument count mismatch: {name} expects {expected}",
        )
    for position in _TENSOR_ARGUMENT_POSITIONS.get(name, ()):
        literal = _literal(value.arguments[position])
        if literal is not _UNKNOWN:
            raise OptimizerSemanticError("OPT-003", "Optimizer Tensor argument type mismatch")
