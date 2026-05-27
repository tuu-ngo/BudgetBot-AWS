import React, { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  Sparkles,
  FileText,
  ArrowRight,
  Upload,
  MessageSquare,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  PieChart as RPieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { AppShell } from '../components/app/AppShell'
import {
  formatVND,
  categoryColors,
  confidencePill,
} from '../lib/mockData'
import { api, normalizeTransaction } from '../lib/api'
import { PillButton } from '../components/landing/PillButton'
export function Dashboard() {
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    api
      .getTransactions()
      .then((data) => {
        if (!active) return
        setTransactions((data.transactions || []).map(normalizeTransaction))
      })
      .catch((err) => {
        if (!active) return
        setError(err.message || 'Could not load dashboard data.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const totalIncome = transactions
    .filter((t) => t.amount > 0)
    .reduce((s, t) => s + t.amount, 0)
  const totalExpense = Math.abs(
    transactions.filter((t) => t.amount < 0).reduce((s, t) => s + t.amount, 0),
  )
  const balance = totalIncome - totalExpense
  const byCategory = transactions
    .filter((t) => t.amount < 0)
    .reduce(
      (acc, t) => {
        acc[t.category] = (acc[t.category] || 0) + Math.abs(t.amount)
        return acc
      },
      {},
    )
  const pieData = Object.entries(byCategory)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({
      name,
      value,
      color: categoryColors[name] || '#71717A',
    }))
  const topCategory = pieData[0]
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-2.5 rounded-lg shadow-lg border border-gray-100 text-xs">
          <p className="font-semibold">{payload[0].name}</p>
          <p className="text-gray-600">{formatVND(-payload[0].value)}</p>
        </div>
      )
    }
    return null
  }
  return (
    <AppShell
      title="Financial Overview"
      subtitle="Your spending at a glance — based on your latest uploaded statement."
    >
      {loading && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-5 text-sm text-gray-500">
          Loading dashboard data...
        </div>
      )}
      {error && (
        <div className="bg-red-50 rounded-2xl border border-red-100 p-5 text-sm text-red-700">
          {error}
        </div>
      )}
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {[
          {
            label: 'Total Income',
            value: formatVND(totalIncome),
            icon: TrendingUp,
            color: 'text-green-600',
            bg: 'bg-green-50',
          },
          {
            label: 'Total Expense',
            value: formatVND(-totalExpense),
            icon: TrendingDown,
            color: 'text-orange-600',
            bg: 'bg-orange-50',
          },
          {
            label: 'Current Balance',
            value: formatVND(balance),
            icon: Wallet,
            color: 'text-blue-600',
            bg: 'bg-blue-50',
          },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{
              opacity: 0,
              y: 10,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              delay: i * 0.05,
            }}
            className="bg-white rounded-2xl border border-gray-100 shadow-card p-5"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                {stat.label}
              </span>
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center ${stat.bg} ${stat.color}`}
              >
                <stat.icon size={14} />
              </div>
            </div>
            <div className="text-2xl font-bold tracking-tight">
              {stat.value}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Shortcuts */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
        {[
          {
            to: '/upload',
            icon: Upload,
            label: 'Upload statement',
            desc: 'New CSV',
          },
          {
            to: '/transactions',
            icon: FileText,
            label: 'View transactions',
            desc: 'All details',
          },
          {
            to: '/assistant',
            icon: MessageSquare,
            label: 'Ask AI',
            desc: 'Chat coach',
          },
        ].map((sc, i) => (
          <motion.div
            key={sc.to}
            initial={{
              opacity: 0,
              y: 10,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              delay: 0.15 + i * 0.05,
            }}
          >
            <Link
              to={sc.to}
              className="group flex items-center gap-3 bg-white rounded-2xl border border-gray-100 shadow-card p-4 hover:border-orange-300 transition-colors"
            >
              <div className="w-10 h-10 rounded-xl bg-cream text-orange-600 flex items-center justify-center group-hover:bg-orange-500 group-hover:text-white transition-colors">
                <sc.icon size={16} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm truncate">{sc.label}</p>
                <p className="text-xs text-gray-500">{sc.desc}</p>
              </div>
              <ArrowRight
                size={14}
                className="text-gray-400 group-hover:text-orange-500 transition-colors"
              />
            </Link>
          </motion.div>
        ))}
      </div>

      {/* Chart + Insight */}
      <div className="grid lg:grid-cols-3 gap-6 mb-6">
        {/* Pie Chart */}
        <motion.div
          initial={{
            opacity: 0,
            y: 10,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          transition={{
            delay: 0.2,
          }}
          className="lg:col-span-2 bg-white rounded-3xl border border-gray-100 shadow-card p-6"
        >
          <div className="flex justify-between items-start mb-2">
            <div>
              <h3 className="font-bold text-gray-900">Spending by Category</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                {formatVND(-totalExpense)} total this period
              </p>
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-6 items-center mt-4">
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <RPieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={85}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </RPieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-2.5">
              {pieData.slice(0, 6).map((d, i) => {
                const pct = totalExpense > 0 ? Math.round((d.value / totalExpense) * 100) : 0
                return (
                  <motion.div
                    key={d.name}
                    initial={{
                      opacity: 0,
                      x: 10,
                    }}
                    animate={{
                      opacity: 1,
                      x: 0,
                    }}
                    transition={{
                      delay: 0.3 + i * 0.05,
                    }}
                    className="flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <div
                        className="w-2.5 h-2.5 rounded-sm flex-shrink-0"
                        style={{
                          backgroundColor: d.color,
                        }}
                      />
                      <span className="font-medium text-gray-700 truncate">
                        {d.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className="text-gray-500 tabular-nums">{pct}%</span>
                      <span className="font-semibold tabular-nums w-20 text-right">
                        {formatVND(-d.value)}
                      </span>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          </div>
        </motion.div>

        {/* AI Insight */}
        <motion.div
          initial={{
            opacity: 0,
            y: 10,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          transition={{
            delay: 0.25,
          }}
          className="bg-black text-white rounded-3xl p-6 relative overflow-hidden"
        >
          <div className="absolute -right-10 -top-10 w-32 h-32 rounded-full bg-orange-500/20 blur-2xl" />
          <div className="relative">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles size={14} className="text-orange-400" />
              <span className="text-[10px] uppercase tracking-widest text-orange-400 font-bold">
                AI Insight
              </span>
            </div>
            <p className="text-sm leading-relaxed mb-6">
              {topCategory ? (
                <>
                  You spend the most on{' '}
                  <strong className="text-orange-400">{topCategory.name}</strong>,
                  accounting for{' '}
                  <strong className="text-orange-400">
                    {totalExpense > 0 ? Math.round((topCategory.value / totalExpense) * 100) : 0}%
                  </strong>{' '}
                  of your total expenses.
                </>
              ) : (
                'Upload a statement to unlock AI spending insights.'
              )}
            </p>
            <Link
              to="/assistant"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-orange-400 hover:text-orange-300"
            >
              Ask AI for advice <ArrowRight size={12} />
            </Link>
          </div>
        </motion.div>
      </div>

      {/* Recent Transactions */}
      <motion.div
        initial={{
          opacity: 0,
          y: 10,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          delay: 0.3,
        }}
        className="bg-white rounded-3xl border border-gray-100 shadow-card overflow-hidden"
      >
        <div className="p-6 flex justify-between items-center border-b border-gray-100">
          <div>
            <h2 className="font-bold text-gray-900">Recent Transactions</h2>
            <p className="text-xs text-gray-500 mt-0.5">Last 8 transactions</p>
          </div>
          <Link
            to="/transactions"
            className="text-xs font-medium text-orange-600 hover:text-orange-700 flex items-center gap-1"
          >
            View all <ArrowRight size={12} />
          </Link>
        </div>
        <div className="divide-y divide-gray-50">
          {transactions.slice(0, 8).map((t, i) => {
            const conf = confidencePill(t.confidence)
            return (
              <motion.div
                key={t.id}
                initial={{
                  opacity: 0,
                  x: -10,
                }}
                animate={{
                  opacity: 1,
                  x: 0,
                }}
                transition={{
                  delay: 0.35 + i * 0.03,
                }}
                className="flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{
                      backgroundColor: `${categoryColors[t.category] || '#71717A'}20`,
                      color: categoryColors[t.category] || '#71717A',
                    }}
                  >
                    <FileText size={14} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {t.description}
                    </p>
                    <p className="text-xs text-gray-500">
                      {t.date} · {t.category}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${conf.color} hidden sm:inline-block`}
                  >
                    {conf.label}
                  </span>
                  <span
                    className={`text-sm font-semibold tabular-nums ${t.amount > 0 ? 'text-green-600' : 'text-gray-900'}`}
                  >
                    {formatVND(t.amount)}
                  </span>
                </div>
              </motion.div>
            )
          })}
        </div>
      </motion.div>
    </AppShell>
  )
}
