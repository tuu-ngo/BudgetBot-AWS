import React from 'react'

export function PillButton({ children, className = '', ...props }) {
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center rounded-full bg-black px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-900 ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
