import { NavLink } from 'react-router-dom'

const tabs: { to: string; label: string; end?: boolean }[] = [
  { to: '/', label: 'Chat', end: true },
  { to: '/files', label: 'Files' },
  { to: '/scheduled', label: 'Scheduled' },
]

export default function BottomNav() {
  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 z-10 bg-white border-t flex"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          end={t.end}
          className={({ isActive }) =>
            `flex-1 text-center py-3 text-sm ${
              isActive ? 'text-black font-medium' : 'text-gray-500'
            }`
          }
        >
          {t.label}
        </NavLink>
      ))}
    </nav>
  )
}
