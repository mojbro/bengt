import { useCancelJob, useScheduledJobs } from '../hooks/useScheduler'

function formatNextRun(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export default function ScheduledPage() {
  const jobs = useScheduledJobs()
  const cancel = useCancelJob()

  return (
    <div className="h-full overflow-auto bg-white">
      <header className="border-b px-4 md:px-6 py-4 sticky top-0 bg-white z-10">
        <h1 className="text-xl font-semibold">Scheduled</h1>
        <p className="text-sm text-gray-500 mt-1">
          Ask the agent to remind you of something and the reminder fires at
          the scheduled time into the Scheduled conversation.
        </p>
      </header>

      <div className="p-6">
        {jobs.isLoading && (
          <p className="text-sm text-gray-500">Loading…</p>
        )}
        {jobs.isError && (
          <p className="text-sm text-red-600">
            {jobs.error instanceof Error ? jobs.error.message : 'Failed to load.'}
          </p>
        )}
        {jobs.data && jobs.data.length === 0 && (
          <div className="text-center py-12 text-gray-500 text-sm">
            <p>No jobs scheduled yet.</p>
          </div>
        )}
        {jobs.data && jobs.data.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-gray-400 border-b">
              <tr>
                <th className="py-2 pr-4 font-medium">Next run</th>
                <th className="py-2 pr-4 font-medium">Instruction</th>
                <th className="py-2 pr-4 font-medium">ID</th>
                <th className="py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {jobs.data.map((job) => (
                <tr key={job.id} className="border-b last:border-b-0">
                  <td className="py-2 pr-4 whitespace-nowrap">
                    {formatNextRun(job.next_run)}
                  </td>
                  <td className="py-2 pr-4">{job.instruction || <span className="text-gray-400">—</span>}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-gray-500 truncate max-w-[12rem]">
                    {job.id}
                  </td>
                  <td className="py-2 text-right">
                    <button
                      onClick={() => cancel.mutate(job.id)}
                      disabled={cancel.isPending}
                      className="text-xs text-red-600 hover:underline disabled:opacity-40"
                    >
                      Cancel
                    </button>
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
