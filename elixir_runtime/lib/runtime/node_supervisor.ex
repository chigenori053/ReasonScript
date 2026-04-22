defmodule Runtime.NodeSupervisor do
  @moduledoc false

  use Supervisor

  def start_link(node_name) do
    Supervisor.start_link(__MODULE__, node_name, name: Runtime.via({:node_sup, node_name}))
  end

  def start_session(node_name, child_spec) do
    DynamicSupervisor.start_child(Runtime.via({:node_session_sup, node_name}), child_spec)
  end

  @impl true
  def init(node_name) do
    children = [
      {DynamicSupervisor, name: Runtime.via({:node_session_sup, node_name}), strategy: :one_for_one}
    ]

    Supervisor.init(children, strategy: :one_for_one)
  end
end
