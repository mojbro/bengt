import type { StreamingTurn } from '../hooks/useChatStream'

import Markdown from './Markdown'
import ToolInvocation from './ToolInvocation'

export default function StreamingMessage({ turn }: { turn: StreamingTurn }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-2 w-full">
        {turn.tools.map((tool) => (
          <ToolInvocation
            key={tool.call_id}
            name={tool.name}
            args={tool.arguments}
            result={tool.result}
            error={tool.error}
            pending={tool.result === undefined}
          />
        ))}
        {(turn.text || turn.tools.length === 0) && (
          <div className="bg-gray-100 rounded-2xl px-4 py-2 break-words">
            {turn.text ? <Markdown>{turn.text}</Markdown> : null}
            <span className="inline-block w-1.5 h-4 ml-0.5 align-middle bg-gray-400 animate-pulse" />
          </div>
        )}
      </div>
    </div>
  )
}
