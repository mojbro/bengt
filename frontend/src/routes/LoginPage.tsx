import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { useAuth, useLogin } from '../hooks/useAuth'

export default function LoginPage() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const { data: auth } = useAuth()
  const login = useLogin()

  if (auth?.authed) {
    // Already logged in — don't sit on /login.
    navigate('/', { replace: true })
    return null
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setError(null)
    try {
      await login.mutateAsync(password)
      navigate('/', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Wrong password.')
      } else {
        setError(err instanceof Error ? err.message : 'Login failed.')
      }
    }
  }

  return (
    <div className="min-h-full flex items-center justify-center bg-gray-100 p-4">
      <form
        onSubmit={onSubmit}
        className="bg-white p-8 rounded-lg shadow-sm w-full max-w-sm space-y-4 border"
      >
        <div>
          <h1 className="text-2xl font-semibold">bengt</h1>
          <p className="text-sm text-gray-500">Sign in to continue.</p>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-black/20"
            autoComplete="current-password"
          />
        </div>
        {error && (
          <p className="text-red-600 text-sm" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={login.isPending || !password}
          className="w-full bg-black text-white rounded py-2 text-sm font-medium disabled:opacity-50"
        >
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
