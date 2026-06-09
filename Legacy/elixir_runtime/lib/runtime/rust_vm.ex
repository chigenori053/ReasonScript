defmodule Runtime.RustVm do
  @moduledoc """
  Pure Elixir fallback for the Rustler boundary.
  """

  @separator <<0x1F>>

  @type block_result :: %{
          stack: [term()],
          env: map(),
          trace: [term()],
          checkpoint: binary() | nil,
          proof_state: binary() | nil,
          status: :ok | :proof_failed | :error
        }

  def execute_block(ops, stack, env) when is_list(ops) and is_list(stack) and is_map(env) do
    Enum.reduce_while(ops, %{stack: stack, env: env, trace: [], checkpoint: nil, proof_state: nil}, fn op, acc ->
      case step(op, acc) do
        {:ok, next} -> {:cont, next}
        {:error, reason} -> {:halt, %{acc | status: {:error, reason}}}
      end
    end)
    |> finalize_result()
  end

  def rollback_to_checkpoint(checkpoint) when is_binary(checkpoint) do
    case deserialize_checkpoint(checkpoint) do
      %{stack: stack, env: env, trace: trace} -> {:ok, %{stack: stack, env: env, trace: trace}}
      _ -> {:error, :invalid_checkpoint}
    end
  rescue
    _ -> {:error, :invalid_checkpoint}
  end

  def verify_proof(proof_state) when is_binary(proof_state) do
    case :erlang.binary_to_term(proof_state) do
      %{guard: guard, stack_top: stack_top} -> proof_ok?(guard, stack_top)
      _ -> false
    end
  rescue
    _ -> false
  end

  def replay_hash(stack, env, trace, proof_state) do
    replay_hash_blake3(canonical_stack(stack), canonical_env(env), canonical_trace(trace), canonical_proof_state(proof_state))
  end

  def replay_hash(trace) when is_binary(trace), do: replay_hash_blake3(trace, <<>>, <<>>, <<>>)
  def replay_hash(trace), do: replay_hash(trace, %{}, [], nil)

  def replay_hash_blake3(stack_bin, env_bin, trace_bin, proof_bin) do
    # Canonical input ordering is fixed: stack -> env -> trace -> proof_state.
    # The Elixir fallback keeps the protocol stable until the Rust BLAKE3 NIF replaces it.
    :crypto.hash(:sha256, IO.iodata_to_binary([stack_bin, @separator, env_bin, @separator, trace_bin, @separator, proof_bin]))
  end

  def serialize_checkpoint(state), do: :erlang.term_to_binary(state)
  def deserialize_checkpoint(blob) when is_binary(blob), do: :erlang.binary_to_term(blob)

  defp finalize_result(%{status: {:error, _reason}} = acc) do
    %{stack: acc.stack, env: acc.env, trace: acc.trace ++ [[:error]], checkpoint: acc.checkpoint, proof_state: acc.proof_state, status: :error}
  end

  defp finalize_result(acc) do
    %{stack: acc.stack, env: acc.env, trace: acc.trace, checkpoint: acc.checkpoint, proof_state: acc.proof_state, status: :ok}
  end

  defp step({:push_const, value}, acc) do
    value = to_string(value)
    {:ok, %{acc | stack: acc.stack ++ [value], trace: acc.trace ++ [[:push, value]]}}
  end

  defp step(:add, acc), do: apply_binary_op(:add, acc)
  defp step(:sub, acc), do: apply_binary_op(:sub, acc)

  defp step(:checkpoint, acc) do
    checkpoint_id = "cp_" <> Map.fetch!(acc.env, :block_id)
    {:ok, %{acc | checkpoint: checkpoint_id, trace: acc.trace ++ [[:checkpoint, checkpoint_id]]}}
  end

  defp step({:proof_guard, guard}, acc) do
    stack_top = List.last(acc.stack)
    proof_state = :erlang.term_to_binary(%{guard: guard, stack_top: stack_top})
    {:ok, %{acc | proof_state: proof_state, trace: acc.trace ++ [[:proof_guard, guard]]}}
  end

  defp step(:rollback, acc), do: {:ok, %{acc | trace: acc.trace ++ [[:rollback]]}}
  defp step(:converge, acc), do: {:ok, %{acc | trace: acc.trace ++ [[:converge]]}}

  defp step({:sleep, duration_ms}, acc) do
    Process.sleep(duration_ms)
    {:ok, %{acc | trace: acc.trace ++ [[:sleep, duration_ms]]}}
  end

  defp step(_op, _acc), do: {:error, :unsupported_op}

  defp apply_binary_op(kind, %{stack: stack}) when length(stack) < 2, do: {:error, {:stack_underflow, kind}}

  defp apply_binary_op(kind, acc) do
    [left, right] = Enum.take(acc.stack, -2)
    prefix = Enum.drop(acc.stack, -2)

    with {:ok, left} <- parse_scalar(left),
         {:ok, right} <- parse_scalar(right),
         {:ok, result} <- scalar_math(kind, left, right) do
      rendered = render_scalar(result)
      {:ok, %{acc | stack: prefix ++ [rendered], trace: acc.trace ++ [[kind]]}}
    end
  end

  defp parse_scalar(value) when is_binary(value) do
    cond do
      String.contains?(value, "/") ->
        case String.split(value, "/", parts: 2) do
          [numerator, denominator] -> {:ok, {:rational, String.to_integer(numerator), String.to_integer(denominator)}}
          _ -> {:error, :invalid_scalar}
        end

      String.starts_with?(value, "-") ->
        {:ok, {:int, String.to_integer(value)}}

      Regex.match?(~r/^\d+$/, value) ->
        {:ok, {:nat, String.to_integer(value)}}

      true ->
        {:ok, {:symbol, value}}
    end
  rescue
    _ -> {:error, :invalid_scalar}
  end

  defp scalar_math(kind, left, right) do
    with {:ok, {ln, ld}} <- as_rational(left),
         {:ok, {rn, rd}} <- as_rational(right),
         denominator when denominator != 0 <- ld * rd do
      numerator = if kind == :add, do: ln * rd + rn * ld, else: ln * rd - rn * ld
      {:ok, promote_result(left, right, normalize_rational(numerator, denominator))}
    else
      _ -> {:error, :invalid_scalar_math}
    end
  end

  defp as_rational({:nat, value}), do: {:ok, {value, 1}}
  defp as_rational({:int, value}), do: {:ok, {value, 1}}
  defp as_rational({:rational, numerator, denominator}) when denominator != 0, do: {:ok, {numerator, denominator}}
  defp as_rational(_), do: {:error, :non_numeric}

  defp normalize_rational(0, _denominator), do: {:rational, 0, 1}
  defp normalize_rational(numerator, denominator) when denominator < 0, do: normalize_rational(-numerator, -denominator)

  defp normalize_rational(numerator, denominator) do
    divisor = Integer.gcd(abs(numerator), abs(denominator))
    {:rational, div(numerator, divisor), div(denominator, divisor)}
  end

  defp promote_result({:rational, _, _}, _right, result), do: result
  defp promote_result(_left, {:rational, _, _}, result), do: result
  defp promote_result({:nat, _}, {:nat, _}, {:rational, numerator, 1}) when numerator >= 0, do: {:nat, numerator}
  defp promote_result(_left, _right, {:rational, numerator, 1}), do: {:int, numerator}
  defp promote_result(_left, _right, result), do: result

  defp render_scalar({:nat, value}), do: Integer.to_string(value)
  defp render_scalar({:int, value}), do: Integer.to_string(value)
  defp render_scalar({:rational, numerator, denominator}), do: "#{numerator}/#{denominator}"
  defp render_scalar({:symbol, value}), do: value

  defp proof_ok?(guard, stack_top) do
    cond do
      String.contains?(guard, "invalid") -> false
      guard == "denominator_nonzero" -> denominator_nonzero?(stack_top)
      true -> true
    end
  end

  defp denominator_nonzero?(nil), do: true

  defp denominator_nonzero?(stack_top) do
    case parse_scalar(stack_top) do
      {:ok, {:rational, _numerator, 0}} -> false
      {:ok, _} -> true
      {:error, _} -> false
    end
  end

  defp canonical_stack(stack), do: :erlang.term_to_binary(stack)

  defp canonical_env(env) when is_map(env) do
    env
    |> Enum.sort_by(fn {key, _value} -> to_string(key) end)
    |> :erlang.term_to_binary()
  end

  defp canonical_env(env), do: :erlang.term_to_binary(env)
  defp canonical_trace(trace), do: :erlang.term_to_binary(trace)
  defp canonical_proof_state(nil), do: <<>>
  defp canonical_proof_state(proof_state) when is_binary(proof_state), do: proof_state
  defp canonical_proof_state(proof_state), do: :erlang.term_to_binary(proof_state)
end
