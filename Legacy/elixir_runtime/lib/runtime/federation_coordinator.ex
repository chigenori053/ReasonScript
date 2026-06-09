defmodule Runtime.FederationCoordinator do
  @moduledoc false

  use GenServer

  @protocol_version "REPLAY_PROTOCOL_V1"

  def start_link(arg \\ []) do
    GenServer.start_link(__MODULE__, arg, name: __MODULE__)
  end

  def protocol_version, do: @protocol_version

  def register_session(session_id, node_name, mir_program, opts \\ []) do
    GenServer.call(__MODULE__, {:register_session, session_id, node_name, mir_program, opts}, :infinity)
  end

  def session_node(session_id) do
    GenServer.call(__MODULE__, {:session_node, session_id})
  end

  def migrate_session(session_id, node_name) do
    GenServer.call(__MODULE__, {:migrate_session, session_id, node_name}, :infinity)
  end

  def note_node_down(node_name, remap_to) do
    GenServer.call(__MODULE__, {:node_down, node_name, remap_to}, :infinity)
  end

  def record_remote_worker(session_id, shard_id, node_name, pid) do
    GenServer.cast(__MODULE__, {:record_remote_worker, session_id, shard_id, node_name, pid})
  end

  def replicate_metadata(session_id, metadata) do
    GenServer.cast(__MODULE__, {:replicate_metadata, session_id, metadata})
  end

  def federate(group_id, session_ids, federation_edges \\ []) do
    GenServer.call(__MODULE__, {:federate, group_id, session_ids, federation_edges}, :infinity)
  end

  def federation(group_id) do
    GenServer.call(__MODULE__, {:federation, group_id})
  end

  def status do
    GenServer.call(__MODULE__, :status)
  end

  @impl true
  def init(_arg) do
    {:ok,
     %{
       sessions: %{},
       federation_dag: %{},
       remote_workers: %{},
       cluster_barriers: %{},
       provenance_roots: %{}
     }}
  end

  @impl true
  def handle_call({:register_session, session_id, node_name, mir_program, opts}, _from, state) do
    if Map.has_key?(state.sessions, session_id) do
      {:reply, {:error, :session_already_registered}, state}
    else
      session_meta = %{
        node: node_name,
        mir_program: mir_program,
        protocol_version: Keyword.get(opts, :protocol_version, @protocol_version),
        latest_checkpoint_root: nil,
        lineage_root_hash: nil,
        proof_barrier_state: :idle,
        shard_placement: %{}
      }

      {:reply, :ok, put_in(state, [:sessions, session_id], session_meta)}
    end
  end

  def handle_call({:session_node, session_id}, _from, state) do
    {:reply, get_in(state, [:sessions, session_id, :node]), state}
  end

  def handle_call({:migrate_session, session_id, node_name}, _from, state) do
    case get_in(state, [:sessions, session_id]) do
      nil ->
        {:reply, {:error, :unknown_session}, state}

      session ->
        updated =
          state
          |> put_in([:sessions, session_id, :node], node_name)
          |> put_in([:sessions, session_id, :shard_placement], Map.new(Map.keys(session.shard_placement), &{&1, node_name}))

        {:reply, :ok, updated}
    end
  end

  def handle_call({:node_down, node_name, remap_to}, _from, state) do
    updated =
      Enum.reduce(state.sessions, state, fn {session_id, session}, acc ->
        if session.node == node_name do
          acc
          |> put_in([:sessions, session_id, :node], remap_to)
          |> put_in([:sessions, session_id, :shard_placement], remap_shards(session.shard_placement, remap_to))
        else
          acc
        end
      end)

    {:reply, :ok, updated}
  end

  def handle_call({:federate, group_id, session_ids, federation_edges}, _from, state) do
    with {:ok, sessions} <- fetch_sessions(state.sessions, session_ids),
         :ok <- protocol_match?(sessions),
         :ok <- acyclic_federation?(session_ids, federation_edges) do
      federation = %{
        group_id: group_id,
        sessions: Enum.sort(session_ids),
        edges: federation_edges,
        protocol_version: @protocol_version
      }

      {:reply, {:ok, federation}, put_in(state, [:federation_dag, group_id], federation)}
    else
      {:error, reason} -> {:reply, {:error, reason}, state}
    end
  end

  def handle_call({:federation, group_id}, _from, state) do
    {:reply, Map.get(state.federation_dag, group_id), state}
  end

  def handle_call(:status, _from, state) do
    {:reply,
     %{
       sessions: Map.new(state.sessions, fn {id, meta} -> {id, meta.node} end),
       federation_dag: state.federation_dag,
       remote_workers: state.remote_workers,
       cluster_barriers: state.cluster_barriers,
       provenance_roots: state.provenance_roots,
       protocol_version: @protocol_version
     }, state}
  end

  @impl true
  def handle_cast({:record_remote_worker, session_id, shard_id, node_name, pid}, state) do
    state =
      state
      |> put_in([:remote_workers, shard_id], {node_name, pid})
      |> update_in([:sessions, session_id, :shard_placement], fn placement ->
        Map.put(placement || %{}, shard_id, node_name)
      end)

    {:noreply, state}
  end

  def handle_cast({:replicate_metadata, session_id, metadata}, state) do
    state =
      state
      |> update_in([:sessions, session_id], fn session -> Map.merge(session || %{}, metadata) end)
      |> put_in([:provenance_roots, session_id], metadata[:lineage_root_hash] || metadata["lineage_root_hash"])

    {:noreply, state}
  end

  defp fetch_sessions(all_sessions, session_ids) do
    sessions = Enum.map(session_ids, &Map.get(all_sessions, &1))
    if Enum.any?(sessions, &is_nil/1), do: {:error, :unknown_session}, else: {:ok, sessions}
  end

  defp protocol_match?(sessions) do
    versions = sessions |> Enum.map(& &1.protocol_version) |> Enum.uniq()
    if versions == [@protocol_version], do: :ok, else: {:error, :protocol_mismatch}
  end

  defp acyclic_federation?(session_ids, edges) do
    indegree = Map.new(session_ids, &{&1, 0})

    indegree =
      Enum.reduce(edges, indegree, fn {from, to}, acc ->
        if from == to, do: raise("federation cycle"), else: Map.update!(acc, to, &(&1 + 1))
      end)

    ready = indegree |> Enum.filter(fn {_id, degree} -> degree == 0 end) |> length()
    if ready > 0, do: :ok, else: {:error, :federation_cycle}
  rescue
    _ -> {:error, :federation_cycle}
  end

  defp remap_shards(placement, remap_to) do
    placement |> Map.keys() |> Map.new(&{&1, remap_to})
  end
end
