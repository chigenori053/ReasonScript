defmodule Runtime.DistributedProofBarrier do
  @moduledoc false

  use GenServer

  alias Runtime.RustVm

  def start_link(session_id) do
    GenServer.start_link(__MODULE__, session_id, name: Runtime.via({:proof_barrier, session_id}))
  end

  def proof_passed?(session_id, shard_id, worker_results) do
    GenServer.call(Runtime.via({:proof_barrier, session_id}), {:proof_passed?, shard_id, List.wrap(worker_results)}, :infinity)
  end

  @impl true
  def init(session_id) do
    {:ok, %{session_id: session_id, shard_status: %{}}}
  end

  @impl true
  def handle_call({:proof_passed?, shard_id, worker_results}, _from, state) do
    result =
      if Enum.all?(worker_results, fn result ->
           is_nil(result.proof_state) or RustVm.verify_proof(result.proof_state)
         end) do
        {:ok, :passed}
      else
        {:error, :proof_failed}
      end

    {:reply, result, put_in(state, [:shard_status, shard_id], result)}
  end
end
