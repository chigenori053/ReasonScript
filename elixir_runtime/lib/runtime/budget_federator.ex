defmodule Runtime.BudgetFederator do
  @moduledoc false

  use GenServer

  @default_limit 2

  def start_link(arg \\ []) do
    GenServer.start_link(__MODULE__, arg, name: __MODULE__)
  end

  def register_unit(tenant, unit_id, budget) do
    GenServer.call(__MODULE__, {:register_unit, tenant, unit_id, budget}, :infinity)
  end

  def inspect_budget(tenant) do
    GenServer.call(__MODULE__, {:inspect, tenant})
  end

  @impl true
  def init(_arg) do
    {:ok, %{tenants: %{}}}
  end

  @impl true
  def handle_call({:register_unit, tenant, unit_id, budget}, _from, state) do
    entry = %{
      storage_cost: Map.get(budget, :storage_cost, 1),
      replay_cost: Map.get(budget, :replay_cost, 1),
      proof_reuse_value: Map.get(budget, :proof_reuse_value, 0),
      pedagogical_value: Map.get(budget, :pedagogical_value, 0)
    }

    tenant_state = Map.get(state.tenants, tenant, %{limit: @default_limit, units: %{}})
    units = Map.put(tenant_state.units, unit_id, entry)
    evicted = eviction_candidates(units, tenant_state.limit)
    active = Map.drop(units, evicted)
    next_tenant_state = %{tenant_state | units: active}

    {:reply, {:ok, %{evicted: evicted, active: Map.keys(active)}}, put_in(state, [:tenants, tenant], next_tenant_state)}
  end

  def handle_call({:inspect, tenant}, _from, state) do
    tenant_state = Map.get(state.tenants, tenant, %{limit: @default_limit, units: %{}})

    {:reply,
     %{
       limit: tenant_state.limit,
       active_units: Map.keys(tenant_state.units),
       eviction_order: ranked_units(tenant_state.units)
     }, state}
  end

  defp eviction_candidates(units, limit) when map_size(units) <= limit, do: []
  defp eviction_candidates(units, limit), do: ranked_units(units) |> Enum.drop(limit)

  defp ranked_units(units) do
    units
    |> Enum.map(fn {unit_id, budget} ->
      score = budget.proof_reuse_value + budget.pedagogical_value - budget.storage_cost - budget.replay_cost
      {unit_id, score}
    end)
    |> Enum.sort_by(fn {unit_id, score} -> {score, unit_id} end)
    |> Enum.map(&elem(&1, 0))
    |> Enum.reverse()
  end
end
