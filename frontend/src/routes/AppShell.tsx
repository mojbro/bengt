import { Outlet } from 'react-router-dom'

import BottomNav from '../components/BottomNav'
import Sidebar from '../components/Sidebar'

export default function AppShell() {
  return (
    <div className="h-full flex bg-white">
      <aside className="hidden md:block w-64 border-r bg-gray-50 shrink-0">
        <Sidebar />
      </aside>
      <main className="flex-1 min-w-0 overflow-hidden pb-[calc(3.25rem+env(safe-area-inset-bottom))] md:pb-0">
        <Outlet />
      </main>
      <BottomNav />
    </div>
  )
}
