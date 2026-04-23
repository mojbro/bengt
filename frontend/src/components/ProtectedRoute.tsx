import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../hooks/useAuth'

export default function ProtectedRoute() {
  const { data, isLoading, isError } = useAuth()
  if (isLoading) {
    return <div className="p-8 text-gray-500">Loading…</div>
  }
  if (isError || !data?.authed) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
