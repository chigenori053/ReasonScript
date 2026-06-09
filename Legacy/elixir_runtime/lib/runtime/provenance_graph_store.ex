defmodule Runtime.ProvenanceGraphStore do
  @moduledoc false

  use GenServer

  def start_link(arg \\ []) do
    GenServer.start_link(__MODULE__, arg, name: __MODULE__)
  end

  def add_edge(node_name, source_unit_id, target_unit_id, edge_type) do
    GenServer.call(__MODULE__, {:add_edge, node_name, source_unit_id, target_unit_id, edge_type}, :infinity)
  end

  def edges, do: GenServer.call(__MODULE__, :edges)

  @impl true
  def init(_arg) do
    {:ok, %{edges: %{}}}
  end

  @impl true
  def handle_call({:add_edge, node_name, source_unit_id, target_unit_id, edge_type}, _from, state) do
    if path_exists?(state.edges, target_unit_id, source_unit_id) or source_unit_id == target_unit_id do
      {:reply, {:error, :provenance_cycle}, state}
    else
      path = Runtime.ReasonUnitStore.memory_db_path(node_name)
      ensure_schema!(path)

      sql = """
      INSERT INTO memory_provenance(source_unit_id, target_unit_id, edge_type, updated_at)
      VALUES (#{text(source_unit_id)}, #{text(target_unit_id)}, #{text(edge_type)}, #{integer(now_ms())});
      """

      case exec(path, sql) do
        :ok ->
          edges = Map.update(state.edges, source_unit_id, [{target_unit_id, edge_type}], &[{target_unit_id, edge_type} | &1])
          {:reply, :ok, %{state | edges: edges}}

        {:error, reason} ->
          {:reply, {:error, reason}, state}
      end
    end
  end

  def handle_call(:edges, _from, state) do
    {:reply, state.edges, state}
  end

  defp path_exists?(edges, current, goal, visited \\ MapSet.new())
  defp path_exists?(_edges, current, goal, _visited) when current == goal, do: true

  defp path_exists?(edges, current, goal, visited) do
    if MapSet.member?(visited, current) do
      false
    else
      visited = MapSet.put(visited, current)

      edges
      |> Map.get(current, [])
      |> Enum.any?(fn {next, _edge_type} -> path_exists?(edges, next, goal, visited) end)
    end
  end

  defp ensure_schema!(db_path) do
    sql = """
    CREATE TABLE IF NOT EXISTS memory_provenance (
      source_unit_id TEXT NOT NULL,
      target_unit_id TEXT NOT NULL,
      edge_type TEXT NOT NULL,
      updated_at INTEGER NOT NULL
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

  defp text(value), do: "'#{String.replace(to_string(value), "'", "''")}'"
  defp integer(value), do: Integer.to_string(value)
  defp now_ms, do: System.system_time(:millisecond)
end
