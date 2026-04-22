defmodule RuntimeTest do
  use ExUnit.Case, async: false

  setup do
    unique = Integer.to_string(System.unique_integer([:positive]))
    session_a = "tenant_a/project_x/#{unique}_a"
    session_b = "tenant_a/project_x/#{unique}_b"
    session_c = "tenant_a/project_x/#{unique}_c"

    for {session, node} <- [{session_a, "node_a"}, {session_b, "node_b"}, {session_c, "node_b"}] do
      File.rm(Runtime.CheckpointLedger.db_path(session, node))
    end

    File.rm(Runtime.ReasonUnitStore.memory_db_path("node_a"))
    File.rm(Runtime.ReasonUnitStore.memory_db_path("node_b"))

    %{session_a: session_a, session_b: session_b, session_c: session_c}
  end

  test "multi-session isolation keeps rollback in session A from affecting session B", %{session_a: a, session_b: b} do
    assert {:ok, _} = Runtime.start_session(a, [{:push_const, "42"}, :checkpoint, {:push_const, "100"}, :converge], node: "node_a")
    assert {:ok, _} = Runtime.start_session(b, [{:push_const, "7"}, :checkpoint, {:push_const, "9"}, :converge], node: "node_b")

    assert {:ok, snapshot_a} = Runtime.execute(a)
    assert {:ok, snapshot_b} = Runtime.execute(b)
    assert snapshot_a.current_state == "100"
    assert snapshot_b.current_state == "9"

    assert {:ok, rolled_back} = Runtime.rollback(a, "cp_block_1")
    assert rolled_back.current_state == "42"

    still_b = Runtime.status(b)
    assert still_b.node_name == "node_b"
    assert still_b.status == :done
  end

  test "node crash failover remaps session and resumes on another node", %{session_a: a} do
    program = [{:push_const, "42"}, :checkpoint, {:sleep, 300}, {:push_const, "100"}, :converge]
    assert {:ok, _} = Runtime.start_session(a, program, node: "node_a")

    parent = self()
    spawned = spawn(fn -> send(parent, {:execute_result, Runtime.execute(a)}) end)
    wait_for_checkpoint(a, "cp_block_1")

    assert :ok = Runtime.fail_node("node_a", "node_b")
    wait_until_down(spawned)

    assert {:ok, _} = Runtime.resume_session(a, node: "node_b")
    assert {:ok, snapshot} = Runtime.execute(a)
    assert snapshot.current_state == "100"
    assert Runtime.status(a).node_name == "node_b"
  end

  test "cross-session federation runs deterministically across nodes", %{session_a: a, session_b: b} do
    assert {:ok, _} = Runtime.start_session(a, [{:push_const, "1"}, :checkpoint, :converge], node: "node_a")
    assert {:ok, _} = Runtime.start_session(b, [{:push_const, "2"}, :checkpoint, :converge], node: "node_b")

    assert {:ok, federation} = Runtime.federate_sessions("group_ab", [a, b], [{a, b}])
    assert federation.sessions == [a, b]

    assert {:ok, results} = Runtime.cluster_run("group_ab")
    assert Enum.map(results, &elem(&1, 0)) == [a, b]
  end

  test "proof federation rolls back affected subtree only", %{session_a: a, session_b: b, session_c: c} do
    assert {:ok, _} = Runtime.start_session(a, [{:push_const, "42"}, :checkpoint, :converge], node: "node_a")
    assert {:ok, _} = Runtime.start_session(b, [{:push_const, "1/0"}, {:proof_guard, "denominator_nonzero"}, :converge], node: "node_b")
    assert {:ok, _} = Runtime.start_session(c, [{:push_const, "9"}, :checkpoint, :converge], node: "node_b")

    assert {:ok, _} = Runtime.federate_sessions("group_proof", [a, b, c], [{a, b}])
    assert {:ok, results} = Runtime.cluster_run("group_proof")

    result_map = Map.new(results)
    assert match?({:ok, _}, result_map[a])
    assert match?({:error, :proof_failed}, result_map[b])
    assert match?({:ok, _}, result_map[c])

    {:ok, good_snapshot} = result_map[c]
    assert good_snapshot.current_state == "9"
  end

  test "protocol mismatch fails fast during federation", %{session_a: a, session_b: b} do
    assert {:ok, _} = Runtime.start_session(a, [{:push_const, "1"}, :checkpoint, :converge], node: "node_a")
    assert {:ok, _} = Runtime.start_session(b, [{:push_const, "2"}, :checkpoint, :converge], node: "node_b", protocol_version: "REPLAY_PROTOCOL_V2")

    assert {:error, :protocol_mismatch} = Runtime.federate_sessions("group_bad", [a, b], [])
  end

  test "cross-session reason unit reuse preserves source lineage", %{session_a: a, session_b: b} do
    assert {:ok, _} = Runtime.start_session(a, [{:push_const, "1"}, :checkpoint, :converge], node: "node_a")
    assert {:ok, _} = Runtime.start_session(b, [{:push_const, "2"}, :checkpoint, :converge], node: "node_b")

    assert {:ok, persisted} =
             Runtime.persist_reason_unit(a, %{
               semantic_payload: %{kind: :reason_unit, label: "session continuity"},
               research_provenance: [],
               budget: %{proof_reuse_value: 2}
             })

    assert {:ok, imported} = Runtime.import_reason_unit(b, persisted.unit_id)
    assert imported.unit_id == persisted.unit_id
    assert imported.source_tenant == "tenant_a"
  end

  test "proof fragment reuse is stored and reverified", %{session_a: a} do
    assert {:ok, _} = Runtime.start_session(a, [{:push_const, "1"}, :checkpoint, :converge], node: "node_a")

    assert {:ok, persisted} =
             Runtime.persist_reason_unit(a, %{
               semantic_payload: %{kind: :proof_unit, label: "deterministic transition"},
               proof_obligations: ["deterministic_transition", "denominator_nonzero"]
             })

    assert persisted.proof_fragment_id
    assert {:ok, reused} = Runtime.reuse_proof_fragment(a, persisted.proof_fragment_id)
    assert reused.verified
  end

  test "educational scaffold reuse can be queried by misconception cluster", %{session_a: a} do
    assert {:ok, _} = Runtime.start_session(a, [{:push_const, "1"}, :checkpoint, :converge], node: "node_a")

    assert {:ok, _} =
             Runtime.persist_reason_unit(a, %{
               semantic_payload: %{kind: :lesson, hint_chain: ["split fraction", "normalize sign"]},
               educational_annotations: %{misconception: "fraction_sign", learner_group: "algebra_i", scaffold_level: 2}
             })

    assert {:ok, query_result} = Runtime.memory_query("tenant_a", "fraction_sign")
    assert length(query_result.educational_matches) == 1
  end

  test "research provenance graph rejects cycles", %{session_a: a} do
    assert {:ok, _} = Runtime.start_session(a, [{:push_const, "1"}, :checkpoint, :converge], node: "node_a")

    assert {:ok, first} =
             Runtime.persist_reason_unit(a, %{
               semantic_payload: %{kind: :research, label: "root finding"}
             })

    assert {:ok, second} =
             Runtime.persist_reason_unit(a, %{
               semantic_payload: %{kind: :research, label: "validated finding"},
               research_provenance: [%{target_unit_id: first.unit_id, edge_type: "supports"}]
             })

    assert {:error, :provenance_cycle} =
             Runtime.persist_reason_unit(a, %{
               semantic_payload: %{kind: :research, label: "root finding"},
               research_provenance: [%{target_unit_id: second.unit_id, edge_type: "supports"}]
             })
  end

  test "memory budget evicts lower reuse value first", %{session_a: a} do
    assert {:ok, _} = Runtime.start_session(a, [{:push_const, "1"}, :checkpoint, :converge], node: "node_a")

    assert {:ok, low} =
             Runtime.persist_reason_unit(a, %{
               semantic_payload: %{kind: :memory, label: "low"},
               budget: %{storage_cost: 4, replay_cost: 3, proof_reuse_value: 0, pedagogical_value: 0}
             })

    assert {:ok, _mid} =
             Runtime.persist_reason_unit(a, %{
               semantic_payload: %{kind: :memory, label: "mid"},
               budget: %{storage_cost: 1, replay_cost: 1, proof_reuse_value: 2, pedagogical_value: 1}
             })

    assert {:ok, high} =
             Runtime.persist_reason_unit(a, %{
               semantic_payload: %{kind: :memory, label: "high"},
               budget: %{storage_cost: 1, replay_cost: 1, proof_reuse_value: 5, pedagogical_value: 3}
             })

    budget = Runtime.memory_budget("tenant_a")
    refute low.unit_id in budget.active_units
    assert high.unit_id in budget.active_units
  end

  defp wait_for_checkpoint(session_id, checkpoint_id, attempts \\ 40)
  defp wait_for_checkpoint(_session_id, _checkpoint_id, 0), do: flunk("checkpoint was not written")

  defp wait_for_checkpoint(session_id, checkpoint_id, attempts) do
    if checkpoint_id in Runtime.status(session_id).checkpoints do
      :ok
    else
      Process.sleep(20)
      wait_for_checkpoint(session_id, checkpoint_id, attempts - 1)
    end
  end

  defp wait_until_down(pid, attempts \\ 40)
  defp wait_until_down(_pid, 0), do: :ok

  defp wait_until_down(pid, attempts) do
    if Process.alive?(pid) do
      Process.sleep(20)
      wait_until_down(pid, attempts - 1)
    else
      :ok
    end
  end
end
