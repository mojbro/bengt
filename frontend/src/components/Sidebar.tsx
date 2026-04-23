import { Link, NavLink } from 'react-router-dom'

import { useLogout } from '../hooks/useAuth'

export default function Sidebar() {
  const logout = useLogout()

  return (
    <div className="flex h-full flex-col">
      <div className="p-4 border-b">
        <Link to="/" className="block text-lg font-semibold">
          bengt
        </Link>
      </div>

      <nav className="flex-1 p-2 space-y-1 text-sm overflow-auto">
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
        <div className="mt-4 px-3 text-xs uppercase text-gray-400 tracking-wide">
          Conversations
        </div>
        <p className="px-3 py-2 text-gray-500 text-xs">
          Conversation list lands in the next step.
        </p>
      </nav>

      <div className="p-2 border-t">
        <button
          onClick={() => logout.mutate()}
          className="w-full text-left px-3 py-2 rounded text-sm text-gray-600 hover:bg-gray-100"
          disabled={logout.isPending}
        >
          {logout.isPending ? 'Signing out…' : 'Sign out'}
        </button>
      </div>
    </div>
  )
}
