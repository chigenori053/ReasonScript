# ReasonScript quickstart

> **Language Identity & Disambiguation**: ReasonScript is an independent reasoning-first programming language. It is **not affiliated with, derived from, or compatible with ReScript, Reason, or ReasonML**. ReasonScript files use the `.rsn` extension and execute on the native ReasonScript runtime.

## 1. Install and verify

Follow the [installation guide](../installation/README.md), then run:

```sh
reason --version
reason doctor --json
```

From a source checkout, use `./reason` in place of `reason`.

## 2. Create a project

```sh
reason init hello-reason
cd hello-reason
```

The project contains `reason.toml`, `src/main.rsn`, a test directory, and an
artifact directory.

## 3. Add an executable calculation

Put this in `src/main.rsn`:

```reasonscript
model HelloReason {
  struct Reading {
    label: string
    value: float
  }

  fn IsHigh(value: float) -> bool {
    return value >= 10.0
  }

  calculation Summary {
    let reading = Reading { label: "temperature", value: 12.5 }
    if IsHigh(reading.value) {
      result = reading.label
    } else {
      result = "normal"
    }
  }
}
```

## 4. Check, build, and run

Validate the syntax and semantics, build artifacts, and execute the model:

```sh
reason check src/main.rsn
reason build
reason run --json
```

The output will confirm that the goal was reached and show the calculation result:
```json
{
  "runtime_result": {
    "calculations": {
      "Summary": "temperature"
    },
    "result": "temperature",
    "status": "success"
  }
}
```

Use `reason analyze src/main.rsn --json` to inspect diagnostics and `reason view
src/main.rsn --plain` to view source beside its lowered representations.

## 5. Run tests

```sh
reason test
```

Repository contributors should finish with:

```sh
./reason ci --json
```

Next, read the [language reference](../language-reference.md),
[standard library](../standard-library.md), and [CLI reference](../reference/cli.md).
