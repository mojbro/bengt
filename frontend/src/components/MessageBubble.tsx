import type { MessageOut } from '../hooks/useConversations'

import Markdown from './Markdown'
import ToolInvocation from './ToolInvocation'

type Props = {
  message: MessageOut
  // For tool-role messages, lookup by tool_call_id to show result next to call.
  toolResultsById?: Map<string, { result: string; error: boolean }>
}

export default function MessageBubble({ message, toolResultsById }: Props) {
  if (message.role === 'system' || message.role === 'tool') return null

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="bg-indigo-600 text-white rounded-2xl px-4 py-2 max-w-[75%] whitespace-pre-wrap break-words">
          {message.content}
        </div>
      </div>
    )
  }

  // assistant
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-2 w-full">
        {message.tool_calls?.map((tc) => {
          const result = toolResultsById?.get(tc.id)
          return (
            <ToolInvocation
              key={tc.id}
              name={tc.name}
              args={tc.arguments}
              result={result?.result}
              error={result?.error}
            />
          )
        })}
        {message.content && (
          <div className="bg-gray-100 rounded-2xl px-4 py-2 break-words">
            <Markdown>{message.content}</Markdown>
          </div>
        )}
      </div>
    </div>
  )
}
