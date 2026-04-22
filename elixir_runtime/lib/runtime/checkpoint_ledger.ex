defmodule Runtime.CheckpointLedger do
  @moduledoc false

  use GenServer

  alias Runtime.FederationCoordinator
  alias Runtime.RustVm

  @busy_retry_attempts 5
  @busy_retry_delay 50

  def start_link({session_id, mir_program, mode, node_name}) do
    GenServer.start_link(__MODULE__, {session_id, mir_program, mode, node_name}, name: Runtime.via({:ledger, session_id}))
  end

  def db_path(session_id, node_name \\ nil)

  def db_path(session_id, nil) do
    [path | _] = Path.wildcard(Path.expand("../runtime_data/nodes/*/#{sanitize_session_id(session_id)}.sqlite3", File.cwd!())) ++ [db_path(session_id, "node_a")]
    path
  end

  def db_path(session_id, node_name) do
    root = Path.expand("../runtime_data/nodes/#{node_name}", File.cwd!())
    File.mkdir_p!(root)
    Path.join(root, "#{sanitize_session_id(session_id)}.sqlite3")
  end

  def transfer_session(session_id, from_node, to_node) do
    from = db_path(session_id, from_node)
    to = db_path(session_id, to_node)
    File.mkdir_p!(Path.dirname(to))
    File.cp!(from, to)
    :ok
  end

  def bootstrap_resume(session_id, node_name \\ nil) do
    path = db_path(session_id, node_name)

    with true <- File.exists?(path),
         {:ok, row} <- fetch_session_row(path),
         {:ok, latest} <- latest_valid_checkpoint(path, session_id) do
      {:ok,
       %{
         session_id: session_id,
         db_path: path,
         mir_program: decode_blob(row["mir_program_blob"]),
         frontier_index: String.to_integer(row["frontier_index"]),
         status: row["status"],
         latest_checkpoint: latest
       }}
    else
      false -> {:error, :session_not_found}
      {:error, reason} -> {:error, reason}
    end
  end

  def latest(session_id), do: GenServer.call(Runtime.via({:ledger, session_id}), :latest)
  def latest_valid(session_id), do: GenServer.call(Runtime.via({:ledger, session_id}), :latest_valid)
  def lineage(session_id), do: GenServer.call(Runtime.via({:ledger, session_id}), :lineage)
  def causal_lineage(session_id), do: GenServer.call(Runtime.via({:ledger, session_id}), :causal_lineage)
  def federated_lineage(session_id), do: GenServer.call(Runtime.via({:ledger, session_id}), :federated_lineage)
  def write_checkpoint(session_id, attrs), do: GenServer.call(Runtime.via({:ledger, session_id}), {:write_checkpoint, attrs}, :infinity)
  def mark_worker(session_id, attrs), do: GenServer.call(Runtime.via({:ledger, session_id}), {:mark_worker, attrs}, :infinity)
  def update_session_progress(session_id, frontier_index, status), do: GenServer.call(Runtime.via({:ledger, session_id}), {:update_session_progress, frontier_index, status}, :infinity)

  @impl true
  def init({session_id, mir_program, mode, node_name}) do
    path = db_path(session_id, node_name)
    ensure_schema!(path)

    with :ok <- ensure_session_row(path, session_id, mir_program, mode),
         {:ok, latest_checkpoint} <- latest_valid_checkpoint(path, session_id) do
      {:ok, %{session_id: session_id, node_name: node_name, db_path: path, latest_checkpoint: latest_checkpoint && latest_checkpoint["checkpoint_id"]}}
    else
      {:error, reason} -> {:stop, reason}
    end
  end

  @impl true
  def handle_call(:latest, _from, state), do: {:reply, state.latest_checkpoint, state}
  def handle_call(:latest_valid, _from, state), do: {:reply, latest_valid_checkpoint(state.db_path, state.session_id), state}
  def handle_call(:lineage, _from, state), do: {:reply, query_rows(state.db_path, "SELECT worker_id, block_id, parent_worker_id, checkpoint_id, status, updated_at FROM lineage WHERE session_id = #{text(state.session_id)} ORDER BY updated_at ASC;", ["worker_id", "block_id", "parent_worker_id", "checkpoint_id", "status", "updated_at"]), state}
  def handle_call(:causal_lineage, _from, state), do: {:reply, query_rows(state.db_path, "SELECT node_id, parent_node_id, shard_id, replay_hash, status, updated_at FROM causal_lineage WHERE session_id = #{text(state.session_id)} ORDER BY updated_at ASC, node_id ASC;", ["node_id", "parent_node_id", "shard_id", "replay_hash", "status", "updated_at"]), state}
  def handle_call(:federated_lineage, _from, state), do: {:reply, query_rows(state.db_path, "SELECT session_id, node_name, shard_id, parent_session_id, replay_hash, protocol_version, status, updated_at FROM federated_lineage WHERE session_id = #{text(state.session_id)} ORDER BY updated_at ASC;", ["session_id", "node_name", "shard_id", "parent_session_id", "replay_hash", "protocol_version", "status", "updated_at"]), state}

  def handle_call({:mark_worker, attrs}, _from, state) do
    sql = """
    INSERT INTO lineage(session_id, worker_id, block_id, parent_worker_id, checkpoint_id, status, updated_at)
    VALUES (#{text(state.session_id)}, #{text(attrs.worker_id)}, #{text(attrs.block_id)}, #{nullable_text(attrs.parent_worker_id)},
            #{nullable_text(attrs.checkpoint_id)}, #{text(attrs.status)}, #{integer(attrs.updated_at)})
    ON CONFLICT(session_id, worker_id, block_id)
    DO UPDATE SET parent_worker_id=excluded.parent_worker_id,
                  checkpoint_id=excluded.checkpoint_id,
                  status=excluded.status,
                  updated_at=excluded.updated_at;
    """

    {:reply, exec(state.db_path, sql), state}
  end

  def handle_call({:update_session_progress, frontier_index, status}, _from, state) do
    sql = """
    UPDATE sessions
    SET frontier_index = #{integer(frontier_index)},
        status = #{text(to_string(status))},
        updated_at = #{integer(now_ms())}
    WHERE session_id = #{text(state.session_id)};
    """

    {:reply, exec(state.db_path, sql), state}
  end

  def handle_call({:write_checkpoint, attrs}, _from, state) do
    replay_hash = RustVm.replay_hash(attrs.stack, attrs.env, attrs.trace, attrs.proof_state)
    replay_hash_hex = Base.encode16(replay_hash, case: :lower)
    protocol_version = FederationCoordinator.protocol_version()

    sql = """
    BEGIN IMMEDIATE;
    INSERT INTO checkpoints(session_id, checkpoint_id, block_id, stack_blob, env_blob, trace_blob, replay_hash,
                            parent_checkpoint_id, worker_id, created_at)
    VALUES (#{text(state.session_id)}, #{text(attrs.checkpoint_id)}, #{text(attrs.block_id)},
            #{blob(encode_blob(attrs.stack))}, #{blob(encode_blob(attrs.env))}, #{blob(encode_blob(attrs.trace))},
            #{text(replay_hash_hex)}, #{nullable_text(attrs.parent_checkpoint_id)}, #{text(attrs.worker_id)}, #{integer(now_ms())})
    ON CONFLICT(session_id, checkpoint_id)
    DO UPDATE SET block_id=excluded.block_id, stack_blob=excluded.stack_blob, env_blob=excluded.env_blob,
                  trace_blob=excluded.trace_blob, replay_hash=excluded.replay_hash,
                  parent_checkpoint_id=excluded.parent_checkpoint_id, worker_id=excluded.worker_id, created_at=excluded.created_at;
    INSERT INTO lineage(session_id, worker_id, block_id, parent_worker_id, checkpoint_id, status, updated_at)
    VALUES (#{text(state.session_id)}, #{text(attrs.worker_id)}, #{text(attrs.block_id)}, #{nullable_text(attrs.parent_worker_id)},
            #{text(attrs.checkpoint_id)}, 'committed', #{integer(now_ms())})
    ON CONFLICT(session_id, worker_id, block_id)
    DO UPDATE SET checkpoint_id=excluded.checkpoint_id, status='committed', updated_at=excluded.updated_at;
    INSERT INTO causal_lineage(session_id, node_id, parent_node_id, shard_id, replay_hash, status, updated_at)
    VALUES (#{text(state.session_id)}, #{text(attrs.block_id)}, #{nullable_text(attrs.parent_checkpoint_id)},
            #{text(attrs.block_id)}, #{text(replay_hash_hex)}, 'committed', #{integer(now_ms())})
    ON CONFLICT(session_id, node_id, shard_id)
    DO UPDATE SET parent_node_id=excluded.parent_node_id, replay_hash=excluded.replay_hash, status='committed', updated_at=excluded.updated_at;
    INSERT INTO federated_lineage(session_id, node_name, shard_id, parent_session_id, replay_hash, protocol_version, status, updated_at)
    VALUES (#{text(state.session_id)}, #{text(state.node_name)}, #{text(attrs.block_id)}, #{nullable_text(attrs.parent_session_id)},
            #{text(replay_hash_hex)}, #{text(protocol_version)}, 'committed', #{integer(now_ms())})
    ON CONFLICT(session_id, node_name, shard_id)
    DO UPDATE SET parent_session_id=excluded.parent_session_id, replay_hash=excluded.replay_hash,
                  protocol_version=excluded.protocol_version, status='committed', updated_at=excluded.updated_at;
    UPDATE sessions
    SET frontier_index = #{integer(attrs.frontier_index)}, status = 'running', updated_at = #{integer(now_ms())}
    WHERE session_id = #{text(state.session_id)};
    COMMIT;
    """

    case exec(state.db_path, sql) do
      :ok ->
        FederationCoordinator.replicate_metadata(state.session_id, %{
          latest_checkpoint_root: attrs.checkpoint_id,
          replay_protocol_version: protocol_version,
          shard_placement: %{attrs.block_id => state.node_name},
          lineage_root_hash: replay_hash_hex,
          proof_barrier_state: :passed
        })

        {:reply, {:ok, replay_hash}, %{state | latest_checkpoint: attrs.checkpoint_id}}

      {:error, reason} ->
        {:reply, {:error, reason}, state}
    end
  end

  defp ensure_schema!(db_path) do
    sql = """
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;
    CREATE TABLE IF NOT EXISTS checkpoints (
      session_id TEXT NOT NULL,
      checkpoint_id TEXT NOT NULL,
      block_id TEXT NOT NULL,
      stack_blob BLOB NOT NULL,
      env_blob BLOB NOT NULL,
      trace_blob BLOB NOT NULL,
      replay_hash TEXT NOT NULL,
      parent_checkpoint_id TEXT,
      worker_id TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      PRIMARY KEY (session_id, checkpoint_id)
    );
    CREATE TABLE IF NOT EXISTS lineage (
      session_id TEXT NOT NULL,
      worker_id TEXT NOT NULL,
      block_id TEXT NOT NULL,
      parent_worker_id TEXT,
      checkpoint_id TEXT,
      status TEXT NOT NULL,
      updated_at INTEGER NOT NULL,
      PRIMARY KEY (session_id, worker_id, block_id)
    );
    CREATE TABLE IF NOT EXISTS causal_lineage (
      session_id TEXT NOT NULL,
      node_id TEXT NOT NULL,
      parent_node_id TEXT,
      shard_id TEXT NOT NULL,
      replay_hash TEXT NOT NULL,
      status TEXT NOT NULL,
      updated_at INTEGER NOT NULL,
      PRIMARY KEY (session_id, node_id, shard_id)
    );
    CREATE TABLE IF NOT EXISTS federated_lineage (
      session_id TEXT NOT NULL,
      node_name TEXT NOT NULL,
      shard_id TEXT NOT NULL,
      parent_session_id TEXT,
      replay_hash TEXT NOT NULL,
      protocol_version TEXT NOT NULL,
      status TEXT NOT NULL,
      updated_at INTEGER NOT NULL,
      PRIMARY KEY (session_id, node_name, shard_id)
    );
    CREATE TABLE IF NOT EXISTS sessions (
      session_id TEXT PRIMARY KEY,
      mir_program_blob BLOB NOT NULL,
      frontier_index INTEGER NOT NULL,
      status TEXT NOT NULL,
      updated_at INTEGER NOT NULL
    );
    """

    :ok = exec!(db_path, sql)
  end

  defp ensure_session_row(db_path, session_id, mir_program, :fresh) do
    sql = """
    INSERT INTO sessions(session_id, mir_program_blob, frontier_index, status, updated_at)
    VALUES (#{text(session_id)}, #{blob(encode_blob(mir_program))}, 0, 'idle', #{integer(now_ms())})
    ON CONFLICT(session_id)
    DO UPDATE SET mir_program_blob=excluded.mir_program_blob, frontier_index=0, status='idle', updated_at=excluded.updated_at;
    """

    exec(db_path, sql)
  end

  defp ensure_session_row(db_path, _session_id, _mir_program, :resume) do
    if match?({:ok, _}, fetch_session_row(db_path)), do: :ok, else: {:error, :session_not_found}
  end

  defp fetch_session_row(db_path) do
    case query_rows(db_path, "SELECT hex(mir_program_blob), frontier_index, status FROM sessions LIMIT 1;", ["mir_program_blob", "frontier_index", "status"]) do
      {:ok, [row | _]} -> {:ok, row}
      {:ok, []} -> {:error, :session_not_found}
      {:error, reason} -> {:error, reason}
    end
  end

  defp latest_valid_checkpoint(db_path, session_id) do
    sql = """
    SELECT checkpoint_id, block_id, hex(stack_blob), hex(env_blob), hex(trace_blob), replay_hash,
           parent_checkpoint_id, worker_id, created_at
    FROM checkpoints WHERE session_id = #{text(session_id)} ORDER BY created_at DESC LIMIT 1;
    """

    with {:ok, [row | _]} <- query_rows(db_path, sql, ["checkpoint_id", "block_id", "stack_blob", "env_blob", "trace_blob", "replay_hash", "parent_checkpoint_id", "worker_id", "created_at"]),
         :ok <- verify_checkpoint_row(row) do
      {:ok, Map.merge(row, %{"stack" => decode_blob(row["stack_blob"]), "env" => decode_blob(row["env_blob"]), "trace" => decode_blob(row["trace_blob"])})}
    else
      {:ok, []} -> {:ok, nil}
      {:error, reason} -> {:error, reason}
    end
  end

  defp verify_checkpoint_row(row) do
    hash = RustVm.replay_hash(decode_blob(row["stack_blob"]), decode_blob(row["env_blob"]), decode_blob(row["trace_blob"]), nil) |> Base.encode16(case: :lower)
    if hash == row["replay_hash"], do: :ok, else: {:error, :replay_hash_mismatch}
  end

  defp exec!(db_path, sql) do
    case exec(db_path, sql) do
      :ok -> :ok
      {:error, reason} -> raise "sqlite exec failed: #{inspect(reason)}"
    end
  end

  defp exec(db_path, sql, attempt \\ 1)

  defp exec(db_path, sql, attempt) do
    {output, code} = System.cmd(sqlite3_path(), [db_path, sql], stderr_to_stdout: true, env: [{"SQLITE_BUSY_TIMEOUT", "1000"}])

    cond do
      code == 0 -> :ok
      attempt < @busy_retry_attempts and (String.contains?(output, "locked") or String.contains?(output, "busy")) ->
        Process.sleep(@busy_retry_delay * attempt)
        exec(db_path, sql, attempt + 1)
      true -> {:error, String.trim(output)}
    end
  end

  defp query_rows(db_path, sql, columns) do
    {output, code} = System.cmd(sqlite3_path(), ["-tabs", "-noheader", db_path, sql], stderr_to_stdout: true)

    cond do
      code == 0 and String.trim(output) == "" -> {:ok, []}
      code == 0 ->
        {:ok, output |> String.trim() |> String.split("\n", trim: true) |> Enum.map(fn line -> Enum.zip(columns, String.split(line, "\t")) |> Map.new() end)}
      true -> {:error, String.trim(output)}
    end
  end

  defp sqlite3_path, do: System.find_executable("sqlite3") || raise("sqlite3 not found")
  defp now_ms, do: System.system_time(:millisecond)
  defp integer(value), do: Integer.to_string(value)
  defp text(value), do: "'#{String.replace(to_string(value), "'", "''")}'"
  defp nullable_text(nil), do: "NULL"
  defp nullable_text(value), do: text(value)
  defp blob(value), do: "X'#{Base.encode16(value, case: :upper)}'"
  defp encode_blob(term), do: :erlang.term_to_binary(term)
  defp decode_blob(hex), do: hex |> Base.decode16!(case: :mixed) |> :erlang.binary_to_term()
  defp sanitize_session_id(session_id), do: String.replace(session_id, "/", "__")
end
