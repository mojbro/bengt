import type { ReactNode } from 'react'

type Props = {
  onClick: () => void
  ariaLabel: string
  children: ReactNode
}

export default function FAB({ onClick, ariaLabel, children }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      // On mobile the bottom tab bar eats ~56px + safe area, so the FAB
      // parks a bit above that. On desktop the bottom nav is hidden so the
      // standard 24px offset is fine.
      className="fixed right-5 z-20 h-14 w-14 rounded-full bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg flex items-center justify-center transition active:scale-95"
      style={{
        bottom: 'calc(5rem + env(safe-area-inset-bottom))',
      }}
    >
      {children}
    </button>
  )
}
