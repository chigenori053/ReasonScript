defmodule Runtime.ProofFragmentStore do
  @moduledoc false

  use GenServer

  def start_link(arg \\ []) do
    GenServer.start_link(__MODULE__, arg, name: __MODULE__)
  end

  def persist(node_name, attrs), do: GenServer.call(__MODULE__, {:persist, node_name, attrs}, :infinity)
  def fetch(fragment_id), do: GenServer.call(__MODULE__, {:fetch, fragment_id}, :infinity)

  @impl true
  def init(_arg) do
    {:ok, %{}}
  end

  @impl true
  def handle_call({:persist, node_name, attrs}, _from, state) do
    path = Runtime.ReasonUnitStore.memory_db_path(node_name)
    ensure_schema!(path)

    sql = """
    INSERT INTO proof_fragments(fragment_id, unit_id, proof_blob, proof_hash, reusable, created_at)
    VALUES (#{text(attrs.fragment_id)}, #{text(attrs.unit_id)}, #{blob(attrs.proof_blob)}, #{text(attrs.proof_hash)},
            #{boolean(attrs.reusable)}, #{integer(now_ms())})
    ON CONFLICT(fragment_id)
    DO UPDATE SET unit_id=excluded.unit_id, proof_blob=excluded.proof_blob, proof_hash=excluded.proof_hash,
                  reusable=excluded.reusable;
    """

    {:reply, exec(path, sql), Map.put(state, attrs.fragment_id, node_name)}
  end

  def handle_call({:fetch, fragment_id}, _from, state) do
    result =
      state
      |> Map.values()
      |> Enum.uniq()
      |> Enum.find_value({:error, :unknown_fragment}, fn node_name ->
        path = Runtime.ReasonUnitStore.memory_db_path(node_name)

        case query_rows(path, "SELECT fragment_id, unit_id, hex(proof_blob), proof_hash, reusable, created_at FROM proof_fragments WHERE fragment_id = #{text(fragment_id)} LIMIT 1;", ["fragment_id", "unit_id", "proof_blob", "proof_hash", "reusable", "created_at"]) do
          {:ok, [row | _]} ->
            {:ok,
             %{
               fragment_id: row["fragment_id"],
               unit_id: row["unit_id"],
               proof_blob: decode_blob(row["proof_blob"]),
               proof_hash: row["proof_hash"],
               reusable: row["reusable"] == "1",
               created_at: row["created_at"]
             }}

          _ ->
            nil
        end
      end)

    {:reply, result, state}
  end

  defp ensure_schema!(db_path) do
    sql = """
    CREATE TABLE IF NOT EXISTS proof_fragments (
      fragment_id TEXT PRIMARY KEY,
      unit_id TEXT NOT NULL,
      proof_blob BLOB NOT NULL,
      proof_hash TEXT NOT NULL,
      reusable BOOLEAN NOT NULL,
      created_at INTEGER NOT NULL
    );
    """

    case exec(db_path, sql) do
      :ok -> :ok
      {:error, reason} -> raise "sqlite exec failed: #{inspect(reason)}"
    end
  end

  defp exec(db_path, sql) do
    {output, code} = System.cmd(System.find_executable("sqlite3") || raise("sqlite3 not found"), [db_path, sql], stderr_to_stdout: true)
    if code == 0, do: :ok, else: {:error, String.trim(output)}
  end

  defp query_rows(db_path, sql, columns) do
    if File.exists?(db_path) do
      {output, code} = System.cmd(System.find_executable("sqlite3") || raise("sqlite3 not found"), ["-tabs", "-noheader", db_path, sql], stderr_to_stdout: true)

      cond do
        code == 0 and String.trim(output) == "" -> {:ok, []}
        code == 0 -> {:ok, output |> String.trim() |> String.split("\n", trim: true) |> Enum.map(fn line -> Enum.zip(columns, String.split(line, "\t")) |> Map.new() end)}
        true -> {:error, String.trim(output)}
      end
    else
      {:ok, []}
    end
  end

  defp integer(value), do: Integer.to_string(value)
  defp now_ms, do: System.system_time(:millisecond)
  defp text(value), do: "'#{String.replace(to_string(value), "'", "''")}'"
  defp boolean(true), do: "1"
  defp boolean(false), do: "0"
  defp blob(value), do: "X'#{Base.encode16(value, case: :upper)}'"
  defp decode_blob(hex), do: hex |> Base.decode16!(case: :mixed) |> :erlang.binary_to_term()
end
