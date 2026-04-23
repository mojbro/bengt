import { Check } from 'lucide-react'

import type { Priority, TodoOut } from '../hooks/useTodos'

type Props = {
  todo: TodoOut
  onToggle: () => void
  onClick: () => void
}

const PRIORITY_DOT: Record<Priority, string> = {
  highest: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-amber-400',
  low: 'bg-blue-400',
  lowest: 'bg-gray-400',
}

function dueDescription(
  due: string | null,
  done: boolean,
): { label: string; className: string } | null {
  if (!due) return null
  // Anchor at midday so the local-timezone conversion doesn't bump the
  // "day" across a boundary.
  const d = new Date(due + 'T12:00:00')
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const weekAhead = new Date(today)
  weekAhead.setDate(weekAhead.getDate() + 7)

  const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString()

  if (!done && d < today) {
    return {
      label: d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
      }),
      className: 'text-red-600 bg-red-50',
    }
  }
  if (sameDay(d, today)) return { label: 'Today', className: 'text-amber-700 bg-amber-50' }
  if (sameDay(d, tomorrow)) return { label: 'Tomorrow', className: 'text-amber-700 bg-amber-50' }
  if (d < weekAhead) {
    return {
      label: d.toLocaleDateString(undefined, { weekday: 'short' }),
      className: 'text-gray-600 bg-gray-100',
    }
  }
  return {
    label: d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
    className: 'text-gray-600 bg-gray-100',
  }
}

export default function TodoRow({ todo, onToggle, onClick }: Props) {
  const due = dueDescription(todo.due, todo.done)
  return (
    <div className="flex items-start gap-3 px-4 py-3 hover:bg-gray-50 active:bg-gray-100 transition">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          onToggle()
        }}
        aria-label={todo.done ? 'Mark as not done' : 'Mark as done'}
        className={`flex-shrink-0 w-6 h-6 mt-0.5 rounded-full border-2 flex items-center justify-center transition ${
          todo.done
            ? 'bg-indigo-600 border-indigo-600'
            : 'border-gray-300 hover:border-indigo-500'
        }`}
      >
        {todo.done && <Check size={14} className="text-white" strokeWidth={3} />}
      </button>

      <button
        type="button"
        onClick={onClick}
        className="flex-1 min-w-0 text-left"
      >
        <div className="flex items-start gap-2 flex-wrap">
          {todo.priority && (
            <span
              aria-label={`${todo.priority} priority`}
              className={`flex-shrink-0 mt-1.5 w-2 h-2 rounded-full ${PRIORITY_DOT[todo.priority]}`}
            />
          )}
          <span
            className={`text-sm break-words ${
              todo.done ? 'text-gray-400 line-through' : 'text-gray-900'
            }`}
          >
            {todo.text}
          </span>
        </div>
        {(due || todo.tags.length > 0) && (
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            {due && (
              <span
                className={`text-xs rounded-full px-2 py-0.5 font-medium ${due.className}`}
              >
                {due.label}
              </span>
            )}
            {todo.tags.map((t) => (
              <span
                key={t}
                className="text-xs rounded-full px-2 py-0.5 bg-indigo-50 text-indigo-700"
              >
                #{t}
              </span>
            ))}
          </div>
        )}
      </button>
    </div>
  )
}
