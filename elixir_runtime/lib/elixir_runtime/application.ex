defmodule ElixirRuntime.Application do
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      {Registry, keys: :unique, name: Runtime.Registry},
      Runtime.ClusterSupervisor
    ]

    Supervisor.start_link(children, strategy: :one_for_one, name: ElixirRuntime.Supervisor)
  end
end
