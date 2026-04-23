import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../api/client'

export type ScheduledJobOut = {
  id: string
  instruction: string
  next_run: string | null
}

export function useScheduledJobs() {
  return useQuery({
    queryKey: ['scheduler', 'jobs'],
    queryFn: () => apiFetch<ScheduledJobOut[]>('/scheduler/jobs'),
  })
}

export function useCancelJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/scheduler/jobs/${encodeURIComponent(id)}`, {
        method: 'DELETE',
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler', 'jobs'] }),
  })
}
