import { Link, NavLink, useNavigate } from 'react-router-dom'

import { useLogout } from '../hooks/useAuth'
import {
  useConversations,
  useCreateConversation,
} from '../hooks/useConversations'

export default function Sidebar() {
  const logout = useLogout()
  const conversations = useConversations()
  const createConv = useCreateConversation()
  const navigate = useNavigate()

  async function startNew() {
    const conv = await createConv.mutateAsync('New thread')
    navigate(`/conversations/${conv.id}`)
  }

  return (
    <div className="flex h-full flex-col">
      <div className="p-4 border-b flex items-center justify-between">
        <Link to="/" className="text-lg font-semibold">
          bengt
        </Link>
        <button
          onClick={startNew}
          disabled={createConv.isPending}
          className="text-xs bg-black text-white rounded px-2 py-1 hover:bg-gray-800 disabled:opacity-50"
          title="New conversation"
        >
          + New
        </button>
      </div>

      <nav className="flex-1 p-2 space-y-0.5 text-sm overflow-auto">
        <NavLink
          to="/"
          end
          className={({ isActive }) =>
            `block px-3 py-2 rounded ${
              isActive ? 'bg-gray-200 font-medium' : 'hover:bg-gray-100'
            }`
          }
        >
          Chat
        </NavLink>
        <NavLink
          to="/files"
          className={({ isActive }) =>
            `block px-3 py-2 rounded ${
              isActive ? 'bg-gray-200 font-medium' : 'hover:bg-gray-100'
            }`
          }
        >
          Files
        </NavLink>
        <NavLink
          to="/scheduled"
          className={({ isActive }) =>
            `block px-3 py-2 rounded ${
              isActive ? 'bg-gray-200 font-medium' : 'hover:bg-gray-100'
            }`
          }
        >
          Scheduled
        </NavLink>
        <NavLink
          to="/audit"
          className={({ isActive }) =>
            `block px-3 py-2 rounded ${
              isActive ? 'bg-gray-200 font-medium' : 'hover:bg-gray-100'
            }`
          }
        >
          Audit
        </NavLink>

        <div className="mt-4 px-3 text-xs uppercase tracking-wide text-gray-400">
          Conversations
        </div>
        {conversations.isLoading && (
          <p className="px-3 py-2 text-gray-400 text-xs">Loading…</p>
        )}
        {conversations.data?.length === 0 && (
          <p className="px-3 py-2 text-gray-500 text-xs">None yet.</p>
        )}
        {conversations.data?.map((conv) => (
          <NavLink
            key={conv.id}
            to={`/conversations/${conv.id}`}
            className={({ isActive }) =>
              `block px-3 py-2 rounded truncate ${
                isActive ? 'bg-gray-200 font-medium' : 'hover:bg-gray-100'
              }`
            }
          >
            {conv.title}
          </NavLink>
        ))}
      </nav>

      <div className="p-2 border-t">
        <button
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
          className="w-full text-left px-3 py-2 rounded text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-50"
        >
          {logout.isPending ? 'Signing out…' : 'Sign out'}
        </button>
      </div>
    </div>
  )
}
