"""Functional optimizer standard library built on the Tensor reference API."""

from __future__ import annotations

import math
from typing import Any

from frontend.language_surface.nodes import CallExpressionNode, IdentifierNode, MemberAccessNode
from frontend.tensor import TensorError, TensorRuntime, TensorValueRef


class OptimizerError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def optimizer_call_name(value: Any) -> str | None:
    if not isinstance(value, CallExpressionNode) or not isinstance(value.callee, MemberAccessNode):
        return None
    if not isinstance(value.callee.object, IdentifierNode):
        return None
    namespace = value.callee.object.name
    if namespace not in {"optimizer", "scheduler"}:
        return None
    return f"{namespace}.{value.callee.member}"


def call_optimizer(name: str, runtime: TensorRuntime, *args: Any) -> Any:
    functions = {
        "optimizer.sgd": _sgd,
        "optimizer.momentum": _momentum,
        "optimizer.adam": _adam,
        "optimizer.adamw": _adamw,
        "scheduler.step_decay": _step_decay,
        "scheduler.cosine": _cosine,
        "scheduler.linear_warmup": _linear_warmup,
    }
    function = functions.get(name)
    if function is None:
        raise OptimizerError("OPT-001", f"unknown optimizer or scheduler function: {name}")
    try:
        output = function(runtime, *args) if name.startswith("optimizer.") else function(*args)
    except (TypeError, TensorError) as error:
        raise OptimizerError("OPT-002", f"invalid {name} arguments") from error
    runtime.trace.append({
        "step_id": f"step_{len(runtime.trace)+1:04d}",
        "operation_type": "optimizer_call",
        "function_id": name,
        "inputs": [_trace_value(value) for value in args],
        "output": _trace_value(output),
        "status": "success",
        "diagnostics": [],
    })
    return output


def _parameters(runtime: TensorRuntime, parameters: Any, gradients: Any) -> tuple[list[TensorValueRef], list[TensorValueRef]]:
    if not isinstance(parameters, list) or not isinstance(gradients, list) or not parameters or len(parameters) != len(gradients):
        raise OptimizerError("OPT-002", "parameters and gradients must be non-empty arrays of equal length")
    if not all(isinstance(value, TensorValueRef) for value in [*parameters, *gradients]):
        raise OptimizerError("OPT-002", "parameters and gradients must be Tensor values")
    for parameter, gradient in zip(parameters, gradients):
        if runtime._tensor(parameter).shape != runtime._tensor(gradient).shape:
            raise OptimizerError("OPT-003", "parameter and gradient shapes must match")
    return parameters, gradients


def _updated_parameter(runtime: TensorRuntime, parameter: TensorValueRef, values: list[float]) -> TensorValueRef:
    source = runtime._tensor(parameter)
    return runtime.parameter(runtime._new(source.shape, source.dtype, values))


def _state_values(runtime: TensorRuntime, state: Any, name: str, parameters: list[TensorValueRef]) -> list[TensorValueRef]:
    if state is None:
        return [runtime._new(runtime._tensor(value).shape, value.dtype, [0.0] * len(runtime._tensor(value).data)) for value in parameters]
    if not isinstance(state, dict) or not isinstance(state.get(name), list) or len(state[name]) != len(parameters):
        raise OptimizerError("OPT-004", f"optimizer state is missing {name}")
    values = state[name]
    if not all(isinstance(value, TensorValueRef) for value in values):
        raise OptimizerError("OPT-004", f"optimizer state {name} must contain Tensors")
    return values


def _sgd(runtime: TensorRuntime, parameters: Any, gradients: Any, learning_rate: Any, weight_decay: Any = 0.0) -> list[TensorValueRef]:
    params, grads = _parameters(runtime, parameters, gradients)
    lr, decay = float(learning_rate), float(weight_decay)
    return [
        _updated_parameter(runtime, parameter, [
            value - lr * (gradient + decay * value)
            for value, gradient in zip(runtime._tensor(parameter).data, runtime._tensor(grad).data)
        ])
        for parameter, grad in zip(params, grads)
    ]


