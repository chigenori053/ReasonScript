defmodule ElixirRuntimeTest do
  use ExUnit.Case
  doctest ElixirRuntime

  test "greets the world" do
    assert ElixirRuntime.hello() == :world
  end
end
