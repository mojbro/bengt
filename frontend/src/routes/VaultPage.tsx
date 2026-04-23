import { useState } from 'react'

import Editor from '../components/Editor'
import VaultTree from '../components/VaultTree'

export default function VaultPage() {
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <div className="flex h-full">
      <aside className="w-64 border-r bg-gray-50 overflow-auto py-2">
        <div className="px-3 pb-2 text-xs uppercase tracking-wide text-gray-400">
          Vault
        </div>
        <VaultTree selectedPath={selected} onSelect={setSelected} />
      </aside>
      <div className="flex-1 overflow-hidden">
        {selected ? (
          <Editor path={selected} />
        ) : (
          <div className="h-full flex items-center justify-center text-gray-500 text-sm p-8">
            <div className="text-center max-w-sm">
              <p className="mb-1">Pick a file from the tree to edit it.</p>
              <p className="text-xs text-gray-400">
                New files are created by the agent or via chat; in-UI file
                creation lands later.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
