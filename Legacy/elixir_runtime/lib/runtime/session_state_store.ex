defmodule Runtime.SessionStateStore do
  @moduledoc false

  use GenServer

  alias Runtime.CheckpointLedger
  alias Runtime.RustVm

  def start_link({session_id, mode}) do
    GenServer.start_link(__MODULE__, {session_id, mode}, name: Runtime.via({:state_store, session_id}))
  end

  def execution_input(session_id) do
    GenServer.call(Runtime.via({:state_store, session_id}), :execution_input)
  end

  def commit_result(session_id, block_id, worker_id, frontier_index, result) do
    GenServer.call(Runtime.via({:state_store, session_id}), {:commit_result, block_id, worker_id, frontier_index, result}, :infinity)
  end

  def rollback_to_checkpoint(session_id, checkpoint_id) do
    GenServer.call(Runtime.via({:state_store, session_id}), {:rollback, checkpoint_id}, :infinity)
  end

  def latest_checkpoint(session_id) do
    GenServer.call(Runtime.via({:state_store, session_id}), :latest_checkpoint)
  end

  def snapshot(session_id) do
    GenServer.call(Runtime.via({:state_store, session_id}), :snapshot)
  end

  def put_env(session_id, env) do
    GenServer.call(Runtime.via({:state_store, session_id}), {:put_env, env})
  end

  @impl true
  def init({session_id, mode}) do
    base = %{
      session_id: session_id,
      stack: [],
      env: %{},
      trace: [],
      current_state: "INIT",
      previous_state: nil,
      checkpoints: %{},
      latest_checkpoint_id: nil
    }

    case hydrate_state(base, mode) do
      {:ok, state} -> {:ok, state}
      {:error, reason} -> {:stop, reason}
    end
  end

  @impl true
  def handle_call(:execution_input, _from, state) do
    {:reply, %{stack: state.stack, env: state.env}, state}
  end

  def handle_call(:latest_checkpoint, _from, state) do
    {:reply, state.latest_checkpoint_id, state}
  end

  def handle_call(:snapshot, _from, state) do
    {:reply,
     %{
       stack: state.stack,
       env: state.env,
       trace: state.trace,
       current_state: state.current_state,
       previous_state: state.previous_state,
      checkpoints: Map.keys(state.checkpoints)
     }, state}
  end

  def handle_call({:put_env, env}, _from, state) do
    {:reply, :ok, %{state | env: env}}
  end

  def handle_call({:commit_result, block_id, worker_id, frontier_index, result}, _from, state) do
    state =
      state
      |> Map.put(:stack, result.stack)
      |> Map.put(:env, result.env)
      |> Map.put(:trace, state.trace ++ result.trace)
      |> Map.put(:current_state, current_state_from_stack(result.stack))

    {reply, state} =
      case result.checkpoint do
        nil ->
          {%{checkpoint_id: state.latest_checkpoint_id, snapshot: snapshot_reply(state)}, state}

        checkpoint_id ->
          {:ok, _hash} =
            CheckpointLedger.write_checkpoint(state.session_id, %{
              checkpoint_id: checkpoint_id,
              block_id: block_id,
              worker_id: worker_id,
              parent_worker_id: Map.get(state.env, :parent_worker_id),
              parent_session_id: Map.get(state.env, :parent_session_id),
              parent_checkpoint_id: state.latest_checkpoint_id,
              frontier_index: frontier_index,
              stack: result.stack,
              env: result.env,
              trace: result.trace,
              proof_state: result.proof_state
            })

          updated_state =
            state
            |> put_in([:checkpoints, checkpoint_id], true)
            |> Map.put(:previous_state, state.latest_checkpoint_id)
            |> Map.put(:latest_checkpoint_id, checkpoint_id)

          {%{checkpoint_id: checkpoint_id, snapshot: snapshot_reply(updated_state)}, updated_state}
      end

    {:reply, reply, state}
  end

  def handle_call({:rollback, checkpoint_id}, _from, state) do
    with {:ok, checkpoint} <- CheckpointLedger.latest_valid(state.session_id),
         true <- checkpoint["checkpoint_id"] == checkpoint_id,
         {:ok, restored} <-
           RustVm.rollback_to_checkpoint(
             RustVm.serialize_checkpoint(%{
               stack: checkpoint["stack"],
               env: checkpoint["env"],
               trace: checkpoint["trace"]
             })
           ) do
      new_state =
        state
        |> Map.put(:stack, restored.stack)
        |> Map.put(:env, restored.env)
        |> Map.put(:trace, state.trace ++ [[:rollback, checkpoint_id]])
        |> Map.put(:current_state, current_state_from_stack(restored.stack))
        |> Map.put(:previous_state, checkpoint_id)
        |> Map.put(:latest_checkpoint_id, checkpoint_id)

      {:reply, {:ok, snapshot_reply(new_state)}, new_state}
    else
      _ -> {:reply, {:error, :checkpoint_restore_mismatch}, state}
    end
  end

  defp hydrate_state(state, :fresh), do: {:ok, state}

  defp hydrate_state(state, :resume) do
    case CheckpointLedger.latest_valid(state.session_id) do
      {:ok, nil} ->
        {:ok, state}

      {:ok, checkpoint} ->
        {:ok,
         state
         |> Map.put(:stack, checkpoint["stack"])
         |> Map.put(:env, checkpoint["env"])
         |> Map.put(:trace, checkpoint["trace"])
         |> Map.put(:current_state, current_state_from_stack(checkpoint["stack"]))
         |> Map.put(:previous_state, checkpoint["parent_checkpoint_id"])
         |> Map.put(:latest_checkpoint_id, checkpoint["checkpoint_id"])
         |> put_in([:checkpoints, checkpoint["checkpoint_id"]], true)}

      {:error, reason} ->
        {:error, reason}
    end
  end

  defp snapshot_reply(state) do
    %{
      stack: state.stack,
      env: state.env,
      trace: state.trace,
      current_state: state.current_state,
      previous_state: checkpoint_state(state),
      checkpoints: Map.keys(state.checkpoints)
    }
  end

  defp checkpoint_state(%{latest_checkpoint_id: nil, previous_state: value}), do: value
  defp checkpoint_state(%{latest_checkpoint_id: checkpoint_id}), do: checkpoint_id

  defp current_state_from_stack([]), do: "INIT"
  defp current_state_from_stack(stack), do: List.last(stack)
end
