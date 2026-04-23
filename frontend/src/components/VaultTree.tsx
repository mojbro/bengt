import { useState } from 'react'

import { useVaultTree, type VaultEntry } from '../hooks/useVault'

type Props = {
  selectedPath: string | null
  onSelect: (path: string) => void
}

export default function VaultTree({ selectedPath, onSelect }: Props) {
  const root = useVaultTree('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  function toggle(path: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  if (root.isLoading) {
    return <p className="text-xs text-gray-400 px-3 py-2">Loading…</p>
  }
  if (root.isError) {
    return <p className="text-xs text-red-600 px-3 py-2">Failed to load vault.</p>
  }

  return (
    <ul className="text-sm">
      {(root.data ?? []).map((entry) => (
        <TreeNode
          key={entry.path}
          entry={entry}
          depth={0}
          expanded={expanded}
          toggle={toggle}
          selectedPath={selectedPath}
          onSelect={onSelect}
        />
      ))}
      {root.data?.length === 0 && (
        <li className="text-xs text-gray-400 px-3 py-2">Vault is empty.</li>
      )}
    </ul>
  )
}

type NodeProps = {
  entry: VaultEntry
  depth: number
  expanded: Set<string>
  toggle: (path: string) => void
  selectedPath: string | null
  onSelect: (path: string) => void
}

function TreeNode({
  entry,
  depth,
  expanded,
  toggle,
  selectedPath,
  onSelect,
}: NodeProps) {
  const name = entry.path.split('/').filter(Boolean).pop() || entry.path
  const paddingLeft = { paddingLeft: `${8 + depth * 12}px` }
  if (entry.is_dir) {
    return (
      <DirNode
        entry={entry}
        name={name}
        paddingLeft={paddingLeft}
        depth={depth}
        expanded={expanded}
        toggle={toggle}
        selectedPath={selectedPath}
        onSelect={onSelect}
      />
    )
  }
  const isSelected = selectedPath === entry.path
  return (
    <li>
      <button
        onClick={() => onSelect(entry.path)}
        style={paddingLeft}
        className={`w-full text-left py-1 pr-2 truncate rounded ${
          isSelected ? 'bg-blue-100 text-blue-900 font-medium' : 'hover:bg-gray-100'
        }`}
      >
        {name}
      </button>
    </li>
  )
}

function DirNode({
  entry,
  name,
  paddingLeft,
  depth,
  expanded,
  toggle,
  selectedPath,
  onSelect,
}: {
  entry: VaultEntry
  name: string
  paddingLeft: React.CSSProperties
  depth: number
  expanded: Set<string>
  toggle: (path: string) => void
  selectedPath: string | null
  onSelect: (path: string) => void
}) {
  const isOpen = expanded.has(entry.path)
  const children = useVaultTree(entry.path, { enabled: isOpen })
  return (
    <li>
      <button
        onClick={() => toggle(entry.path)}
        style={paddingLeft}
        className="w-full text-left py-1 pr-2 truncate rounded hover:bg-gray-100 flex items-center gap-1"
      >
        <span className="text-gray-400 text-xs w-3">{isOpen ? '▾' : '▸'}</span>
        <span className="truncate">{name}/</span>
      </button>
      {isOpen && children.data && (
        <ul>
          {children.data.map((child) => (
            <TreeNode
              key={child.path}
              entry={child}
              depth={depth + 1}
              expanded={expanded}
              toggle={toggle}
              selectedPath={selectedPath}
              onSelect={onSelect}
            />
          ))}
          {children.data.length === 0 && (
            <li
              className="text-xs text-gray-400 py-1"
              style={{ paddingLeft: `${8 + (depth + 1) * 12}px` }}
            >
              (empty)
            </li>
          )}
        </ul>
      )}
    </li>
  )
}
