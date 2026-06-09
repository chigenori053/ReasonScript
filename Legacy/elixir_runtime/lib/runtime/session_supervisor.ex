defmodule Runtime.SessionSupervisor do
  @moduledoc false

  use Supervisor

  def start_link({session_id, mir_program, mode, node_name}) do
    Supervisor.start_link(__MODULE__, {session_id, mir_program, mode, node_name}, name: Runtime.via({:session_supervisor, session_id}))
  end

  @impl true
  def init({session_id, mir_program, mode, node_name}) do
    scheduler_graph = Runtime.build_scheduler_graph(mir_program)

    children = [
      {Runtime.CheckpointLedger, {session_id, mir_program, mode, node_name}},
      {Runtime.SessionStateStore, {session_id, mode}},
      {Runtime.DistributedProofBarrier, session_id},
      {Runtime.SchedulerGraphServer, {session_id, scheduler_graph, mode}},
      {DynamicSupervisor, name: Runtime.via({:worker_sup, session_id}), strategy: :one_for_one},
      {Runtime.OrchestratorServer, {session_id, mir_program, mode, node_name}}
    ]

    Supervisor.init(children, strategy: :rest_for_one)
  end
end
