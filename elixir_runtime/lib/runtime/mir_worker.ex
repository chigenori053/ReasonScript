defmodule Runtime.MirWorker do
  @moduledoc false

  use GenServer

  alias Runtime.RustVm

  def start_link(worker_spec) do
    GenServer.start_link(__MODULE__, worker_spec)
  end

  @impl true
  def init(worker_spec) do
    {:ok, worker_spec, {:continue, :execute}}
  end

  @impl true
  def handle_continue(:execute, state) do
    result = RustVm.execute_block(state.ops, state.stack, state.env)
    send(state.orchestrator, {:worker_result, state.worker_id, state.block_id, result})
    {:stop, :normal, state}
  end
end
