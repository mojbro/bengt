import { Plus } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import FAB from '../components/FAB'
import { useLogout } from '../hooks/useAuth'
import {
  useConversations,
  useCreateConversation,
} from '../hooks/useConversations'

function relativeTime(iso: string): string {
  const when = new Date(iso).getTime()
  const diff = Date.now() - when
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

export default function Home() {
  const conversations = useConversations()
  const createConv = useCreateConversation()
  const logout = useLogout()
  const navigate = useNavigate()

  async function startNew() {
    if (createConv.isPending) return
    const conv = await createConv.mutateAsync('New thread')
    navigate(`/conversations/${conv.id}`)
  }

  return (
    <div className="h-full overflow-auto bg-white">
      <header className="border-b px-4 md:px-6 py-4 sticky top-0 bg-white z-10">
        <h1 className="text-xl font-semibold">Chat</h1>
      </header>

      {conversations.isLoading && (
        <p className="px-4 py-6 text-sm text-gray-500">Loading…</p>
      )}
      {conversations.isError && (
        <p className="px-4 py-6 text-sm text-red-600">
          {conversations.error instanceof Error
            ? conversations.error.message
            : 'Failed to load conversations.'}
        </p>
      )}
      {conversations.data?.length === 0 && (
        <div className="px-4 py-16 text-center text-gray-500">
          <p className="text-lg mb-1">No conversations yet.</p>
          <p className="text-sm">Tap the + button to start one.</p>
        </div>
      )}

      <ul className="divide-y">
        {conversations.data?.map((conv) => (
          <li key={conv.id}>
            <Link
              to={`/conversations/${conv.id}`}
              className="block px-4 md:px-6 py-3 hover:bg-gray-50 active:bg-gray-100"
            >
              <div className="font-medium truncate">{conv.title}</div>
              <div className="text-xs text-gray-500 mt-0.5">
                Last active {relativeTime(conv.updated_at)}
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {/* Sign-out is in the sidebar on desktop; surfaces here for mobile. */}
      <div className="p-4 md:hidden">
        <button
          type="button"
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
          className="text-sm text-gray-500 hover:text-gray-800 disabled:opacity-50"
        >
          {logout.isPending ? 'Signing out…' : 'Sign out'}
        </button>
      </div>

      <FAB onClick={startNew} ariaLabel="New conversation">
        <Plus size={26} />
      </FAB>
    </div>
  )
}
