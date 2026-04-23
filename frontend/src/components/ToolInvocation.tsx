type Props = {
  name: string
  args: Record<string, unknown>
  result?: string
  error?: boolean
  pending?: boolean
}

export default function ToolInvocation({ name, args, result, error, pending }: Props) {
  const argsPreview = Object.entries(args)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')

  const border = error
    ? 'border-red-400'
    : pending
      ? 'border-yellow-400 animate-pulse'
      : 'border-gray-300'

  return (
    <div
      className={`text-xs text-gray-600 font-mono border-l-2 pl-2 py-1 bg-gray-50 ${border}`}
    >
      <div>
        <span className="font-semibold text-gray-700">{name}</span>
        {argsPreview && <span className="text-gray-500">({argsPreview})</span>}
      </div>
      {result && (
        <div
          className={`mt-1 whitespace-pre-wrap break-words ${
            error ? 'text-red-600' : 'text-gray-500'
          }`}
        >
          {result.length > 400 ? `${result.slice(0, 400)}…` : result}
        </div>
      )}
    </div>
  )
}
