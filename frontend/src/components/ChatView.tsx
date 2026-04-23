import { useEffect, useMemo, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useChatStream } from '../hooks/useChatStream'
import {
  useConversation,
  useDeleteConversation,
  type MessageOut,
} from '../hooks/useConversations'

import ChatInput from './ChatInput'
import MessageBubble from './MessageBubble'
import StreamingMessage from './StreamingMessage'

type Props = { conversationId: string }

export default function ChatView({ conversationId }: Props) {
  const { data: conversation, isLoading, error: loadError } = useConversation(conversationId)
  const { streaming, error: streamError, connected, send } = useChatStream(conversationId)
  const deleteConv = useDeleteConversation()
  const navigate = useNavigate()
  const endRef = useRef<HTMLDivElement>(null)

  const toolResultsById = useMemo(() => {
    const map = new Map<string, { result: string; error: boolean }>()
    if (!conversation) return map
    for (const msg of conversation.messages) {
      if (msg.role === 'tool' && msg.tool_call_id) {
        map.set(msg.tool_call_id, { result: msg.content, error: false })
      }
    }
    return map
  }, [conversation])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [conversation?.messages.length, streaming?.text, streaming?.tools.length])

  if (isLoading) {
    return <div className="p-6 text-gray-500 text-sm">Loading…</div>
  }
  if (loadError || !conversation) {
    return (
      <div className="p-6 text-red-600 text-sm">
        {loadError instanceof Error ? loadError.message : 'Failed to load conversation.'}
      </div>
    )
  }

  const visibleMessages = conversation.messages.filter(
    (m: MessageOut) => m.role !== 'system' && m.role !== 'tool',
  )

  const isStreaming = streaming !== null

  function handleDelete() {
    if (!conversation) return
    if (
      window.confirm(
        `Delete "${conversation.title}"?\n\nThis removes the conversation and all its messages. It cannot be undone.`,
      )
    ) {
      deleteConv.mutate(conversationId, {
        onSuccess: () => navigate('/'),
      })
    }
  }

  return (
    <div className="flex flex-col h-full">
      <header className="border-b px-4 py-3 flex items-center justify-between gap-3">
        <h2 className="font-medium truncate">{conversation.title}</h2>
        <div className="flex items-center gap-3 flex-shrink-0">
          <Link
            to={`/audit?conversation_id=${encodeURIComponent(conversationId)}`}
            className="text-xs text-gray-500 hover:underline"
            title="View this conversation's LLM calls and tool invocations"
          >
            Debug
          </Link>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleteConv.isPending}
            className="text-xs text-red-600 hover:underline disabled:opacity-40"
          >
            {deleteConv.isPending ? 'Deleting…' : 'Delete'}
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-auto px-4 py-4 space-y-4 bg-white">
        {visibleMessages.length === 0 && !streaming && (
          <p className="text-gray-500 text-sm">
            Say hello to get started.
          </p>
        )}
        {visibleMessages.map((msg) => (
          <MessageBubble
            key={msg.id}
            message={msg}
            toolResultsById={toolResultsById}
          />
        ))}
        {streaming && <StreamingMessage turn={streaming} />}
        {streamError && (
          <div className="text-red-600 text-sm">
            {streamError}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="border-t p-3 bg-white">
        <ChatInput
          disabled={isStreaming || !connected}
          onSend={send}
          placeholder={!connected ? 'Connecting…' : isStreaming ? 'Waiting for reply…' : undefined}
        />
      </div>
    </div>
  )
}
