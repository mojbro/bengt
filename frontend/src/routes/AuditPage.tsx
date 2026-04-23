import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useAuditRecent, useBudget, type AuditEntryOut } from '../hooks/useAudit'

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: 'short',
    timeStyle: 'medium',
  })
}

function formatCost(usd: number): string {
  if (usd === 0) return '—'
  if (usd < 0.001) return `$${(usd * 1000).toFixed(3)}m`
  return `$${usd.toFixed(4)}`
}

function describe(entry: AuditEntryOut): string {
  const d = entry.data as Record<string, unknown>
  if (entry.kind === 'llm_call') {
    const model = (d.model as string) ?? '?'
    const inp = d.input_tokens ?? '?'
    const out = d.output_tokens ?? '?'
    return `${model} — ${inp} in, ${out} out`
  }
  if (entry.kind === 'tool_invocation') {
    const name = (d.name as string) ?? '?'
    const err = d.error ? ' (error)' : ''
    const args = d.arguments as Record<string, unknown> | undefined
    const argPreview = args
      ? Object.entries(args)
          .map(([k, v]) => {
            const s = typeof v === 'string' ? v : JSON.stringify(v)
            return `${k}=${s.length > 40 ? s.slice(0, 40) + '…' : s}`
          })
          .join(', ')
      : ''
    return `${name}(${argPreview})${err}`
  }
  return entry.kind
}

export default function AuditPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const urlConvId = searchParams.get('conversation_id') || ''
  const [filter, setFilter] = useState<string>(urlConvId)

  const activeFilter = urlConvId.trim() || undefined
  const entries = useAuditRecent(100, activeFilter)
  const budget = useBudget()

  function applyFilter(value: string) {
    const trimmed = value.trim()
    const next = new URLSearchParams(searchParams)
    if (trimmed) next.set('conversation_id', trimmed)
    else next.delete('conversation_id')
    setSearchParams(next, { replace: true })
  }

  return (
    <div className="h-full overflow-auto bg-white">
      <header className="border-b px-6 py-4">
        <h1 className="text-xl font-medium">Audit</h1>
        <p className="text-sm text-gray-500 mt-1">
          Every LLM call and tool invocation, newest first. Refreshes every
          10 seconds.
        </p>
      </header>

      <div className="px-6 py-4 border-b bg-gray-50">
        {budget.data ? (
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm">
            <div>
              <span className="text-gray-500">Today: </span>
              <span
                className={`font-mono ${
                  budget.data.exceeded ? 'text-red-600 font-bold' : ''
                }`}
              >
                ${budget.data.spent_usd.toFixed(4)}
              </span>
              <span className="text-gray-400"> / ${budget.data.cap_usd.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-gray-500">Remaining: </span>
              <span className="font-mono">
                ${budget.data.remaining_usd.toFixed(4)}
              </span>
            </div>
            {budget.data.exceeded && (
              <span className="text-red-600 font-medium">
                Budget exceeded — agent calls are refused until UTC midnight.
              </span>
            )}
          </div>
        ) : (
          <p className="text-xs text-gray-400">Loading budget…</p>
        )}
      </div>

      <div className="px-6 py-3 border-b">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            applyFilter(filter)
          }}
          className="flex items-center gap-2"
        >
          <label className="text-xs text-gray-500 whitespace-nowrap">
            Filter by conversation id:
          </label>
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="conv-uuid…"
            className="flex-1 border rounded px-2 py-1 text-sm font-mono min-w-0"
          />
          <button
            type="submit"
            className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg px-3 py-1 transition"
          >
            Filter
          </button>
          {activeFilter && (
            <button
              type="button"
              onClick={() => {
                setFilter('')
                applyFilter('')
              }}
              className="text-xs text-gray-500 hover:underline"
            >
              Clear
            </button>
          )}
        </form>
        {activeFilter && (
          <p className="mt-2 text-xs text-gray-500">
            Showing activity for conversation{' '}
            <code className="bg-gray-100 px-1 py-0.5 rounded">{activeFilter}</code>
            {' '}·{' '}
            <Link
              to={`/conversations/${activeFilter}`}
              className="text-blue-700 hover:underline"
            >
              open this conversation
            </Link>
          </p>
        )}
      </div>

      <div className="p-6">
        {entries.isLoading && (
          <p className="text-sm text-gray-500">Loading…</p>
        )}
        {entries.data?.length === 0 && (
          <p className="text-sm text-gray-500">
            {activeFilter
              ? 'No activity logged against this conversation yet.'
              : 'No activity yet.'}
          </p>
        )}
        {entries.data && entries.data.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-gray-400 border-b">
              <tr>
                <th className="py-2 pr-4 font-medium whitespace-nowrap">When</th>
                <th className="py-2 pr-4 font-medium">Kind</th>
                <th className="py-2 pr-4 font-medium">Detail</th>
                <th className="py-2 font-medium text-right whitespace-nowrap">Cost</th>
              </tr>
            </thead>
            <tbody>
              {entries.data.map((e) => (
                <tr key={e.id} className="border-b last:border-b-0 align-top">
                  <td className="py-2 pr-4 whitespace-nowrap text-gray-500 font-mono text-xs">
                    {formatTime(e.timestamp)}
                  </td>
                  <td className="py-2 pr-4 whitespace-nowrap">
                    <span
                      className={`text-xs rounded px-1.5 py-0.5 ${
                        e.kind === 'llm_call'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {e.kind === 'llm_call' ? 'LLM' : 'TOOL'}
                    </span>
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs break-all">
                    {describe(e)}
                  </td>
                  <td className="py-2 text-right whitespace-nowrap font-mono text-xs">
                    {formatCost(e.cost_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
