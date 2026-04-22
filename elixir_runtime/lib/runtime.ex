defmodule Runtime do
  @moduledoc """
  Multi-session cluster-aware reasoning runtime API.
  """

  alias Runtime.CheckpointLedger
  alias Runtime.FederationCoordinator
  alias Runtime.MemorySpaceCoordinator
  alias Runtime.NodeSupervisor

  @default_node "node_a"

  @type session_id :: binary()
  @type mir_op ::
          {:push_const, term()}
          | {:proof_guard, binary()}
          | {:sleep, non_neg_integer()}
          | :add
          | :sub
          | :checkpoint
          | :rollback
          | :converge

  @type mir_program :: [mir_op()] | %{nodes: [map()]}

  def start_session(session_id, mir_program, opts \\ []) when is_binary(session_id) do
    node_name = Keyword.get(opts, :node, @default_node)
    :ok = FederationCoordinator.register_session(session_id, node_name, mir_program, opts)
    {:ok, _node_sup} = Runtime.ClusterSupervisor.ensure_node(node_name)
    NodeSupervisor.start_session(node_name, {Runtime.SessionSupervisor, {session_id, mir_program, :fresh, node_name}})
    |> normalize_start()
  end

  def resume_session(session_id, opts \\ []) when is_binary(session_id) do
    node_name =
      Keyword.get_lazy(opts, :node, fn ->
        FederationCoordinator.session_node(session_id) || @default_node
      end)

    with {:ok, resumed} <- CheckpointLedger.bootstrap_resume(session_id, node_name),
         {:ok, _node_sup} <- Runtime.ClusterSupervisor.ensure_node(node_name) do
      NodeSupervisor.start_session(node_name, {Runtime.SessionSupervisor, {session_id, resumed.mir_program, :resume, node_name}})
      |> normalize_start()
    end
  end

  def execute(session_id), do: GenServer.call(via({:orchestrator, session_id}), :execute, :infinity)
  def rollback(session_id, checkpoint_id), do: GenServer.call(via({:orchestrator, session_id}), {:rollback, checkpoint_id}, :infinity)
  def status(session_id), do: GenServer.call(via({:orchestrator, session_id}), :status, :infinity)
  def cluster_status, do: FederationCoordinator.status()
  def persist_reason_unit(session_id, reason_unit), do: MemorySpaceCoordinator.persist_reason_unit(session_id, FederationCoordinator.session_node(session_id) || @default_node, reason_unit)
  def import_reason_unit(session_id, unit_id), do: MemorySpaceCoordinator.import_reason_unit(session_id, FederationCoordinator.session_node(session_id) || @default_node, unit_id)
  def reuse_proof_fragment(session_id, fragment_id), do: MemorySpaceCoordinator.reuse_proof_fragment(session_id, fragment_id)
  def memory_query(tenant, query), do: MemorySpaceCoordinator.memory_query(tenant, query)
  def memory_budget(tenant), do: MemorySpaceCoordinator.memory_budget(tenant)

  def federate_sessions(group_id, session_ids, federation_edges \\ []) do
    FederationCoordinator.federate(group_id, session_ids, federation_edges)
  end

  def cluster_run(group_id) do
    with %{sessions: sessions, edges: edges} <- FederationCoordinator.federation(group_id) do
      ordered = topological_session_order(sessions, edges)

      results =
        Enum.map(ordered, fn session_id ->
          {session_id, execute(session_id)}
        end)

      {:ok, results}
    else
      nil -> {:error, :unknown_federation}
      {:error, reason} -> {:error, reason}
    end
  end

  def fail_node(node_name, remap_to) do
    old_sessions =
      FederationCoordinator.status().sessions
      |> Enum.filter(fn {_session_id, node} -> node == node_name end)
      |> Enum.map(&elem(&1, 0))

    Enum.each(old_sessions, fn session_id ->
      CheckpointLedger.transfer_session(session_id, node_name, remap_to)
    end)

    case GenServer.whereis(via({:node_sup, node_name})) do
      nil -> :ok
      pid -> DynamicSupervisor.terminate_child(Runtime.ClusterNodeSupervisor, pid)
    end

    FederationCoordinator.note_node_down(node_name, remap_to)
  end

  def migrate_session(session_id, node_name) do
    from = FederationCoordinator.session_node(session_id)
    if from, do: CheckpointLedger.transfer_session(session_id, from, node_name)
    FederationCoordinator.migrate_session(session_id, node_name)
  end

  def via(key), do: {:via, Registry, {Runtime.Registry, key}}

  def build_scheduler_graph(%{nodes: nodes}) do
    sorted =
      nodes
      |> topological_sort()
      |> Enum.with_index(1)
      |> Enum.map(fn {node, rank} ->
        node
        |> Map.put_new(:shard_id, node.id)
        |> Map.put_new(:depends_on, [])
        |> Map.put_new(:rollback_parent, List.first(Map.get(node, :depends_on, [])))
        |> Map.put_new(:budgeted_by, nil)
        |> Map.put_new(:converges, false)
        |> Map.put(:topological_rank, rank)
      end)

    %{
      frontier_dag: Map.new(sorted, &{&1.id, &1}),
      rollback_forest:
        Enum.reduce(sorted, %{}, fn node, acc ->
          case node.rollback_parent do
            nil -> acc
            parent -> Map.update(acc, parent, [node.id], &[node.id | &1])
          end
        end),
      converge_frontier: sorted |> Enum.filter(& &1.converges) |> Enum.map(& &1.id),
      budget_graph: Map.new(sorted, &{&1.id, true})
    }
  end

  def build_scheduler_graph(mir_program) when is_list(mir_program) do
    blocks = partition_mir_program(mir_program)

    nodes =
      blocks
      |> Enum.with_index()
      |> Enum.map(fn {block, index} ->
        parent_id = if index == 0, do: nil, else: Enum.at(blocks, index - 1).id

        %{
          id: block.id,
          shard_id: block.id,
          ops: block.ops,
          depends_on: if(parent_id, do: [parent_id], else: []),
          rollback_parent: parent_id,
          budgeted_by: nil,
          converges: block.converges
        }
      end)

    build_scheduler_graph(%{nodes: nodes})
  end

  def partition_mir_program(mir_program) do
    mir_program
    |> Enum.reduce({[], []}, fn op, {blocks, current} ->
      next = current ++ [op]
      if boundary_op?(op), do: {blocks ++ [build_block(next, length(blocks) + 1)], []}, else: {blocks, next}
    end)
    |> finalize_blocks()
  end

  defp finalize_blocks({blocks, []}), do: blocks
  defp finalize_blocks({blocks, trailing}), do: blocks ++ [build_block(trailing, length(blocks) + 1)]

  defp build_block(ops, index) do
    %{
      id: "block_#{index}",
      shard_id: "block_#{index}",
      ops: ops,
      proof_required: Enum.any?(ops, &proof_op?/1),
      explicit_rollback: Enum.any?(ops, &(&1 == :rollback)),
      converges: Enum.any?(ops, &(&1 == :converge))
    }
  end

  defp boundary_op?(:checkpoint), do: true
  defp boundary_op?(:rollback), do: true
  defp boundary_op?(:converge), do: true
  defp boundary_op?({:proof_guard, _}), do: true
  defp boundary_op?(_), do: false

  defp proof_op?({:proof_guard, _}), do: true
  defp proof_op?(_), do: false

  defp topological_sort(nodes) do
    nodes_by_id = Map.new(nodes, &{&1.id, &1})
    indegree = Map.new(nodes, fn node -> {node.id, length(Map.get(node, :depends_on, []))} end)

    children =
      Enum.reduce(nodes, %{}, fn node, acc ->
        Enum.reduce(Map.get(node, :depends_on, []), acc, fn parent, map ->
          Map.update(map, parent, [node.id], &[node.id | &1])
        end)
      end)

    do_topological_sort(nodes_by_id, indegree, children, [])
  end

  defp do_topological_sort(nodes_by_id, indegree, children, acc) do
    completed_ids = MapSet.new(Enum.map(acc, & &1.id))

    ready =
      indegree
      |> Enum.filter(fn {id, degree} -> degree == 0 and not MapSet.member?(completed_ids, id) end)
      |> Enum.map(&elem(&1, 0))
      |> Enum.sort()

    case ready do
      [] ->
        if map_size(nodes_by_id) == length(acc), do: acc, else: raise("frontier DAG cycle")

      [next | _] ->
        next_node = Map.fetch!(nodes_by_id, next)

        next_indegree =
          Enum.reduce(Map.get(children, next, []), Map.put(indegree, next, -1), fn child, map ->
            Map.update!(map, child, &(&1 - 1))
          end)

        do_topological_sort(nodes_by_id, next_indegree, children, acc ++ [next_node])
    end
  end

  defp topological_session_order(session_ids, edges) do
    nodes = Enum.map(session_ids, &%{id: &1, depends_on: incoming(&1, edges)})
    topological_sort(nodes) |> Enum.map(& &1.id)
  end

  defp incoming(session_id, edges) do
    edges
    |> Enum.filter(fn {_from, to} -> to == session_id end)
    |> Enum.map(&elem(&1, 0))
  end

  defp normalize_start({:ok, pid}), do: {:ok, pid}
  defp normalize_start({:error, {:already_started, pid}}), do: {:ok, pid}
  defp normalize_start(other), do: other
end
