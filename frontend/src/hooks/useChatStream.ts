import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'

import type { ConversationDetail } from './useConversations'

export type StreamingToolCall = {
  call_id: string
  name: string
  arguments: Record<string, unknown>
  result?: string
  error?: boolean
}

export type StreamingTurn = {
  text: string
  tools: StreamingToolCall[]
}

type ChatEvent =
  | { type: 'text'; text: string }
  | { type: 'tool_start'; call_id: string; name: string; arguments: Record<string, unknown> }
  | { type: 'tool_result'; call_id: string; result: string; error: boolean }
  | { type: 'usage'; input_tokens: number; output_tokens: number; cost_usd: number | null }
  | { type: 'done' }
  | { type: 'error'; message: string }

function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api/chat/ws`
}

export function useChatStream(conversationId: string | undefined) {
  const [streaming, setStreaming] = useState<StreamingTurn | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!conversationId) return
    const ws = new WebSocket(wsUrl())
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      if (wsRef.current === ws) wsRef.current = null
    }
    ws.onerror = () => setError('Connection error')
    ws.onmessage = (e) => {
      let event: ChatEvent
      try {
        event = JSON.parse(e.data)
      } catch {
        return
      }
      if (event.type === 'text') {
        setStreaming((cur) => ({
          text: (cur?.text ?? '') + event.text,
          tools: cur?.tools ?? [],
        }))
      } else if (event.type === 'tool_start') {
        setStreaming((cur) => ({
          text: cur?.text ?? '',
          tools: [
            ...(cur?.tools ?? []),
            {
              call_id: event.call_id,
              name: event.name,
              arguments: event.arguments,
            },
          ],
        }))
      } else if (event.type === 'tool_result') {
        setStreaming((cur) => {
          if (!cur) return cur
          return {
            text: cur.text,
            tools: cur.tools.map((t) =>
              t.call_id === event.call_id
                ? { ...t, result: event.result, error: event.error }
                : t,
            ),
          }
        })
      } else if (event.type === 'usage') {
        // Logged server-side; UI ignores for now (step 15 surfaces cost).
      } else if (event.type === 'done') {
        setStreaming(null)
        queryClient.invalidateQueries({ queryKey: ['conversations', conversationId] })
        queryClient.invalidateQueries({ queryKey: ['conversations'] })
      } else if (event.type === 'error') {
        setError(event.message)
        setStreaming(null)
      }
    }

    return () => {
      ws.close()
      if (wsRef.current === ws) wsRef.current = null
    }
  }, [conversationId, queryClient])

  const send = useCallback(
    (content: string) => {
      if (!conversationId || !wsRef.current) return
      if (wsRef.current.readyState !== WebSocket.OPEN) {
        setError('Not connected yet, please wait a moment.')
        return
      }
      setError(null)
      setStreaming({ text: '', tools: [] })

      // Optimistic user bubble so the UI doesn't feel dead while the agent
      // thinks. Replaced by the real DB row after 'done' triggers invalidate.
      queryClient.setQueryData<ConversationDetail | undefined>(
        ['conversations', conversationId],
        (old) => {
          if (!old) return old
          const lastSeq = old.messages[old.messages.length - 1]?.sequence ?? 0
          return {
            ...old,
            messages: [
              ...old.messages,
              {
                id: `optimistic-${Date.now()}`,
                sequence: lastSeq + 1,
                role: 'user',
                content,
                tool_calls: null,
                tool_call_id: null,
                created_at: new Date().toISOString(),
              },
            ],
          }
        },
      )

      wsRef.current.send(
        JSON.stringify({ conversation_id: conversationId, content }),
      )
    },
    [conversationId, queryClient],
  )

  return { streaming, error, connected, send }
}
