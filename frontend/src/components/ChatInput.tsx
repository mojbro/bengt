import { useState, type KeyboardEvent } from 'react'

type Props = {
  disabled: boolean
  onSend: (text: string) => void
  placeholder?: string
}

export default function ChatInput({ disabled, onSend, placeholder }: Props) {
  const [text, setText] = useState('')

  function submit() {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="flex gap-2 items-end">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder ?? 'Send a message…'}
        rows={2}
        className="flex-1 border rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-black/20 text-base md:text-sm"
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !text.trim()}
        className="bg-black text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
      >
        Send
      </button>
    </div>
  )
}
