defmodule Runtime.OrchestratorServer do
  @moduledoc false

  use GenServer

  alias Runtime.CheckpointLedger
  alias Runtime.DistributedProofBarrier
  alias Runtime.FederationCoordinator
  alias Runtime.MirWorker
  alias Runtime.SchedulerGraphServer
  alias Runtime.SessionStateStore

  def start_link({session_id, mir_program, mode, node_name}) do
    GenServer.start_link(__MODULE__, {session_id, mir_program, mode, node_name}, name: Runtime.via({:orchestrator, session_id}))
  end

  @impl true
  def init({session_id, mir_program, mode, node_name}) do
    {mir_program, completed_nodes} =
      case mode do
        :resume ->
          {:ok, resumed} = CheckpointLedger.bootstrap_resume(session_id, node_name)
          {resumed.mir_program, resumed.frontier_index}

        :fresh ->
          {mir_program, 0}
      end

    scheduler_graph = Runtime.build_scheduler_graph(mir_program)
    nodes = scheduler_graph.frontier_dag |> Map.values() |> Enum.sort_by(&{&1.topological_rank, &1.id})

    {:ok,
     %{
       session_id: session_id,
       node_name: node_name,
       mir_program: mir_program,
       nodes: nodes,
       active_workers: %{},
       checkpoints: %{},
       status: :idle,
       reply_to: nil,
       current_node: nil,
       current_index: completed_nodes
     }}
  end

  @impl true
  def handle_call(:execute, from, %{status: :idle} = state) do
    {:noreply, spawn_next_node(%{state | status: :running, reply_to: from})}
  end

  def handle_call(:execute, _from, state), do: {:reply, {:error, {:invalid_status, state.status}}, state}

  def handle_call({:rollback, checkpoint_id}, _from, state) do
    case SessionStateStore.rollback_to_checkpoint(state.session_id, checkpoint_id) do
      {:ok, snapshot} -> {:reply, {:ok, snapshot}, %{state | status: :rolled_back}}
      {:error, reason} -> {:reply, {:error, reason}, %{state | status: :failed}}
    end
  end

  def handle_call(:status, _from, state) do
    {:reply,
     %{
       session_id: state.session_id,
       node_name: state.node_name,
       protocol_version: FederationCoordinator.protocol_version(),
       active_workers: state.active_workers,
       checkpoints: Map.keys(state.checkpoints),
       frontier: SchedulerGraphServer.status(state.session_id),
       status: state.status,
       current_block: state.current_node && state.current_node.id,
       lineage: unwrap_rows(CheckpointLedger.lineage(state.session_id)),
       causal_lineage: unwrap_rows(CheckpointLedger.causal_lineage(state.session_id)),
       federated_lineage: unwrap_rows(CheckpointLedger.federated_lineage(state.session_id))
     }, state}
  end

  @impl true
  def handle_info({:worker_result, worker_id, _block_id, result}, state) do
    Process.demonitor(worker_monitor!(state.active_workers, worker_id), [:flush])
    active_workers = Map.delete(state.active_workers, worker_id)
    node = state.current_node

    case maybe_commit_or_rollback(state.session_id, node, worker_id, state.current_index + 1, result) do
      {:ok, snapshot} ->
        :ok = SchedulerGraphServer.mark_committed(state.session_id, node.id)

        next_state =
          state
          |> Map.put(:active_workers, active_workers)
          |> Map.put(:checkpoints, Map.put(state.checkpoints, snapshot.previous_state || "", true))
          |> Map.put(:current_node, nil)
          |> Map.update!(:current_index, &(&1 + 1))

        {:noreply, advance_or_finish(next_state, snapshot, node)}

      {:rolled_back, _snapshot} ->
        :ok = SchedulerGraphServer.mark_failed(state.session_id, node.id)
        {:noreply, spawn_next_node(%{state | active_workers: active_workers, current_node: nil, status: :running})}

      {:error, reason} ->
        :ok = SchedulerGraphServer.mark_failed(state.session_id, node.id)
        {:noreply, finish(state, {:error, reason}, :failed, active_workers)}
    end
  end

  def handle_info({:DOWN, _ref, :process, pid, reason}, state) do
    case Enum.find(state.active_workers, fn {_worker_id, data} -> data.pid == pid end) do
      nil ->
        {:noreply, state}

      {worker_id, _data} when reason in [:normal, :shutdown] ->
        {:noreply, %{state | active_workers: Map.delete(state.active_workers, worker_id)}}

      {worker_id, _data} ->
        _ = CheckpointLedger.mark_worker(state.session_id, %{worker_id: worker_id, block_id: state.current_node.id, parent_worker_id: nil, checkpoint_id: SessionStateStore.latest_checkpoint(state.session_id), status: "restarting", updated_at: System.system_time(:millisecond)})
        if latest = SessionStateStore.latest_checkpoint(state.session_id), do: SessionStateStore.rollback_to_checkpoint(state.session_id, latest)
        {:noreply, spawn_current_node(%{state | active_workers: Map.delete(state.active_workers, worker_id), status: :running})}
    end
  end

  defp maybe_commit_or_rollback(session_id, %{explicit_rollback: true}, _worker_id, _index, _result) do
    case SessionStateStore.latest_checkpoint(session_id) do
      nil -> {:ok, SessionStateStore.snapshot(session_id)}
      checkpoint_id -> SessionStateStore.rollback_to_checkpoint(session_id, checkpoint_id)
    end
  end

  defp maybe_commit_or_rollback(session_id, node, worker_id, index, result) do
    with {:ok, _proof} <- DistributedProofBarrier.proof_passed?(session_id, node.shard_id, [result]),
         {:ok, commit_reply} <- normalize_commit(SessionStateStore.commit_result(session_id, node.id, worker_id, index, result)),
         :ok <- CheckpointLedger.update_session_progress(session_id, index, :running) do
      {:ok, commit_reply.snapshot}
    else
      {:error, :proof_failed} ->
        checkpoint_id = SessionStateStore.latest_checkpoint(session_id)
        if checkpoint_id, do: CheckpointLedger.update_session_progress(session_id, max(index - 1, 0), :rolled_back)
        if checkpoint_id, do: wrap_rollback(SessionStateStore.rollback_to_checkpoint(session_id, checkpoint_id)), else: {:error, :proof_failed}

      other ->
        other
    end
  end

  defp normalize_commit(%{snapshot: _snapshot} = reply), do: {:ok, reply}
  defp normalize_commit(other), do: {:error, other}

  defp advance_or_finish(state, snapshot, node) do
    if node && node.converges do
      :ok = CheckpointLedger.update_session_progress(state.session_id, state.current_index, :done)
      finish(state, {:ok, snapshot}, :done, state.active_workers)
    else
      spawn_next_node(%{state | status: :running})
    end
  end

  defp finish(state, reply, status, active_workers) do
    if state.reply_to, do: GenServer.reply(state.reply_to, reply)
    %{state | status: status, reply_to: nil, active_workers: active_workers, current_node: nil}
  end

  defp spawn_next_node(state) do
    case SchedulerGraphServer.next_runnable(state.session_id) do
      {:ok, node} -> spawn_current_node(%{state | current_node: node})
      :empty -> finish(state, {:ok, SessionStateStore.snapshot(state.session_id)}, :done, state.active_workers)
    end
  end

  defp spawn_current_node(%{current_node: nil} = state), do: state

  defp spawn_current_node(state) do
    %{stack: stack, env: env} = SessionStateStore.execution_input(state.session_id)
    worker_id = "#{state.current_node.id}_worker"
    parent_checkpoint_id = SessionStateStore.latest_checkpoint(state.session_id)

    _ = CheckpointLedger.mark_worker(state.session_id, %{worker_id: worker_id, block_id: state.current_node.id, parent_worker_id: nil, checkpoint_id: parent_checkpoint_id, status: "running", updated_at: System.system_time(:millisecond)})

    worker_spec = %{
      worker_id: worker_id,
      session_id: state.session_id,
      block_id: state.current_node.id,
      ops: state.current_node.ops,
      stack: stack,
      env: env |> Map.put(:block_id, state.current_node.id) |> Map.put(:node_name, state.node_name),
      trace: [],
      checkpoint_id: parent_checkpoint_id,
      proof_required: Map.get(state.current_node, :proof_required, false),
      orchestrator: self()
    }

    {:ok, pid} =
      :rpc.call(
        node(),
        DynamicSupervisor,
        :start_child,
        [Runtime.via({:worker_sup, state.session_id}), %{id: worker_id, start: {MirWorker, :start_link, [worker_spec]}, restart: :temporary}]
      )

    FederationCoordinator.record_remote_worker(state.session_id, state.current_node.shard_id, state.node_name, pid)

    ref = Process.monitor(pid)
    %{state | active_workers: Map.put(state.active_workers, worker_id, %{pid: pid, ref: ref})}
  end

  defp worker_monitor!(active_workers, worker_id), do: active_workers |> Map.fetch!(worker_id) |> Map.fetch!(:ref)
  defp unwrap_rows({:ok, rows}), do: rows
  defp unwrap_rows(_), do: []
  defp wrap_rollback({:ok, snapshot}), do: {:rolled_back, snapshot}
  defp wrap_rollback(other), do: other
end
