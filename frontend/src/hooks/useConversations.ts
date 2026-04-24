import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../api/client'

export type ToolCallPayload = {
  id: string
  name: string
  arguments: Record<string, unknown>
}

export type MessageOut = {
  id: string
  sequence: number
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  tool_calls: ToolCallPayload[] | null
  tool_call_id: string | null
  created_at: string
}

export type ConversationOut = {
  id: string
  title: string
  model: string | null
  created_at: string
  updated_at: string
}

export type ConversationDetail = ConversationOut & {
  messages: MessageOut[]
}

export function useConversations() {
  return useQuery({
    queryKey: ['conversations'],
    queryFn: () => apiFetch<ConversationOut[]>('/conversations'),
  })
}

export function useConversation(id: string | undefined) {
  return useQuery({
    queryKey: ['conversations', id],
    queryFn: () => apiFetch<ConversationDetail>(`/conversations/${id}`),
    enabled: !!id,
  })
}

export function useCreateConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (title: string = 'New thread') =>
      apiFetch<ConversationOut>('/conversations', {
        method: 'POST',
        body: JSON.stringify({ title }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['conversations'] }),
  })
}

export function useDeleteConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/conversations/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['conversations'] }),
  })
}

export function useRenameConversation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      apiFetch<ConversationOut>(`/conversations/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ title }),
      }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['conversations'] })
      qc.invalidateQueries({ queryKey: ['conversations', data.id] })
    },
  })
}

export function useSetConversationModel() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, model }: { id: string; model: string | null }) =>
      apiFetch<ConversationOut>(`/conversations/${id}`, {
        method: 'PATCH',
        // Send null explicitly so the backend can distinguish clear vs omit.
        body: JSON.stringify({ model }),
      }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['conversations'] })
      qc.invalidateQueries({ queryKey: ['conversations', data.id] })
    },
  })
}
