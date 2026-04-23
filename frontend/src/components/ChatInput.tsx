import { Loader2, Paperclip, X } from 'lucide-react'
import { useRef, useState, type ChangeEvent, type KeyboardEvent } from 'react'

import { useUploadFile, type UploadOut } from '../hooks/useUploads'

type Props = {
  disabled: boolean
  onSend: (text: string) => void
  placeholder?: string
}

type Attachment = {
  file: File
  result?: UploadOut
  error?: string
}

const ACCEPT =
  '.pdf,.docx,.txt,.md,.markdown,.html,.htm,application/pdf,text/plain,text/markdown,text/html'

export default function ChatInput({ disabled, onSend, placeholder }: Props) {
  const [text, setText] = useState('')
  const [attachment, setAttachment] = useState<Attachment | null>(null)
  const uploadFile = useUploadFile()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const uploading = uploadFile.isPending
  const canSend =
    !disabled && (text.trim().length > 0 || !!attachment?.result) && !uploading

  function clearAttachment() {
    setAttachment(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  async function onFileSelected(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setAttachment({ file })
    try {
      const result = await uploadFile.mutateAsync(file)
      setAttachment({ file, result })
    } catch (err) {
      setAttachment({
        file,
        error: err instanceof Error ? err.message : 'Upload failed.',
      })
    }
  }

  function buildMessage(trimmedText: string): string {
    if (!attachment?.result) return trimmedText
    const { md_path, summary, tags } = attachment.result
    const header = summary
      ? `[Attached: ${md_path}. Summary: ${summary}]`
      : `[Attached: ${md_path}]`
    const tagLine = tags.length ? `Tags: ${tags.join(', ')}` : ''
    const parts = [header]
    if (tagLine) parts.push(tagLine)
    if (trimmedText) parts.push('', trimmedText)
    return parts.join('\n')
  }

  function submit() {
    if (!canSend) return
    const trimmed = text.trim()
    onSend(buildMessage(trimmed))
    setText('')
    clearAttachment()
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="space-y-2">
      {attachment && (
        <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm">
          <Paperclip size={14} className="flex-shrink-0 text-gray-500" />
          <div className="flex-1 min-w-0">
            <div className="truncate font-medium">{attachment.file.name}</div>
            {uploading && (
              <div className="text-xs text-gray-500 flex items-center gap-1">
                <Loader2 size={10} className="animate-spin" />
                Uploading and summarizing…
              </div>
            )}
            {attachment.error && (
              <div className="text-xs text-red-600">{attachment.error}</div>
            )}
            {attachment.result && (
              <div className="text-xs text-gray-500 truncate">
                {attachment.result.tags.length > 0
                  ? attachment.result.tags.map((t) => `#${t}`).join(' ')
                  : 'Summarized.'}
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={clearAttachment}
            className="flex-shrink-0 text-gray-400 hover:text-gray-700"
            aria-label="Remove attachment"
          >
            <X size={16} />
          </button>
        </div>
      )}

      <div className="flex gap-2 items-end">
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT}
          onChange={onFileSelected}
          hidden
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || uploading || !!attachment}
          className="flex-shrink-0 rounded-lg border border-gray-300 text-gray-500 hover:bg-gray-50 hover:text-gray-800 p-2 transition disabled:opacity-40"
          aria-label="Attach a file"
          title="Attach PDF, DOCX, TXT, MD, or HTML"
        >
          <Paperclip size={18} />
        </button>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder ?? 'Send a message…'}
          rows={2}
          className="flex-1 border rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/40 text-base md:text-sm"
        />
        <button
          type="button"
          onClick={submit}
          disabled={!canSend}
          className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 transition"
        >
          Send
        </button>
      </div>
    </div>
  )
}
