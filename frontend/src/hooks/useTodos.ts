import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../api/client'

export type Priority = 'highest' | 'high' | 'medium' | 'low' | 'lowest'

export type TodoOut = {
  id: string
  text: string
  done: boolean
  due: string | null // ISO date (YYYY-MM-DD)
  priority: Priority | null
  tags: string[]
  mentions: string[]
  completed_at: string | null
}

export type CreateTodoInput = {
  text: string
  due?: string | null
  priority?: Priority | null
}

export type UpdateTodoInput = {
  text: string
  due?: string | null
  priority?: Priority | null
}

const KEY = ['todos']

export function useTodos() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => apiFetch<TodoOut[]>('/todos'),
  })
}

export function useCreateTodo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateTodoInput) =>
      apiFetch<TodoOut>('/todos', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}

export function useToggleTodo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<TodoOut>(`/todos/${id}/toggle`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateTodo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: UpdateTodoInput & { id: string }) =>
      apiFetch<TodoOut>(`/todos/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}

export function useDeleteTodo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/todos/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}
