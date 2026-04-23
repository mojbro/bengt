import { useState } from 'react'

import Editor from '../components/Editor'
import VaultTree from '../components/VaultTree'

export default function VaultPage() {
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <div className="h-full flex flex-col md:flex-row">
      {/* Tree: full height on desktop, hidden on mobile when a file is open. */}
      <aside
        className={`${
          selected ? 'hidden md:block' : 'block'
        } md:w-64 md:border-r md:flex-shrink-0 bg-gray-50 overflow-auto py-2 md:h-full`}
      >
        <div className="px-3 pb-2 text-xs uppercase tracking-wide text-gray-400">
          Vault
        </div>
        <VaultTree selectedPath={selected} onSelect={setSelected} />
      </aside>

      {/* Editor pane. Hidden on mobile until a file is picked. */}
      <div
        className={`${
          selected ? 'flex flex-1' : 'hidden md:flex md:flex-1'
        } overflow-hidden min-h-0`}
      >
        {selected ? (
          <Editor
            path={selected}
            onBack={() => setSelected(null)}
            onDeleted={() => setSelected(null)}
          />
        ) : (
          <div className="h-full w-full flex items-center justify-center text-gray-500 text-sm p-8">
            <p>Pick a file from the tree.</p>
          </div>
        )}
      </div>
    </div>
  )
}
