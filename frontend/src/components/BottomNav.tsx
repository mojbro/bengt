import {
  CheckCircle2,
  Clock,
  FolderOpen,
  MessageSquare,
  type LucideIcon,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

type Tab = { to: string; label: string; Icon: LucideIcon; end?: boolean }

const tabs: Tab[] = [
  { to: '/', label: 'Chat', Icon: MessageSquare, end: true },
  { to: '/todos', label: 'Todos', Icon: CheckCircle2 },
  { to: '/files', label: 'Files', Icon: FolderOpen },
  { to: '/scheduled', label: 'Scheduled', Icon: Clock },
]

export default function BottomNav() {
  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-white border-t flex"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {tabs.map(({ to, label, Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-center py-2 text-[11px] transition ${
              isActive ? 'text-indigo-600' : 'text-gray-500 hover:text-gray-800'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Icon
                size={22}
                strokeWidth={isActive ? 2.25 : 1.75}
                className="mb-0.5"
              />
              <span className={isActive ? 'font-semibold' : ''}>{label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
