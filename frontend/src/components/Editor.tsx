import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from '../api/client'
import { useVaultFile, useWriteFile } from '../hooks/useVault'

type Props = { path: string; onBack?: () => void }

const AUTOSAVE_DELAY_MS = 2000

export default function Editor({ path, onBack }: Props) {
  const { data, isLoading, error } = useVaultFile(path)
  const writeFile = useWriteFile()
  const queryClient = useQueryClient()

  const [content, setContent] = useState('')
  const [dirty, setDirty] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [conflict, setConflict] = useState<string | null>(null)
  const [loadedMtime, setLoadedMtime] = useState<string | null>(null)
  const loadedPathRef = useRef<string | null>(null)

  // Reset content whenever we switch files or when the server fetches on a
  // clean buffer. In-progress edits survive background refetches.
  useEffect(() => {
    if (data && (loadedPathRef.current !== path || !dirty)) {
      setContent(data.content)
      setLoadedMtime(data.modified_at)
      setDirty(false)
      setConflict(null)
      loadedPathRef.current = path
    }

  }, [data, path])

  const save = useCallback(async () => {
    if (!dirty) return
    setSaveError(null)
    setConflict(null)
    try {
      const result = await writeFile.mutateAsync({
        path,
        content,
        expected_modified_at: loadedMtime,
      })
      setLoadedMtime(result.modified_at)
      setDirty(false)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setConflict(err.message)
      } else {
        setSaveError(err instanceof Error ? err.message : 'Save failed.')
      }
    }
  }, [content, dirty, loadedMtime, path, writeFile])

  // Debounced autosave — 2s after the last keystroke, but skip while a
  // conflict is unresolved (user has to choose to reload or force-save).
  useEffect(() => {
    if (!dirty || conflict) return
    const id = setTimeout(() => {
      save()
    }, AUTOSAVE_DELAY_MS)
    return () => clearTimeout(id)
  }, [content, dirty, conflict, save])

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

  async function reloadFromDisk() {
    // Wipe the buffer so the next query refetch repopulates content + mtime.
    setDirty(false)
    setConflict(null)
    loadedPathRef.current = null
    await queryClient.invalidateQueries({ queryKey: ['vault', 'file', path] })
  }

  async function forceSave() {
    setConflict(null)
    setSaveError(null)
    try {
      const result = await writeFile.mutateAsync({
        path,
        content,
        // No expected_modified_at — unconditional overwrite.
        expected_modified_at: null,
      })
      setLoadedMtime(result.modified_at)
      setDirty(false)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed.')
    }
  }

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
    : conflict
      ? 'Conflict'
      : dirty
        ? 'Unsaved'
        : 'Saved'

  const statusClass = conflict
    ? 'text-red-600 font-medium'
    : dirty
      ? 'text-orange-600'
      : 'text-gray-400'

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
          <span className={`text-xs ${statusClass}`}>{statusLabel}</span>
          <button
            type="button"
            onClick={save}
            disabled={!dirty || writeFile.isPending || !!conflict}
            className="text-xs bg-black text-white rounded px-3 py-1 disabled:opacity-40"
            title="Save (⌘S)"
          >
            Save
          </button>
        </div>
      </header>
      {conflict && (
        <div className="px-4 py-2 border-b bg-yellow-50 text-yellow-900 text-sm flex items-center justify-between gap-3 flex-wrap">
          <span>
            <strong>File changed on disk.</strong> Probably the agent wrote
            to it. Your unsaved edits are still here.
          </span>
          <span className="flex items-center gap-2 flex-shrink-0">
            <button
              type="button"
              onClick={reloadFromDisk}
              className="text-xs bg-yellow-700 text-white rounded px-2 py-1"
            >
              Reload (discard my edits)
            </button>
            <button
              type="button"
              onClick={forceSave}
              className="text-xs border border-yellow-700 text-yellow-900 rounded px-2 py-1"
            >
              Force save
            </button>
          </span>
        </div>
      )}
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
