import { useState } from 'react'

import Editor from '../components/Editor'
import VaultTree from '../components/VaultTree'

export default function VaultPage() {
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <div className="h-full flex flex-col">
      {/* On mobile the header hides once an editor is open so the file
          takes the full screen with its own header (+ back button). */}
      <header
        className={`${
          selected ? 'hidden md:block' : 'block'
        } border-b px-4 md:px-6 py-4 sticky top-0 bg-white z-10`}
      >
        <h1 className="text-xl font-semibold">Files</h1>
      </header>

      <div className="flex-1 flex flex-col md:flex-row min-h-0">
        <aside
          className={`${
            selected ? 'hidden md:block' : 'block'
          } md:w-64 md:border-r md:flex-shrink-0 bg-gray-50 overflow-auto md:h-full`}
        >
          <VaultTree selectedPath={selected} onSelect={setSelected} />
        </aside>

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
    </div>
  )
}
