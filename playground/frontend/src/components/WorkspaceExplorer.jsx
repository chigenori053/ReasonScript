import { useState } from 'react'
import './WorkspaceExplorer.css'

function WorkspaceNode({ node, selectedPath, onSelectFile, depth }) {
  if (node.kind === 'directory') {
    return (
      <details className="ws-node ws-dir" open={!node.is_ignored}>
        <summary
          className={`ws-dir-label${node.is_ignored ? ' ws-ignored' : ''}`}
          style={{ paddingLeft: `${depth * 12 + 6}px` }}
        >
          {node.name}
          {node.is_ignored && <span className="ws-badge">ignored</span>}
        </summary>
        {!node.is_ignored && node.children?.length > 0 && (
          <div className="ws-children">
            {node.children.map(child => (
              <WorkspaceNode
                key={child.relative_path}
                node={child}
                selectedPath={selectedPath}
                onSelectFile={onSelectFile}
                depth={depth + 1}
              />
            ))}
          </div>
        )}
      </details>
    )
  }

  const isActive = node.relative_path === selectedPath
  const clickable = node.is_source

  return (
    <div
      className={`ws-node ws-file${isActive ? ' ws-active' : ''}${clickable ? '' : ' ws-inert'}`}
      style={{ paddingLeft: `${depth * 12 + 6}px` }}
      onClick={() => clickable && onSelectFile(node.relative_path)}
      title={clickable ? node.relative_path : `${node.relative_path} — preview unavailable`}
    >
      {node.name}
    </div>
  )
}

export default function WorkspaceExplorer({
  root,
  files,
  scanStatus,
  selectedPath,
  missingSelected,
  loading,
  error,
  onOpenWorkspace,
  onRefresh,
  onSelectFile,
}) {
  const [rootInput, setRootInput] = useState('')

  return (
    <div className="workspace-explorer">
      <div className="ws-header">Workspace</div>
      <div className="ws-open-row">
        <input
          className="ws-root-input"
          type="text"
          placeholder="/absolute/path/to/project"
          value={rootInput}
          onChange={e => setRootInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && rootInput.trim()) onOpenWorkspace(rootInput.trim()) }}
        />
        <button
          className="ws-open-btn"
          disabled={!rootInput.trim() || loading}
          onClick={() => onOpenWorkspace(rootInput.trim())}
        >
          Open
        </button>
      </div>

      {error && <div className="ws-error">{error}</div>}

      {root && (
        <>
          <div className="ws-root-row">
            <span className="ws-root-name" title={root}>{root}</span>
            <button className="ws-refresh-btn" onClick={onRefresh} disabled={loading} title="Refresh workspace">
              ⟳
            </button>
          </div>
          {scanStatus?.truncated && (
            <div className="ws-warning">
              Scan truncated at {scanStatus.max_files} files (max depth {scanStatus.max_depth}).
            </div>
          )}
          {missingSelected && (
            <div className="ws-warning">Selected file no longer exists on disk.</div>
          )}
          <div className="ws-tree">
            {files.length === 0 && <div className="ws-empty">No files found.</div>}
            {files.map(node => (
              <WorkspaceNode
                key={node.relative_path}
                node={node}
                selectedPath={selectedPath}
                onSelectFile={onSelectFile}
                depth={0}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
