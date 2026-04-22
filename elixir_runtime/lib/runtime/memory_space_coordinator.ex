defmodule Runtime.MemorySpaceCoordinator do
  @moduledoc false

  use GenServer

  alias Runtime.BudgetFederator
  alias Runtime.FederationCoordinator
  alias Runtime.ProofFragmentStore
  alias Runtime.ProvenanceGraphStore
  alias Runtime.ReasonUnitStore
  alias Runtime.RustVm

  @memory_schema "MEMORY_SCHEMA_V1"
  @serializer_schema "SERIALIZER_SCHEMA_V1"

  def start_link(arg \\ []) do
    GenServer.start_link(__MODULE__, arg, name: __MODULE__)
  end

  def persist_reason_unit(session_id, node_name, reason_unit) do
    GenServer.call(__MODULE__, {:persist_reason_unit, session_id, node_name, reason_unit}, :infinity)
  end

  def import_reason_unit(session_id, node_name, unit_id) do
    GenServer.call(__MODULE__, {:import_reason_unit, session_id, node_name, unit_id}, :infinity)
  end

  def reuse_proof_fragment(session_id, fragment_id) do
    GenServer.call(__MODULE__, {:reuse_proof_fragment, session_id, fragment_id}, :infinity)
  end

  def memory_query(tenant, query) do
    GenServer.call(__MODULE__, {:memory_query, tenant, query}, :infinity)
  end

  def memory_budget(tenant) do
    GenServer.call(__MODULE__, {:memory_budget, tenant})
  end

  @impl true
  def init(_arg) do
    {:ok,
     %{
       memory_roots: %{},
       active_reason_units: %{},
       proof_fragments: %{},
       provenance_roots: %{},
       budget_state: %{},
       schema_versions: %{}
     }}
  end

  @impl true
  def handle_call({:persist_reason_unit, session_id, node_name, reason_unit}, _from, state) do
    with {:ok, context} <- session_context(session_id, reason_unit),
         :ok <- schema_match?(reason_unit),
         {semantic_hash, semantic_blob} <- ReasonUnitStore.canonical_identity(context.semantic_payload),
         unit_id <- semantic_hash,
         :ok <- ReasonUnitStore.persist(node_name, %{
           unit_id: unit_id,
           tenant: context.tenant,
           project: context.project,
           semantic_blob: semantic_blob,
           semantic_hash: semantic_hash,
           protocol_version: FederationCoordinator.protocol_version(),
           schema_version: @memory_schema
         }),
         :ok <- maybe_store_educational_trace(node_name, unit_id, context),
         :ok <- maybe_store_provenance(node_name, unit_id, context),
         {:ok, proof_fragment} <- maybe_store_proof_fragment(node_name, unit_id, context),
         {:ok, budget_result} <- BudgetFederator.register_unit(context.tenant, unit_id, context.budget) do
      next_state =
        state
        |> put_in([:active_reason_units, unit_id], node_name)
        |> update_in([:memory_roots, context.tenant], fn roots -> Enum.uniq([unit_id | List.wrap(roots)]) end)
        |> put_in([:schema_versions, unit_id], %{
          protocol_version: FederationCoordinator.protocol_version(),
          memory_schema: @memory_schema,
          serializer_schema: @serializer_schema
        })
        |> put_in([:budget_state, context.tenant], budget_result)
        |> maybe_track_fragment(proof_fragment)
        |> maybe_prune_evicted(context.tenant, budget_result.evicted)

      reply = %{
        unit_id: unit_id,
        semantic_hash: semantic_hash,
        protocol_version: FederationCoordinator.protocol_version(),
        schema_version: @memory_schema,
        proof_fragment_id: proof_fragment && proof_fragment.fragment_id,
        evicted: budget_result.evicted
      }

      {:reply, {:ok, reply}, next_state}
    else
      {:error, reason} -> {:reply, {:error, reason}, state}
    end
  end

  def handle_call({:import_reason_unit, session_id, _node_name, unit_id}, _from, state) do
    with {:ok, %{tenant: tenant}} <- ReasonUnitStore.fetch(unit_id),
         {:ok, session_context} <- session_context(session_id, %{}),
         :ok <- ensure_same_tenant?(tenant, session_context.tenant) do
      imported = %{unit_id: unit_id, source_tenant: tenant, imported_into: session_id, proof_fragment_refs: fragment_refs_for_unit(state, unit_id)}
      {:reply, {:ok, imported}, state}
    else
      {:error, reason} -> {:reply, {:error, reason}, state}
    end
  end

  def handle_call({:reuse_proof_fragment, _session_id, fragment_id}, _from, state) do
    with {:ok, fragment} <- ProofFragmentStore.fetch(fragment_id),
         true <- fragment.reusable or {:error, :fragment_not_reusable},
         true <- reverify_fragment(fragment) or {:error, :proof_reverification_failed} do
      {:reply, {:ok, %{fragment_id: fragment_id, verified: true, unit_id: fragment.unit_id}}, state}
    else
      {:error, reason} -> {:reply, {:error, reason}, state}
      false -> {:reply, {:error, :proof_reverification_failed}, state}
    end
  end

  def handle_call({:memory_query, tenant, query}, _from, state) do
    with {:ok, units} <- ReasonUnitStore.query(tenant, query),
         {:ok, traces} <- educational_trace_matches(tenant, query) do
      active = MapSet.new(Map.keys(state.active_reason_units))

      {:reply,
       {:ok,
        %{
          units: Enum.filter(units, &MapSet.member?(active, &1.unit_id)),
          educational_matches: traces
        }}, state}
    end
  end

  def handle_call({:memory_budget, tenant}, _from, state) do
    budget = BudgetFederator.inspect_budget(tenant)
    {:reply, Map.merge(budget, %{state: Map.get(state.budget_state, tenant, %{evicted: [], active: []})}), state}
  end

  defp session_context(session_id, reason_unit) do
    [tenant, project | _rest] = String.split(session_id, "/", parts: 3) ++ ["default_project"]

    {:ok,
     %{
       tenant: Map.get(reason_unit, :tenant, tenant),
       project: Map.get(reason_unit, :project, project),
       semantic_payload: Map.get(reason_unit, :semantic_payload, reason_unit),
       proof_obligations: Map.get(reason_unit, :proof_obligations, []),
       educational_annotations: Map.get(reason_unit, :educational_annotations, %{}),
       research_provenance: Map.get(reason_unit, :research_provenance, []),
       budget: Map.get(reason_unit, :budget, %{})
     }}
  end

  defp schema_match?(reason_unit) do
    protocol = Map.get(reason_unit, :protocol_version, FederationCoordinator.protocol_version())
    memory_schema = Map.get(reason_unit, :memory_schema, @memory_schema)
    serializer_schema = Map.get(reason_unit, :serializer_schema, @serializer_schema)

    if protocol == FederationCoordinator.protocol_version() and memory_schema == @memory_schema and serializer_schema == @serializer_schema do
      :ok
    else
      {:error, :schema_protocol_mismatch}
    end
  end

  defp maybe_store_provenance(_node_name, _unit_id, %{research_provenance: []}), do: :ok

  defp maybe_store_provenance(node_name, unit_id, %{research_provenance: edges}) do
    Enum.reduce_while(edges, :ok, fn edge, _acc ->
      target = Map.get(edge, :target_unit_id) || Map.get(edge, "target_unit_id")
      type = Map.get(edge, :edge_type) || Map.get(edge, "edge_type") || "derived_from"

      case ProvenanceGraphStore.add_edge(node_name, unit_id, target, type) do
        :ok -> {:cont, :ok}
        {:error, reason} -> {:halt, {:error, reason}}
      end
    end)
  end

  defp maybe_store_educational_trace(_node_name, _unit_id, %{educational_annotations: annotations}) when map_size(annotations) == 0, do: :ok

  defp maybe_store_educational_trace(node_name, unit_id, %{educational_annotations: annotations}) do
    pedagogy_tag = Map.get(annotations, :misconception, Map.get(annotations, :mastery_tag, "general"))
    learner_group = Map.get(annotations, :learner_group, "default")
    trace_id = trace_hash(unit_id, pedagogy_tag)

    ReasonUnitStore.insert_educational_trace(node_name, %{
      trace_id: trace_id,
      learner_group: learner_group,
      unit_id: unit_id,
      pedagogy_tag: to_string(pedagogy_tag),
      trace_blob: :erlang.term_to_binary(annotations)
    })
  end

  defp maybe_store_proof_fragment(_node_name, _unit_id, %{proof_obligations: []}), do: {:ok, nil}

  defp maybe_store_proof_fragment(node_name, unit_id, %{proof_obligations: obligations}) do
    canonical = obligations |> Enum.sort() |> :erlang.term_to_binary()
    fragment_hash = RustVm.replay_hash_blake3(canonical, <<>>, <<>>, <<>>) |> Base.encode16(case: :lower)
    fragment_id = "frag_" <> fragment_hash

    with :ok <- ProofFragmentStore.persist(node_name, %{
           fragment_id: fragment_id,
           unit_id: unit_id,
           proof_blob: canonical,
           proof_hash: fragment_hash,
           reusable: true
         }) do
      {:ok, %{fragment_id: fragment_id, unit_id: unit_id, obligations: obligations}}
    end
  end

  defp educational_trace_matches(tenant, query) do
    pedagogy_tag = to_string(query)
    ReasonUnitStore.educational_traces(tenant, pedagogy_tag)
  end

  defp reverify_fragment(fragment) do
    obligations = :erlang.term_to_binary(fragment.proof_blob)
    recomputed = RustVm.replay_hash_blake3(obligations, <<>>, <<>>, <<>>) |> Base.encode16(case: :lower)
    recomputed == fragment.proof_hash
  end

  defp ensure_same_tenant?(tenant, tenant), do: :ok
  defp ensure_same_tenant?(_source, _target), do: {:error, :tenant_isolation_violation}

  defp maybe_track_fragment(state, nil), do: state

  defp maybe_track_fragment(state, fragment) do
    put_in(state, [:proof_fragments, fragment.fragment_id], fragment)
  end

  defp maybe_prune_evicted(state, _tenant, []), do: state

  defp maybe_prune_evicted(state, tenant, evicted) do
    roots = Map.get(state.memory_roots, tenant, []) |> Enum.reject(&(&1 in evicted))

    state
    |> put_in([:memory_roots, tenant], roots)
    |> Map.update!(:active_reason_units, &Map.drop(&1, evicted))
  end

  defp fragment_refs_for_unit(state, unit_id) do
    state.proof_fragments
    |> Enum.filter(fn {_fragment_id, fragment} -> fragment.unit_id == unit_id end)
    |> Enum.map(&elem(&1, 0))
  end

  defp trace_hash(unit_id, pedagogy_tag) do
    RustVm.replay_hash_blake3(unit_id, pedagogy_tag, <<>>, <<>>) |> Base.encode16(case: :lower)
  end
end
