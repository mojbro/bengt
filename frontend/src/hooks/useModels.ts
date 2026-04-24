import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../api/client'

export type ModelOut = {
  name: string // key the backend uses for conversation.model
  id: string // the underlying provider model id
}

export type ModelsListOut = {
  models: ModelOut[]
  default: string
}

export function useModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: () => apiFetch<ModelsListOut>('/models'),
    staleTime: 5 * 60_000, // config doesn't change mid-session
  })
}
