import { useCallback, useEffect, useRef, useState } from 'react'

import { useVaultFile, useWriteFile } from '../hooks/useVault'

type Props = { path: string; onBack?: () => void }

const AUTOSAVE_DELAY_MS = 2000

export default function Editor({ path, onBack }: Props) {
  const { data, isLoading, error } = useVaultFile(path)
  const writeFile = useWriteFile()

  const [content, setContent] = useState('')
  const [dirty, setDirty] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const loadedPathRef = useRef<string | null>(null)

  // Reset content whenever we switch files or the server fetches.
  useEffect(() => {
    if (data && (loadedPathRef.current !== path || !dirty)) {
      setContent(data.content)
      setDirty(false)
      loadedPathRef.current = path
    }
    // Intentionally not depending on `dirty` — we don't want server
    // refetches to overwrite in-progress edits.

  }, [data, path])

  const save = useCallback(async () => {
    if (!dirty) return
    setSaveError(null)
    try {
      await writeFile.mutateAsync({ path, content })
      setDirty(false)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed.')
    }
  }, [content, dirty, path, writeFile])

  // Debounced autosave — 2s after the last keystroke.
  useEffect(() => {
    if (!dirty) return
    const id = setTimeout(() => {
      save()
    }, AUTOSAVE_DELAY_MS)
    return () => clearTimeout(id)
  }, [content, dirty, save])

  // Ctrl/Cmd+S manual save.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
        e.preventDefault()
        save()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [save])

  if (isLoading) {
    return <div className="p-6 text-gray-500 text-sm">Loading…</div>
  }
  if (error) {
    return (
      <div className="p-6 text-red-600 text-sm">
        {error instanceof Error ? error.message : 'Failed to load file.'}
      </div>
    )
  }

  const statusLabel = writeFile.isPending
    ? 'Saving…'
    : dirty
      ? 'Unsaved'
      : 'Saved'

  return (
    <div className="flex flex-col h-full w-full bg-white">
      <header className="border-b px-4 py-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="md:hidden text-gray-500 hover:text-black px-1 text-base"
              aria-label="Back to tree"
            >
              ←
            </button>
          )}
          <div className="font-mono text-sm truncate">{path}</div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <span
            className={`text-xs ${
              dirty ? 'text-orange-600' : 'text-gray-400'
            }`}
          >
            {statusLabel}
          </span>
          <button
            type="button"
            onClick={save}
            disabled={!dirty || writeFile.isPending}
            className="text-xs bg-black text-white rounded px-3 py-1 disabled:opacity-40"
            title="Save (⌘S)"
          >
            Save
          </button>
        </div>
      </header>
      {saveError && (
        <div className="px-4 py-2 border-b bg-red-50 text-red-700 text-sm">
          {saveError}
        </div>
      )}
      <textarea
        value={content}
        onChange={(e) => {
          setContent(e.target.value)
          setDirty(true)
        }}
        className="flex-1 min-h-0 resize-none outline-none p-4 font-mono text-sm leading-relaxed"
        spellCheck={false}
      />
    </div>
  )
}
