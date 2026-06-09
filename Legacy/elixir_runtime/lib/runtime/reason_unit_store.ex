defmodule Runtime.ReasonUnitStore do
  @moduledoc false

  use GenServer

  alias Runtime.RustVm
  def start_link(arg \\ []) do
    GenServer.start_link(__MODULE__, arg, name: __MODULE__)
  end

  def memory_db_path(node_name) do
    root = Path.expand("../runtime_data/nodes/#{node_name}", File.cwd!())
    File.mkdir_p!(root)
    Path.join(root, "memoryspace.sqlite3")
  end

  def persist(node_name, attrs), do: GenServer.call(__MODULE__, {:persist, node_name, attrs}, :infinity)
  def fetch(unit_id), do: GenServer.call(__MODULE__, {:fetch, unit_id}, :infinity)
  def query(tenant, query), do: GenServer.call(__MODULE__, {:query, tenant, query}, :infinity)
  def all_units, do: GenServer.call(__MODULE__, :all_units, :infinity)

  @impl true
  def init(_arg) do
    {:ok, %{}}
  end

  @impl true
  def handle_call({:persist, node_name, attrs}, _from, state) do
    path = memory_db_path(node_name)
    ensure_schema!(path)

    sql = """
    BEGIN IMMEDIATE;
    INSERT INTO reason_units(unit_id, tenant, project, semantic_blob, semantic_hash, protocol_version, schema_version, created_at)
    VALUES (#{text(attrs.unit_id)}, #{text(attrs.tenant)}, #{text(attrs.project)}, #{blob(attrs.semantic_blob)},
            #{text(attrs.semantic_hash)}, #{text(attrs.protocol_version)}, #{text(attrs.schema_version)}, #{integer(now_ms())})
    ON CONFLICT(unit_id)
    DO UPDATE SET tenant=excluded.tenant, project=excluded.project, semantic_blob=excluded.semantic_blob,
                  semantic_hash=excluded.semantic_hash, protocol_version=excluded.protocol_version,
                  schema_version=excluded.schema_version;
    COMMIT;
    """

    {:reply, exec(path, sql), Map.put(state, attrs.unit_id, node_name)}
  end

  def handle_call({:fetch, unit_id}, _from, state) do
    result =
      case Map.get(state, unit_id) do
        nil ->
          {:error, :unknown_unit}

        node_name ->
          path = memory_db_path(node_name)

          case query_rows(path, "SELECT unit_id, tenant, project, hex(semantic_blob), semantic_hash, protocol_version, schema_version, created_at FROM reason_units WHERE unit_id = #{text(unit_id)} LIMIT 1;", ["unit_id", "tenant", "project", "semantic_blob", "semantic_hash", "protocol_version", "schema_version", "created_at"]) do
            {:ok, [row | _]} ->
              {:ok,
               %{
                 unit_id: row["unit_id"],
                 tenant: row["tenant"],
                 project: row["project"],
                 semantic_payload: decode_blob(row["semantic_blob"]),
                 semantic_hash: row["semantic_hash"],
                 protocol_version: row["protocol_version"],
                 schema_version: row["schema_version"],
                 created_at: row["created_at"]
               }}

            _ ->
              {:error, :unknown_unit}
          end
      end

    {:reply, result, state}
  end

  def handle_call({:query, tenant, query}, _from, state) do
    normalized = String.downcase(to_string(query))

    rows =
      state
      |> Map.values()
      |> Enum.uniq()
      |> Enum.flat_map(fn node_name ->
        path = memory_db_path(node_name)

        case query_rows(path, "SELECT unit_id, tenant, project, hex(semantic_blob), semantic_hash, protocol_version, schema_version, created_at FROM reason_units WHERE tenant = #{text(tenant)};", ["unit_id", "tenant", "project", "semantic_blob", "semantic_hash", "protocol_version", "schema_version", "created_at"]) do
          {:ok, result_rows} -> result_rows
          _ -> []
        end
      end)
      |> Enum.map(fn row ->
        payload = decode_blob(row["semantic_blob"])

        %{
          unit_id: row["unit_id"],
          tenant: row["tenant"],
          project: row["project"],
          semantic_payload: payload,
          semantic_hash: row["semantic_hash"],
          protocol_version: row["protocol_version"],
          schema_version: row["schema_version"],
          created_at: row["created_at"]
        }
      end)
      |> Enum.filter(fn unit ->
        normalized == "" or String.contains?(String.downcase(inspect(unit.semantic_payload)), normalized)
      end)

    {:reply, {:ok, rows}, state}
  end

  def handle_call(:all_units, _from, state) do
    {:reply, {:ok, state}, state}
  end

  defp ensure_schema!(db_path) do
    sql = """
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;
    CREATE TABLE IF NOT EXISTS reason_units (
      unit_id TEXT PRIMARY KEY,
      tenant TEXT NOT NULL,
      project TEXT NOT NULL,
      semantic_blob BLOB NOT NULL,
      semantic_hash TEXT NOT NULL,
      protocol_version TEXT NOT NULL,
      schema_version TEXT NOT NULL,
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS educational_traces (
      trace_id TEXT PRIMARY KEY,
      learner_group TEXT NOT NULL,
      unit_id TEXT NOT NULL,
      pedagogy_tag TEXT NOT NULL,
      trace_blob BLOB NOT NULL,
      created_at INTEGER NOT NULL
    );
    """

    case exec(db_path, sql) do
      :ok -> :ok
      {:error, reason} -> raise "sqlite exec failed: #{inspect(reason)}"
    end
  end

  def insert_educational_trace(node_name, trace_attrs) do
    path = memory_db_path(node_name)
    ensure_schema!(path)

    sql = """
    INSERT INTO educational_traces(trace_id, learner_group, unit_id, pedagogy_tag, trace_blob, created_at)
    VALUES (#{text(trace_attrs.trace_id)}, #{text(trace_attrs.learner_group)}, #{text(trace_attrs.unit_id)},
            #{text(trace_attrs.pedagogy_tag)}, #{blob(trace_attrs.trace_blob)}, #{integer(now_ms())})
    ON CONFLICT(trace_id)
    DO UPDATE SET learner_group=excluded.learner_group, unit_id=excluded.unit_id,
                  pedagogy_tag=excluded.pedagogy_tag, trace_blob=excluded.trace_blob;
    """

    exec(path, sql)
  end

  def educational_traces(tenant, pedagogy_tag) do
    with {:ok, nodes} <- all_units() do
      rows =
        nodes
        |> Map.values()
        |> Enum.uniq()
        |> Enum.flat_map(fn node_name ->
          path = memory_db_path(node_name)

          case query_rows(path, """
               SELECT e.trace_id, e.learner_group, e.unit_id, e.pedagogy_tag, hex(e.trace_blob)
               FROM educational_traces e
               JOIN reason_units r ON r.unit_id = e.unit_id
               WHERE e.pedagogy_tag = #{text(pedagogy_tag)} AND r.tenant = #{text(tenant)};
               """, ["trace_id", "learner_group", "unit_id", "pedagogy_tag", "trace_blob"]) do
            {:ok, result_rows} -> result_rows
            _ -> []
          end
        end)
        |> Enum.map(fn row ->
          %{trace_id: row["trace_id"], learner_group: row["learner_group"], unit_id: row["unit_id"], pedagogy_tag: row["pedagogy_tag"], trace: decode_blob(row["trace_blob"])}
        end)

      {:ok, rows}
    end
  end

  def canonical_identity(payload) do
    canonical = canonicalize(payload)
    binary = :erlang.term_to_binary(canonical)
    hash = RustVm.replay_hash_blake3(binary, <<>>, <<>>, <<>>) |> Base.encode16(case: :lower)
    {hash, binary}
  end

  defp canonicalize(map) when is_map(map) do
    map
    |> Enum.map(fn {key, value} -> {to_string(key), canonicalize(value)} end)
    |> Enum.sort_by(&elem(&1, 0))
  end

  defp canonicalize(list) when is_list(list), do: Enum.map(list, &canonicalize/1)
  defp canonicalize(other), do: other

  defp exec(db_path, sql) do
    {output, code} = System.cmd(sqlite3_path(), [db_path, sql], stderr_to_stdout: true, env: [{"SQLITE_BUSY_TIMEOUT", "1000"}])
    if code == 0, do: :ok, else: {:error, String.trim(output)}
  end

  defp query_rows(db_path, sql, columns) do
    if File.exists?(db_path) do
      {output, code} = System.cmd(sqlite3_path(), ["-tabs", "-noheader", db_path, sql], stderr_to_stdout: true)

      cond do
        code == 0 and String.trim(output) == "" -> {:ok, []}
        code == 0 -> {:ok, output |> String.trim() |> String.split("\n", trim: true) |> Enum.map(fn line -> Enum.zip(columns, String.split(line, "\t")) |> Map.new() end)}
        true -> {:error, String.trim(output)}
      end
    else
      {:ok, []}
    end
  end

  defp sqlite3_path, do: System.find_executable("sqlite3") || raise("sqlite3 not found")
  defp now_ms, do: System.system_time(:millisecond)
  defp integer(value), do: Integer.to_string(value)
  defp text(value), do: "'#{String.replace(to_string(value), "'", "''")}'"
  defp blob(value), do: "X'#{Base.encode16(value, case: :upper)}'"
  defp decode_blob(hex), do: hex |> Base.decode16!(case: :mixed) |> :erlang.binary_to_term()
end
