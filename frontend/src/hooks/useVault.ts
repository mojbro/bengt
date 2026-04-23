import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../api/client'

export type VaultEntry = {
  path: string
  is_dir: boolean
  size: number | null
}

export type FileContentOut = {
  path: string
  content: string
}

export function useVaultTree(
  path: string = '',
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ['vault', 'tree', path],
    queryFn: () =>
      apiFetch<VaultEntry[]>(
        `/vault/tree?path=${encodeURIComponent(path)}`,
      ),
    enabled: options?.enabled ?? true,
  })
}

export function useVaultFile(path: string | null) {
  return useQuery({
    queryKey: ['vault', 'file', path],
    queryFn: () =>
      apiFetch<FileContentOut>(
        `/vault/file?path=${encodeURIComponent(path!)}`,
      ),
    enabled: !!path,
  })
}

export function useWriteFile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ path, content }: { path: string; content: string }) =>
      apiFetch<FileContentOut>(
        `/vault/file?path=${encodeURIComponent(path)}`,
        { method: 'PUT', body: JSON.stringify({ content }) },
      ),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['vault', 'file', vars.path] })
      qc.invalidateQueries({ queryKey: ['vault', 'tree'] })
    },
  })
}
