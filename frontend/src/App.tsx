import { useEffect, useState } from 'react'

type Health = { status: string; llm_provider: string }

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e) => setError(String(e)))
  }, [])

  return (
    <main style={{ fontFamily: 'system-ui', padding: '2rem', maxWidth: 640, margin: '0 auto' }}>
      <h1>bengt</h1>
      <p>Personal AI assistant. Scaffold is alive.</p>
      <section>
        <h2>Backend health</h2>
        {error && <pre style={{ color: 'crimson' }}>{error}</pre>}
        {health && <pre>{JSON.stringify(health, null, 2)}</pre>}
        {!error && !health && <p>Checking…</p>}
      </section>
    </main>
  )
}
