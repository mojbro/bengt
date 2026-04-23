import { useParams } from 'react-router-dom'

export default function ConversationPage() {
  const { id } = useParams()
  return (
    <div className="p-8 text-gray-500">
      <p>Conversation <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">{id}</code></p>
      <p className="text-sm mt-2">Chat view lands in step 11.</p>
    </div>
  )
}
