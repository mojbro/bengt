import { useQuery } from '@tanstack/react-query'

type Health = { status: string; llm_provider: string }

async function fetchHealth(): Promise<Health> {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export default function App() {
  const { data, error, isLoading } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
  })

  return (
    <main style={{ fontFamily: 'system-ui', padding: '2rem', maxWidth: 640, margin: '0 auto' }}>
      <h1>bengt</h1>
      <p>Personal AI assistant. Scaffold is alive.</p>
      <section>
        <h2>Backend health</h2>
        {isLoading && <p>Checking…</p>}
        {error && <pre style={{ color: 'crimson' }}>{String(error)}</pre>}
        {data && <pre>{JSON.stringify(data, null, 2)}</pre>}
      </section>
    </main>
  )
}
