import { Link, useNavigate } from 'react-router-dom'

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
    const conv = await createConv.mutateAsync('New thread')
    navigate(`/conversations/${conv.id}`)
  }

  return (
    <div className="h-full overflow-auto bg-white">
      <header className="border-b px-4 md:px-6 py-4 sticky top-0 bg-white z-10 flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Chat</h1>
        <button
          onClick={startNew}
          disabled={createConv.isPending}
          className="text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-3 py-1.5 disabled:opacity-50 transition"
        >
          {createConv.isPending ? 'Creating…' : '+ New'}
        </button>
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
        <div className="px-4 py-8 text-center text-sm text-gray-500">
          No conversations yet. Tap <strong>+ New</strong> to start one.
        </div>
      )}

      <ul className="divide-y">
        {conversations.data?.map((conv) => (
          <li key={conv.id}>
            <Link
              to={`/conversations/${conv.id}`}
              className="block px-4 py-3 hover:bg-gray-50 active:bg-gray-100"
            >
              <div className="font-medium truncate">{conv.title}</div>
              <div className="text-xs text-gray-500 mt-0.5">
                Last active {relativeTime(conv.updated_at)}
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {/* Sign-out is on the sidebar for desktop; duplicate here for mobile. */}
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
    </div>
  )
}
