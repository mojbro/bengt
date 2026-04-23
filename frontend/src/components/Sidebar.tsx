import {
  Activity,
  CheckCircle2,
  Clock,
  FolderOpen,
  LogOut,
  MessageSquare,
  Plus,
  type LucideIcon,
} from 'lucide-react'
import { Link, NavLink, useNavigate } from 'react-router-dom'

import { useLogout } from '../hooks/useAuth'
import {
  useConversations,
  useCreateConversation,
} from '../hooks/useConversations'

type NavItem = { to: string; label: string; Icon: LucideIcon; end?: boolean }

const navItems: NavItem[] = [
  { to: '/', label: 'Chat', Icon: MessageSquare, end: true },
  { to: '/todos', label: 'Todos', Icon: CheckCircle2 },
  { to: '/files', label: 'Files', Icon: FolderOpen },
  { to: '/scheduled', label: 'Scheduled', Icon: Clock },
  { to: '/audit', label: 'Audit', Icon: Activity },
]

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
          className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-2 py-1 flex items-center gap-1 disabled:opacity-50"
          title="New conversation"
        >
          <Plus size={12} strokeWidth={2.5} />
          New
        </button>
      </div>

      <nav className="flex-1 p-2 space-y-0.5 text-sm overflow-auto">
        {navItems.map(({ to, label, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg transition ${
                isActive
                  ? 'bg-indigo-50 text-indigo-900 font-medium'
                  : 'text-gray-700 hover:bg-gray-100'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon
                  size={16}
                  strokeWidth={isActive ? 2.25 : 1.75}
                  className={isActive ? 'text-indigo-600' : 'text-gray-500'}
                />
                {label}
              </>
            )}
          </NavLink>
        ))}

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
              `block px-3 py-1.5 rounded-lg truncate text-sm transition ${
                isActive
                  ? 'bg-indigo-50 text-indigo-900 font-medium'
                  : 'text-gray-600 hover:bg-gray-100'
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
          className="w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-50"
        >
          <LogOut size={16} strokeWidth={1.75} className="text-gray-500" />
          {logout.isPending ? 'Signing out…' : 'Sign out'}
        </button>
      </div>
    </div>
  )
}
