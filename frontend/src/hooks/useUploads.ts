import { useMutation } from '@tanstack/react-query'

import { ApiError } from '../api/client'

export type UploadOut = {
  original_path: string
  md_path: string
  summary: string
  tags: string[]
  extracted_chars: number
}

export function useUploadFile() {
  return useMutation({
    mutationFn: async (file: File): Promise<UploadOut> => {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/uploads', {
        method: 'POST',
        body: form,
        credentials: 'include',
      })
      if (!res.ok) {
        let detail: string
        try {
          const body = await res.json()
          detail = body.detail || JSON.stringify(body)
        } catch {
          detail = await res.text()
        }
        throw new ApiError(res.status, detail || `HTTP ${res.status}`)
      }
      return (await res.json()) as UploadOut
    },
  })
}

export function useUploadFromUrl() {
  return useMutation({
    mutationFn: async (url: string): Promise<UploadOut> => {
      const res = await fetch('/api/uploads/from-url', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      if (!res.ok) {
        let detail: string
        try {
          const body = await res.json()
          detail = body.detail || JSON.stringify(body)
        } catch {
          detail = await res.text()
        }
        throw new ApiError(res.status, detail || `HTTP ${res.status}`)
      }
      return (await res.json()) as UploadOut
    },
  })
}

export function downloadUrl(vaultPath: string): string {
  return `/api/uploads/download?path=${encodeURIComponent(vaultPath)}`
}
