import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../api/client'

type AuthStatus = { authed: boolean }

export function useAuth() {
  return useQuery({
    queryKey: ['auth'],
    queryFn: () => apiFetch<AuthStatus>('/auth/me'),
    staleTime: 30_000,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (password: string) =>
      apiFetch<AuthStatus>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ password }),
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(['auth'], data)
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch<AuthStatus>('/auth/logout', { method: 'POST' }),
    onSuccess: (data) => {
      queryClient.setQueryData(['auth'], data)
      queryClient.invalidateQueries()
    },
  })
}
