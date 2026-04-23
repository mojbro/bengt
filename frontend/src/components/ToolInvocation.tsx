import { useState } from 'react'

type Props = {
  name: string
  args: Record<string, unknown>
  result?: string
  error?: boolean
  pending?: boolean
}

function summarizeArgs(args: Record<string, unknown>, max: number): string {
  const parts = Object.entries(args).map(([k, v]) => {
    const s = typeof v === 'string' ? v : JSON.stringify(v)
    return `${k}=${s}`
  })
  const joined = parts.join(', ')
  return joined.length > max ? joined.slice(0, max) + '…' : joined
}

export default function ToolInvocation({
  name,
  args,
  result,
  error,
  pending,
}: Props) {
  const [expanded, setExpanded] = useState(false)

  const borderColor = error
    ? 'border-red-400'
    : pending
      ? 'border-yellow-400'
      : 'border-gray-300'

  const statusIcon = pending ? '•' : error ? '✗' : '✓'
  const statusColor = pending
    ? 'text-yellow-600 animate-pulse'
    : error
      ? 'text-red-600'
      : 'text-gray-400'

  const argsShort = summarizeArgs(args, 80)
  const hasArgs = Object.keys(args).length > 0

  return (
    <div className={`font-mono text-xs border-l-2 ${borderColor}`}>
      <button
        type="button"
        onClick={() => setExpanded((x) => !x)}
        className="flex items-center gap-1.5 w-full text-left hover:bg-gray-100 rounded px-1.5 py-1 min-w-0"
        aria-expanded={expanded}
      >
        <span className="text-gray-400 text-[10px] w-2.5 flex-shrink-0">
          {expanded ? '▾' : '▸'}
        </span>
        <span className={`${statusColor} flex-shrink-0`}>{statusIcon}</span>
        <span className="font-semibold text-gray-700 flex-shrink-0">{name}</span>
        {!expanded && argsShort && (
          <span className="text-gray-400 truncate">({argsShort})</span>
        )}
      </button>

      {expanded && (
        <div className="px-1.5 pb-2 pl-5 space-y-1.5">
          {hasArgs && (
            <pre className="text-[11px] text-gray-600 whitespace-pre-wrap break-words bg-gray-50 rounded px-2 py-1 max-h-40 overflow-auto">
              {JSON.stringify(args, null, 2)}
            </pre>
          )}
          {result !== undefined && (
            <pre
              className={`text-[11px] whitespace-pre-wrap break-words rounded px-2 py-1 max-h-64 overflow-auto ${
                error
                  ? 'bg-red-50 text-red-700'
                  : 'bg-gray-50 text-gray-700'
              }`}
            >
              {result}
            </pre>
          )}
          {pending && (
            <p className="text-[11px] text-gray-500 italic">Running…</p>
          )}
        </div>
      )}
    </div>
  )
}
