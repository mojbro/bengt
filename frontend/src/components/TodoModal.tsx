import { useEffect, useState, type FormEvent } from 'react'
import { Trash2, X } from 'lucide-react'

import type { Priority, TodoOut } from '../hooks/useTodos'

type Props = {
  mode: 'create' | 'edit'
  initial?: TodoOut
  onClose: () => void
  onSave: (data: {
    text: string
    due: string | null
    priority: Priority | null
  }) => void | Promise<void>
  onDelete?: () => void | Promise<void>
}

const PRIORITY_OPTIONS: { value: Priority | ''; label: string }[] = [
  { value: '', label: 'No priority' },
  { value: 'highest', label: 'Highest' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
  { value: 'lowest', label: 'Lowest' },
]

export default function TodoModal({
  mode,
  initial,
  onClose,
  onSave,
  onDelete,
}: Props) {
  const [text, setText] = useState(initial?.text ?? '')
  const [due, setDue] = useState<string>(initial?.due ?? '')
  const [priority, setPriority] = useState<Priority | ''>(
    (initial?.priority as Priority | null) ?? '',
  )
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function submit(e: FormEvent) {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || submitting) return
    setSubmitting(true)
    try {
      await onSave({
        text: trimmed,
        due: due || null,
        priority: priority || null,
      })
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex items-end md:items-center justify-center p-0 md:p-4"
      onClick={onClose}
    >
      <form
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
        className="bg-white w-full max-w-lg rounded-t-2xl md:rounded-2xl p-4 md:p-5 space-y-3 shadow-xl"
        style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}
      >
        <div className="flex items-center justify-between">
          <h2 className="font-medium">
            {mode === 'create' ? 'Add todo' : 'Edit todo'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1 -m-1"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <input
          type="text"
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="What needs to be done?"
          className="w-full border rounded-lg px-3 py-2 text-base md:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
        />

        <div className="flex flex-wrap gap-2">
          <label className="flex-1 min-w-[10rem]">
            <span className="block text-xs text-gray-500 mb-1">Due</span>
            <input
              type="date"
              value={due}
              onChange={(e) => setDue(e.target.value)}
              className="w-full border rounded-lg px-2 py-1.5 text-base md:text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
            />
          </label>
          <label className="flex-1 min-w-[10rem]">
            <span className="block text-xs text-gray-500 mb-1">Priority</span>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as Priority | '')}
              className="w-full border rounded-lg px-2 py-1.5 text-base md:text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
            >
              {PRIORITY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="flex items-center justify-between pt-1">
          <div>
            {mode === 'edit' && onDelete && (
              <button
                type="button"
                onClick={async () => {
                  if (window.confirm('Delete this todo?')) {
                    await onDelete()
                    onClose()
                  }
                }}
                className="text-red-600 hover:bg-red-50 rounded-lg px-2 py-1.5 flex items-center gap-1.5 text-sm"
              >
                <Trash2 size={14} /> Delete
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!text.trim() || submitting}
              className="text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-4 py-1.5 font-medium disabled:opacity-50"
            >
              {submitting ? 'Saving…' : mode === 'create' ? 'Add' : 'Save'}
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
