import { useNavigate } from 'react-router-dom'

import { useCreateConversation } from '../hooks/useConversations'

export default function Home() {
  const createConv = useCreateConversation()
  const navigate = useNavigate()

  async function startNew() {
    const conv = await createConv.mutateAsync('New thread')
    navigate(`/conversations/${conv.id}`)
  }

  return (
    <div className="h-full flex items-center justify-center bg-white">
      <div className="text-center max-w-md p-8">
        <h2 className="text-xl font-medium mb-2">Start a conversation</h2>
        <p className="text-sm text-gray-500 mb-6">
          Or pick an existing one from the sidebar.
        </p>
        <button
          onClick={startNew}
          disabled={createConv.isPending}
          className="bg-black text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          {createConv.isPending ? 'Creating…' : '+ New conversation'}
        </button>
      </div>
    </div>
  )
}
