defmodule ElixirRuntime do
  @moduledoc """
  Compatibility wrapper around the Runtime single-session orchestrator.
  """

  def start_session(session_id, mir_program, opts \\ []), do: Runtime.start_session(session_id, mir_program, opts)
  def resume_session(session_id, opts \\ []), do: Runtime.resume_session(session_id, opts)
  defdelegate execute(session_id), to: Runtime
  defdelegate rollback(session_id, checkpoint_id), to: Runtime
  defdelegate status(session_id), to: Runtime
  defdelegate cluster_status(), to: Runtime
  defdelegate federate_sessions(group_id, session_ids, federation_edges), to: Runtime
  defdelegate cluster_run(group_id), to: Runtime
  defdelegate fail_node(node_name, remap_to), to: Runtime
  defdelegate migrate_session(session_id, node_name), to: Runtime
  defdelegate persist_reason_unit(session_id, reason_unit), to: Runtime
  defdelegate import_reason_unit(session_id, unit_id), to: Runtime
  defdelegate reuse_proof_fragment(session_id, fragment_id), to: Runtime
  defdelegate memory_query(tenant, query), to: Runtime
  defdelegate memory_budget(tenant), to: Runtime
end
