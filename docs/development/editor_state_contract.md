# Editor State Contract

Implemented client-side in `playground/frontend/src/App.jsx`. This state
has no backend counterpart — it exists purely in the React component tree.

## Selected file state

```js
selectedFile = {
  relativePath: "examples/basic.rsn",
  content: "model Basic {}",       // live editor buffer
  savedContent: "model Basic {}",  // last content known to be on disk
  version: "1719800000.1234",      // mtime returned by /api/workspace/read or /save
  readOnly: false,
  missing: false,
}
```

`selectedFile === null` means the editor is in temporary mode (see
`workspace_editing_foundation.md`).

## Dirty state

Dirty is **derived**, not stored:

```js
dirty = selectedFile.content !== selectedFile.savedContent
```

- Editing the buffer changes `dirty` immediately (no debounce).
- A successful save sets `savedContent = content`, making `dirty` false.
- Switching to a different file while dirty prompts the user
  (`window.confirm`) before discarding the in-memory edit — this satisfies
  EDIT-004's "warn or preserve" requirement with the simplest correct
  option for a single-buffer editor.

## Stale analyze result

Each analyzed file's result is cached:

```js
analyzeResultsByFile[relativePath] = {
  result: { pipeline, views, diagnostics, artifacts, ... },
  analyzedContent: "...",   // the content that was actually analyzed
}
```

A cached result is **stale** when:

```js
stale = analyzedContent !== selectedFile.content
```

The editor header shows a "stale analysis" badge in that case (AFR-003).
Stale results are still fully rendered — they never crash or block the UI
(AFR-004) — they're just visually flagged as out of date until the user
re-runs Analyze.

## Switching files

When `selectedFile` changes, the cached `analyzeResultsByFile[path].result`
(if any) is restored into the shared `results` state that all 27
`TabPanel` tabs read from (AFR-002). If no cached result exists yet, the
panels show their normal empty/idle state.

## Why no dedicated backend test

Because dirty/stale tracking is pure React state with no server
round-trip, it is verified via manual browser interaction (see the Phase 3
verification steps in the implementation notes) rather than a pytest file.
