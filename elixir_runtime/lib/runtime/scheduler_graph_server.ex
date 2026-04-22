defmodule Runtime.SchedulerGraphServer do
  @moduledoc false

  use GenServer

  def start_link({session_id, scheduler_graph, mode}) do
    GenServer.start_link(__MODULE__, {session_id, scheduler_graph, mode}, name: Runtime.via({:scheduler_graph, session_id}))
  end

  def next_runnable(session_id), do: GenServer.call(Runtime.via({:scheduler_graph, session_id}), :next_runnable)
  def mark_committed(session_id, node_id), do: GenServer.call(Runtime.via({:scheduler_graph, session_id}), {:mark_committed, node_id})
  def mark_failed(session_id, node_id), do: GenServer.call(Runtime.via({:scheduler_graph, session_id}), {:mark_failed, node_id})
  def status(session_id), do: GenServer.call(Runtime.via({:scheduler_graph, session_id}), :status)

  @impl true
  def init({session_id, scheduler_graph, _mode}) do
    {:ok,
     %{
       session_id: session_id,
       frontier_dag: scheduler_graph.frontier_dag,
       active_shards: %{},
       rollback_forest: scheduler_graph.rollback_forest,
       converge_frontier: scheduler_graph.converge_frontier,
       budget_graph: scheduler_graph.budget_graph,
       completed: MapSet.new(),
       invalidated: MapSet.new()
     }}
  end

  @impl true
  def handle_call(:next_runnable, _from, state) do
    runnable =
      state.frontier_dag
      |> Map.values()
      |> Enum.filter(&runnable?(&1, state))
      |> Enum.sort_by(&{&1.topological_rank, &1.id})

    case runnable do
      [node | _] ->
        active_shards = Map.update(state.active_shards, node.shard_id, [node.id], &[node.id | &1])
        {:reply, {:ok, node}, %{state | active_shards: active_shards}}

      [] ->
        {:reply, :empty, state}
    end
  end

  def handle_call({:mark_committed, node_id}, _from, state) do
    node = Map.fetch!(state.frontier_dag, node_id)
    {:reply, :ok, %{state | completed: MapSet.put(state.completed, node_id), active_shards: remove_active(state.active_shards, node)}}
  end

  def handle_call({:mark_failed, node_id}, _from, state) do
    node = Map.fetch!(state.frontier_dag, node_id)
    pruned = descendants(node_id, state.rollback_forest) |> MapSet.new() |> MapSet.put(node_id)
    {:reply, :ok, %{state | invalidated: MapSet.union(state.invalidated, pruned), active_shards: remove_active(state.active_shards, node)}}
  end

  def handle_call(:status, _from, state) do
    ordered =
      state.frontier_dag
      |> Map.values()
      |> Enum.sort_by(&{&1.topological_rank, &1.id})
      |> Enum.map(& &1.id)

    {:reply,
     %{
       frontier_dag: ordered,
       active_shards: state.active_shards,
       rollback_forest: state.rollback_forest,
       converge_frontier: state.converge_frontier,
       budget_graph: state.budget_graph,
       completed: Enum.filter(ordered, &MapSet.member?(state.completed, &1)),
       invalidated: Enum.filter(ordered, &MapSet.member?(state.invalidated, &1))
     }, state}
  end

  defp runnable?(node, state) do
    not MapSet.member?(state.completed, node.id) and
      not MapSet.member?(state.invalidated, node.id) and
      Enum.all?(node.depends_on, &MapSet.member?(state.completed, &1)) and
      Map.get(state.budget_graph, node.id, true) and
      (is_nil(node.rollback_parent) or MapSet.member?(state.completed, node.rollback_parent))
  end

  defp descendants(node_id, forest) do
    direct = Map.get(forest, node_id, [])
    direct ++ Enum.flat_map(direct, &descendants(&1, forest))
  end

  defp remove_active(active_shards, node) do
    case Map.get(active_shards, node.shard_id, []) |> Enum.reject(&(&1 == node.id)) do
      [] -> Map.delete(active_shards, node.shard_id)
      remaining -> Map.put(active_shards, node.shard_id, remaining)
    end
  end
end
