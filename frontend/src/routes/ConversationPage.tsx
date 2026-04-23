import { useParams } from 'react-router-dom'

import ChatView from '../components/ChatView'

export default function ConversationPage() {
  const { id } = useParams()
  if (!id) return null
  return <ChatView conversationId={id} />
}
