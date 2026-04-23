import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'

import FAB from '../components/FAB'
import TodoModal from '../components/TodoModal'
import TodoRow from '../components/TodoRow'
import {
  useCreateTodo,
  useDeleteTodo,
  useToggleTodo,
  useTodos,
  useUpdateTodo,
  type TodoOut,
} from '../hooks/useTodos'

type Filter = 'all' | 'open' | 'done'

function sortTodos(todos: TodoOut[]): TodoOut[] {
  // Open first, then done. Within open: overdue+today first, then by due
  // ascending (no-date at the bottom). Stable by input order otherwise.
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const dueValue = (t: TodoOut): number => {
    if (!t.due) return Number.MAX_SAFE_INTEGER
    return new Date(t.due + 'T12:00:00').getTime()
  }
  return [...todos].sort((a, b) => {
    if (a.done !== b.done) return a.done ? 1 : -1
    return dueValue(a) - dueValue(b)
  })
}

export default function TodosPage() {
  const todos = useTodos()
  const createTodo = useCreateTodo()
  const toggleTodo = useToggleTodo()
  const updateTodo = useUpdateTodo()
  const deleteTodo = useDeleteTodo()

  const [filter, setFilter] = useState<Filter>('open')
  const [showAdd, setShowAdd] = useState(false)
  const [editing, setEditing] = useState<TodoOut | null>(null)

  const sorted = useMemo(() => sortTodos(todos.data ?? []), [todos.data])
  const counts = useMemo(() => {
    const all = todos.data ?? []
    return {
      all: all.length,
      open: all.filter((t) => !t.done).length,
      done: all.filter((t) => t.done).length,
    }
  }, [todos.data])

  const filtered = sorted.filter((t) => {
    if (filter === 'all') return true
    if (filter === 'open') return !t.done
    return t.done
  })

  return (
    <div className="h-full overflow-auto bg-white">
      <header className="border-b px-4 md:px-6 py-4 sticky top-0 bg-white z-10">
        <h1 className="text-xl font-semibold">Todos</h1>
      </header>

      <div className="flex gap-1 px-4 md:px-6 py-3 border-b sticky top-[61px] bg-white z-10">
        {(['open', 'all', 'done'] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`text-sm px-3 py-1 rounded-full font-medium transition ${
              filter === f
                ? 'bg-indigo-100 text-indigo-900'
                : 'text-gray-500 hover:bg-gray-100'
            }`}
          >
            {f[0].toUpperCase() + f.slice(1)}{' '}
            <span className="text-xs opacity-70">({counts[f]})</span>
          </button>
        ))}
      </div>

      {todos.isLoading && (
        <p className="px-4 md:px-6 py-8 text-sm text-gray-400">Loading…</p>
      )}
      {todos.isError && (
        <p className="px-4 md:px-6 py-8 text-sm text-red-600">
          {todos.error instanceof Error
            ? todos.error.message
            : 'Failed to load todos.'}
        </p>
      )}
      {todos.data && filtered.length === 0 && !todos.isLoading && (
        <div className="px-4 md:px-6 py-16 text-center text-gray-500">
          {counts.all === 0 ? (
            <>
              <p className="text-lg mb-1">Your todo list is empty.</p>
              <p className="text-sm">Tap the + button to add your first.</p>
            </>
          ) : filter === 'open' ? (
            <p className="text-sm">
              Nothing open. Nice work! ✨
            </p>
          ) : (
            <p className="text-sm">No todos match this filter.</p>
          )}
        </div>
      )}

      <ul className="divide-y">
        {filtered.map((t) => (
          <li key={t.id}>
            <TodoRow
              todo={t}
              onToggle={() => toggleTodo.mutate(t.id)}
              onClick={() => setEditing(t)}
            />
          </li>
        ))}
      </ul>

      <FAB onClick={() => setShowAdd(true)} ariaLabel="Add todo">
        <Plus size={26} />
      </FAB>

      {showAdd && (
        <TodoModal
          mode="create"
          onClose={() => setShowAdd(false)}
          onSave={async (data) => {
            await createTodo.mutateAsync(data)
          }}
        />
      )}
      {editing && (
        <TodoModal
          mode="edit"
          initial={editing}
          onClose={() => setEditing(null)}
          onSave={async (data) => {
            await updateTodo.mutateAsync({ id: editing.id, ...data })
          }}
          onDelete={async () => {
            await deleteTodo.mutateAsync(editing.id)
          }}
        />
      )}
    </div>
  )
}
