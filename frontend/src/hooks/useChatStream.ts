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
  | { type: 'notification'; kind: string; conversation_id: string; instruction?: string }

const PING_INTERVAL_MS = 25_000
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BASE_MS = 500
const RECONNECT_MAX_MS = 15_000

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
    let cancelled = false
    let pingTimer: ReturnType<typeof setInterval> | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let attempts = 0

    const stopPing = () => {
      if (pingTimer !== null) {
        clearInterval(pingTimer)
        pingTimer = null
      }
    }

    function handleMessage(e: MessageEvent) {
      if (cancelled) return
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
        // Step 15 will surface cost in the UI; ignored for now.
      } else if (event.type === 'done') {
        setStreaming(null)
        queryClient.invalidateQueries({ queryKey: ['conversations', conversationId] })
        queryClient.invalidateQueries({ queryKey: ['conversations'] })
      } else if (event.type === 'error') {
        setError(event.message)
        setStreaming(null)
      } else if (event.type === 'notification') {
        // Server-pushed (e.g. scheduled job fired in another conversation).
        // Invalidate so the sidebar + affected conversation reflect the
        // new DB state without a full reload.
        queryClient.invalidateQueries({ queryKey: ['conversations'] })
        queryClient.invalidateQueries({
          queryKey: ['conversations', event.conversation_id],
        })
      }
    }

    function connect() {
      const ws = new WebSocket(wsUrl())
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelled) return
        attempts = 0
        setConnected(true)
        setError(null)
        pingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            try {
              ws.send(JSON.stringify({ type: 'ping' }))
            } catch {
              // Send failed — onclose will fire and drive reconnect.
            }
          }
        }, PING_INTERVAL_MS)
      }

      ws.onclose = () => {
        if (cancelled) return
        stopPing()
        setConnected(false)
        if (wsRef.current === ws) wsRef.current = null

        attempts += 1
        if (attempts > MAX_RECONNECT_ATTEMPTS) {
          setError(
            "Can't reach the server. Check the backend, then reload this page.",
          )
          return
        }
        const delay = Math.min(
          RECONNECT_BASE_MS * 2 ** (attempts - 1),
          RECONNECT_MAX_MS,
        )
        reconnectTimer = setTimeout(() => {
          if (!cancelled) connect()
        }, delay)
      }

      // onerror is noisy and often followed by onclose — let close drive
      // reconnect, don't stick an error on the UI for transient blips.
      ws.onerror = () => {}

      ws.onmessage = handleMessage
    }

    const onVisibilityChange = () => {
      if (cancelled) return
      if (document.visibilityState !== 'visible') return
      const ws = wsRef.current
      // iOS/Safari and sometimes desktop browsers let the WS die silently
      // when the tab is backgrounded. On wake, if we're not in an active,
      // open state (or if a reconnect isn't already scheduled), kick off a
      // fresh connect so the user isn't staring at a zombie socket.
      if (!ws || ws.readyState === WebSocket.CLOSED) {
        if (reconnectTimer === null) {
          attempts = 0
          connect()
        }
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    connect()

    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', onVisibilityChange)
      stopPing()
      if (reconnectTimer !== null) clearTimeout(reconnectTimer)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [conversationId, queryClient])

  const send = useCallback(
    (content: string) => {
      if (!conversationId || !wsRef.current) return
      if (wsRef.current.readyState !== WebSocket.OPEN) {
        setError('Reconnecting, please wait a moment.')
        return
      }
      setError(null)
      setStreaming({ text: '', tools: [] })

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
