import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { Pencil } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { useChatStream } from '../hooks/useChatStream'
import {
  useConversation,
  useDeleteConversation,
  useRenameConversation,
  useSetConversationModel,
  type MessageOut,
} from '../hooks/useConversations'
import { useModels } from '../hooks/useModels'

import ChatInput from './ChatInput'
import MessageBubble from './MessageBubble'
import StreamingMessage from './StreamingMessage'

type Props = { conversationId: string }

export default function ChatView({ conversationId }: Props) {
  const { data: conversation, isLoading, error: loadError } = useConversation(conversationId)
  const { streaming, error: streamError, connected, send } = useChatStream(conversationId)
  const deleteConv = useDeleteConversation()
  const renameConv = useRenameConversation()
  const setModel = useSetConversationModel()
  const models = useModels()
  const navigate = useNavigate()
  const endRef = useRef<HTMLDivElement>(null)

  const [editingTitle, setEditingTitle] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')

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

  // If the conversation disappears out from under us (deleted in another
  // tab, or the agent cleaned up), don't strand the user on a 404 screen —
  // bounce them back to the list.
  useEffect(() => {
    if (loadError instanceof ApiError && loadError.status === 404) {
      navigate('/', { replace: true })
    }
  }, [loadError, navigate])

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

  function startEditTitle() {
    if (!conversation) return
    setTitleDraft(conversation.title)
    setEditingTitle(true)
  }

  async function saveTitle() {
    setEditingTitle(false)
    const trimmed = titleDraft.trim()
    if (!trimmed || !conversation || trimmed === conversation.title) return
    try {
      await renameConv.mutateAsync({ id: conversationId, title: trimmed })
    } catch (err) {
      window.alert(
        `Couldn't rename: ${err instanceof Error ? err.message : 'unknown'}`,
      )
    }
  }

  function onTitleKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault()
      ;(e.target as HTMLInputElement).blur()
    } else if (e.key === 'Escape') {
      e.preventDefault()
      setEditingTitle(false)
    }
  }

  async function handleDelete() {
    if (!conversation) return
    if (
      !window.confirm(
        `Delete "${conversation.title}"?\n\nThis removes the conversation and all its messages. It cannot be undone.`,
      )
    ) {
      return
    }
    try {
      await deleteConv.mutateAsync(conversationId)
      navigate('/', { replace: true })
    } catch (err) {
      window.alert(
        `Delete failed: ${err instanceof Error ? err.message : 'unknown'}`,
      )
    }
  }

  return (
    <div className="flex flex-col h-full">
      <header className="border-b px-4 md:px-6 py-4 sticky top-0 bg-white z-10 flex items-center justify-between gap-3">
        <div className="flex-1 min-w-0">
          {editingTitle ? (
            <input
              type="text"
              autoFocus
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onBlur={saveTitle}
              onKeyDown={onTitleKey}
              className="w-full text-xl font-semibold bg-transparent border-b-2 border-indigo-500 focus:outline-none text-base md:text-xl"
            />
          ) : (
            <button
              type="button"
              onClick={startEditTitle}
              className="flex items-center gap-2 min-w-0 text-left group"
              title="Click to rename"
            >
              <span className="text-xl font-semibold truncate">{conversation.title}</span>
              <Pencil
                size={14}
                className="flex-shrink-0 text-gray-300 group-hover:text-gray-500 transition"
              />
            </button>
          )}
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {models.data && models.data.models.length > 1 && (
            <select
              value={conversation.model ?? models.data.default}
              onChange={(e) => {
                const next = e.target.value
                setModel.mutate({ id: conversationId, model: next })
              }}
              disabled={setModel.isPending}
              className="text-xs border border-gray-300 rounded-lg px-2 py-1 bg-white hover:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 disabled:opacity-50"
              title="Model used for replies in this conversation"
            >
              {models.data.models.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                </option>
              ))}
            </select>
          )}
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
