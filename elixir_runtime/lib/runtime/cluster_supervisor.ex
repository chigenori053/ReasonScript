defmodule Runtime.ClusterSupervisor do
  @moduledoc false

  use Supervisor

  def start_link(arg \\ []) do
    Supervisor.start_link(__MODULE__, arg, name: __MODULE__)
  end

  def ensure_node(node_name) do
    case GenServer.whereis(Runtime.via({:node_sup, node_name})) do
      nil ->
        DynamicSupervisor.start_child(Runtime.ClusterNodeSupervisor, {Runtime.NodeSupervisor, node_name})

      pid ->
        {:ok, pid}
    end
  end

  @impl true
  def init(_arg) do
    children = [
      Runtime.FederationCoordinator,
      Runtime.MemoryFederationSupervisor,
      {DynamicSupervisor, name: Runtime.ClusterNodeSupervisor, strategy: :one_for_one}
    ]

    Supervisor.init(children, strategy: :one_for_one)
  end
end
