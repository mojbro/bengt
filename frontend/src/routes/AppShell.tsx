import { Outlet } from 'react-router-dom'

import Sidebar from '../components/Sidebar'

export default function AppShell() {
  return (
    <div className="flex h-full bg-white">
      <aside className="hidden md:block w-64 border-r bg-gray-50">
        <Sidebar />
      </aside>
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