def _momentum(runtime: TensorRuntime, parameters: Any, gradients: Any, state: Any, learning_rate: Any, momentum: Any = 0.9, weight_decay: Any = 0.0) -> dict[str, Any]:
    params, grads = _parameters(runtime, parameters, gradients)
    velocity = _state_values(runtime, state, "velocity", params)
    lr, beta, decay = float(learning_rate), float(momentum), float(weight_decay)
    next_velocity, updated = [], []
    for parameter, gradient, previous in zip(params, grads, velocity):
        values = [beta * old + grad + decay * value for value, grad, old in zip(runtime._tensor(parameter).data, runtime._tensor(gradient).data, runtime._tensor(previous).data)]
        next_velocity.append(runtime._new(runtime._tensor(parameter).shape, parameter.dtype, values))
        updated.append(_updated_parameter(runtime, parameter, [value - lr * velocity_value for value, velocity_value in zip(runtime._tensor(parameter).data, values)]))
    return {"parameters": updated, "state": {"velocity": next_velocity}}


def _adam(runtime: TensorRuntime, parameters: Any, gradients: Any, state: Any, learning_rate: Any, beta1: Any = 0.9, beta2: Any = 0.999, epsilon: Any = 1e-8, weight_decay: Any = 0.0, *, decoupled: bool = False) -> dict[str, Any]:
    params, grads = _parameters(runtime, parameters, gradients)
    first = _state_values(runtime, state, "first_moment", params)
    second = _state_values(runtime, state, "second_moment", params)
    step = 1 if state is None else int(state.get("step", 0)) + 1
    lr, b1, b2, eps, decay = float(learning_rate), float(beta1), float(beta2), float(epsilon), float(weight_decay)
    next_first, next_second, updated = [], [], []
    for parameter, gradient, old_first, old_second in zip(params, grads, first, second):
        parameter_values = runtime._tensor(parameter).data
        gradient_values = runtime._tensor(gradient).data
        if not decoupled:
            gradient_values = [gradient + decay * value for gradient, value in zip(gradient_values, parameter_values)]
        first_values = [b1 * old + (1.0 - b1) * grad for old, grad in zip(runtime._tensor(old_first).data, gradient_values)]
        second_values = [b2 * old + (1.0 - b2) * grad * grad for old, grad in zip(runtime._tensor(old_second).data, gradient_values)]
        correction1, correction2 = 1.0 - b1 ** step, 1.0 - b2 ** step
        values = [value * (1.0 - lr * decay) if decoupled else value for value in parameter_values]
        values = [value - lr * (m / correction1) / (math.sqrt(v / correction2) + eps) for value, m, v in zip(values, first_values, second_values)]
        next_first.append(runtime._new(runtime._tensor(parameter).shape, parameter.dtype, first_values))
        next_second.append(runtime._new(runtime._tensor(parameter).shape, parameter.dtype, second_values))
        updated.append(_updated_parameter(runtime, parameter, values))
    return {"parameters": updated, "state": {"step": step, "first_moment": next_first, "second_moment": next_second}}


def _adamw(runtime: TensorRuntime, *args: Any) -> dict[str, Any]:
    return _adam(runtime, *args, decoupled=True)


def _step_decay(learning_rate: Any, epoch: Any, step_size: Any, gamma: Any = 0.1) -> float:
    if int(step_size) <= 0:
        raise OptimizerError("OPT-002", "step_size must be positive")
    return float(learning_rate) * float(gamma) ** (int(epoch) // int(step_size))


def _cosine(learning_rate: Any, step: Any, total_steps: Any, minimum: Any = 0.0) -> float:
    if int(total_steps) <= 0:
        raise OptimizerError("OPT-002", "total_steps must be positive")
    fraction = min(max(int(step), 0), int(total_steps)) / int(total_steps)
    return float(minimum) + (float(learning_rate) - float(minimum)) * (1.0 + math.cos(math.pi * fraction)) / 2.0


def _linear_warmup(learning_rate: Any, step: Any, warmup_steps: Any) -> float:
    if int(warmup_steps) <= 0:
        raise OptimizerError("OPT-002", "warmup_steps must be positive")
    return float(learning_rate) * min(1.0, max(0.0, int(step) / int(warmup_steps)))


def _trace_value(value: Any) -> Any:
    if isinstance(value, TensorValueRef):
        return value.metadata()
    if isinstance(value, list):
        return [_trace_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _trace_value(item) for key, item in value.items()}
    return value
