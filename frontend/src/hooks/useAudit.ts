import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../api/client'

export type AuditEntryOut = {
  id: string
  timestamp: string
  kind: 'llm_call' | 'tool_invocation' | string
  conversation_id: string | null
  cost_usd: number
  data: Record<string, unknown>
}

export type BudgetStatusOut = {
  cap_usd: number
  spent_usd: number
  remaining_usd: number
  exceeded: boolean
}

export function useAuditRecent(limit: number = 100) {
  return useQuery({
    queryKey: ['audit', 'recent', limit],
    queryFn: () =>
      apiFetch<AuditEntryOut[]>(`/audit/recent?limit=${limit}`),
    refetchInterval: 10_000,
  })
}

export function useBudget() {
  return useQuery({
    queryKey: ['audit', 'budget'],
    queryFn: () => apiFetch<BudgetStatusOut>('/audit/budget'),
    refetchInterval: 10_000,
  })
}
