import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { CreditCard, MessageSquare } from 'lucide-react'

export function AppShell({ title, subtitle, children }) {
  const location = useLocation()
  const navItems = [
    { to: '/upload', label: 'Upload', icon: CreditCard },
    { to: '/dashboard', label: 'Dashboard', icon: CreditCard },
    { to: '/transactions', label: 'Transactions', icon: CreditCard },
    { to: '/assistant', label: 'Chat', icon: MessageSquare },
  ]

  return (
    <main className="min-h-screen bg-cream text-slate-900">
      <div className="border-b border-slate-200 bg-white/90 backdrop-blur sticky top-0 z-30">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between gap-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-orange-500/10 text-orange-600 flex items-center justify-center shadow-sm">
              <CreditCard size={20} />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-gray-400 font-semibold">AI Money Coach</p>
              <h1 className="text-base font-bold tracking-tight text-slate-900">Budget Assistant</h1>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-2 rounded-full bg-slate-100/80 px-2 py-2 shadow-sm">
            {navItems.map((item) => {
              const isActive = location.pathname === item.to
              const Icon = item.icon
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition duration-200 ease-out ${
                    isActive
                      ? 'bg-slate-900 text-white shadow-sm'
                      : 'text-slate-600 hover:bg-white hover:text-slate-900 hover:shadow-sm'
                  }`}
                >
                  <Icon size={14} />
                  {item.label}
                </Link>
              )
            })}
          </nav>
        </div>
      </div>

      <div className="bg-cream">
        <div className="max-w-6xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
          <div className="mb-8">
            <p className="text-xs uppercase tracking-[0.3em] text-orange-500 font-semibold">{title}</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900">{subtitle}</h2>
          </div>
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="space-y-6"
          >
            {children}
          </motion.div>
        </div>
      </div>
    </main>
  )
}
