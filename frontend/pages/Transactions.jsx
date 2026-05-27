import React, { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Search,
  ChevronLeft,
  ChevronRight,
  FileText,
  ArrowUpDown,
  X,
  Filter,
} from 'lucide-react'
import { AppShell } from '../components/app/AppShell'
import {
  formatVND,
  categoryColors,
  categoryOptions,
  confidencePill,
} from '../lib/mockData'
import { api, normalizeTransaction } from '../lib/api'
const PAGE_SIZE = 8
export function Transactions() {
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [savingId, setSavingId] = useState('')
  const [search, setSearch] = useState('')
  const [selectedCats, setSelectedCats] = useState(new Set())
  const [txType, setTxType] = useState('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sortKey, setSortKey] = useState('date')
  const [sortDesc, setSortDesc] = useState(true)
  const [page, setPage] = useState(1)

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
        setError(err.message || 'Could not load transactions.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const updateCategory = async (transactionId, category) => {
    setSavingId(transactionId)
    setError('')
    try {
      const result = await api.updateTransactionCategory(transactionId, category)
      const updated = normalizeTransaction(result.transaction)
      setTransactions((prev) =>
        prev.map((txn) => (txn.id === transactionId ? updated : txn)),
      )
    } catch (err) {
      setError(err.message || 'Could not update category.')
    } finally {
      setSavingId('')
    }
  }

  const toggleCat = (cat) => {
    setSelectedCats((prev) => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
    setPage(1)
  }
  const filtered = useMemo(() => {
    let result = transactions
    if (search.trim()) {
      const q = search.toLowerCase()
      result = result.filter(
        (t) =>
          t.description.toLowerCase().includes(q) ||
          Math.abs(t.amount).toString().includes(q),
      )
    }
    if (selectedCats.size > 0) {
      result = result.filter((t) => selectedCats.has(t.category))
    }
    if (txType !== 'all') {
      result = result.filter((t) =>
        txType === 'income' ? t.amount > 0 : t.amount < 0,
      )
    }
    if (dateFrom) {
      result = result.filter((t) => t.rawDate.slice(0, 10) >= dateFrom)
    }
    if (dateTo) {
      result = result.filter((t) => t.rawDate.slice(0, 10) <= dateTo)
    }
    result = [...result].sort((a, b) => {
      let cmp = 0
      if (sortKey === 'date') cmp = a.rawDate.localeCompare(b.rawDate)
      else if (sortKey === 'amount')
        cmp = Math.abs(a.amount) - Math.abs(b.amount)
      else if (sortKey === 'description')
        cmp = a.description.localeCompare(b.description)
      return sortDesc ? -cmp : cmp
    })
    return result
  }, [transactions, search, selectedCats, txType, dateFrom, dateTo, sortKey, sortDesc])
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paginated = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const toggleSort = (key) => {
    if (sortKey === key) setSortDesc(!sortDesc)
    else {
      setSortKey(key)
      setSortDesc(true)
    }
  }
  const clearFilters = () => {
    setSearch('')
    setSelectedCats(new Set())
    setTxType('all')
    setDateFrom('')
    setDateTo('')
    setPage(1)
  }
  const hasActiveFilters =
    search || selectedCats.size > 0 || txType !== 'all' || dateFrom || dateTo
  return (
    <AppShell
      title="Transactions"
      subtitle="Search, filter, and explore every transaction in your statement."
    >
      {loading && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-5 text-sm text-gray-500 mb-6">
          Loading transactions...
        </div>
      )}
      {error && (
        <div className="bg-red-50 rounded-2xl border border-red-100 p-5 text-sm text-red-700 mb-6">
          {error}
        </div>
      )}
      {/* Filters Bar */}
      <motion.div
        initial={{
          opacity: 0,
          y: 10,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        className="bg-white rounded-3xl border border-gray-100 shadow-card p-5 mb-6"
      >
        {/* Search + Type */}
        <div className="flex flex-col md:flex-row gap-3 mb-4">
          <div className="relative flex-1">
            <Search
              size={14}
              className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              placeholder="Search by description or amount..."
              className="w-full pl-11 pr-4 py-2.5 bg-cream rounded-full text-sm outline-none focus:ring-2 focus:ring-orange-400/40 transition-shadow"
            />
          </div>
          <div className="flex items-center gap-2">
            <div className="bg-cream rounded-full p-1 flex">
              {[
                {
                  v: 'all',
                  label: 'All',
                },
                {
                  v: 'income',
                  label: 'Income',
                },
                {
                  v: 'expense',
                  label: 'Expense',
                },
              ].map((t) => (
                <button
                  key={t.v}
                  onClick={() => {
                    setTxType(t.v)
                    setPage(1)
                  }}
                  className={`px-4 py-1.5 rounded-full text-xs font-medium transition-colors ${txType === t.v ? 'bg-black text-white' : 'text-gray-600 hover:text-black'}`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Date Range */}
        <div className="flex flex-col md:flex-row gap-3 mb-4">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-xs text-gray-500 font-medium w-12">From</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value)
                setPage(1)
              }}
              className="flex-1 px-3 py-2 bg-cream rounded-full text-xs outline-none focus:ring-2 focus:ring-orange-400/40"
            />
          </div>
          <div className="flex items-center gap-2 flex-1">
            <span className="text-xs text-gray-500 font-medium w-12">To</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value)
                setPage(1)
              }}
              className="flex-1 px-3 py-2 bg-cream rounded-full text-xs outline-none focus:ring-2 focus:ring-orange-400/40"
            />
          </div>
        </div>

        {/* Categories */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 text-xs text-gray-500 font-medium mr-1">
            <Filter size={12} />
            Categories:
          </div>
          {categoryOptions.map((cat) => {
            const active = selectedCats.has(cat)
            return (
              <button
                key={cat}
                onClick={() => toggleCat(cat)}
                className={`px-3 py-1 rounded-full text-[11px] font-medium transition-colors ${active ? 'text-white' : 'text-gray-600 hover:text-black bg-cream'}`}
                style={
                  active
                    ? {
                        backgroundColor: categoryColors[cat] || '#71717A',
                      }
                    : {}
                }
              >
                {cat}
              </button>
            )
          })}
          {hasActiveFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 px-3 py-1 text-[11px] font-medium text-red-600 hover:bg-red-50 rounded-full transition-colors ml-auto"
            >
              <X size={11} /> Clear
            </button>
          )}
        </div>
      </motion.div>

      {/* Results count */}
      <div className="flex items-center justify-between mb-3 px-1">
        <p className="text-xs text-gray-500">
          Showing{' '}
          <span className="font-semibold text-gray-900">
            {paginated.length}
          </span>{' '}
          of{' '}
          <span className="font-semibold text-gray-900">{filtered.length}</span>{' '}
          transactions
        </p>
      </div>

      {/* Data Table */}
      <motion.div
        initial={{
          opacity: 0,
        }}
        animate={{
          opacity: 1,
        }}
        className="bg-white rounded-3xl border border-gray-100 shadow-card overflow-hidden"
      >
        {/* Header */}
        <div className="grid grid-cols-12 gap-4 px-6 py-3 bg-gray-50 text-[10px] font-bold uppercase tracking-wider text-gray-500">
          <button
            onClick={() => toggleSort('date')}
            className="col-span-2 text-left flex items-center gap-1 hover:text-black transition-colors"
          >
            Date{' '}
            <ArrowUpDown
              size={10}
              className={sortKey === 'date' ? 'text-orange-500' : ''}
            />
          </button>
          <button
            onClick={() => toggleSort('description')}
            className="col-span-5 text-left flex items-center gap-1 hover:text-black transition-colors"
          >
            Description{' '}
            <ArrowUpDown
              size={10}
              className={sortKey === 'description' ? 'text-orange-500' : ''}
            />
          </button>
          <div className="col-span-2">Category</div>
          <button
            onClick={() => toggleSort('amount')}
            className="col-span-3 text-right flex items-center justify-end gap-1 hover:text-black transition-colors"
          >
            Amount{' '}
            <ArrowUpDown
              size={10}
              className={sortKey === 'amount' ? 'text-orange-500' : ''}
            />
          </button>
        </div>

        {/* Rows */}
        <div className="divide-y divide-gray-50">
          {paginated.length === 0 ? (
            <div className="p-16 text-center">
              <Search size={28} className="mx-auto text-gray-300 mb-3" />
              <p className="text-sm font-medium text-gray-500">
                No transactions match your filters
              </p>
              <button
                onClick={clearFilters}
                className="text-xs text-orange-600 hover:text-orange-700 mt-2"
              >
                Clear filters
              </button>
            </div>
          ) : (
            paginated.map((t, i) => {
              const conf = confidencePill(t.confidence)
              return (
                <motion.div
                  key={t.id}
                  initial={{
                    opacity: 0,
                    y: 5,
                  }}
                  animate={{
                    opacity: 1,
                    y: 0,
                  }}
                  transition={{
                    delay: i * 0.02,
                  }}
                  className="grid grid-cols-12 gap-4 px-6 py-4 items-center hover:bg-gray-50/50 transition-colors"
                >
                  <div className="col-span-2 text-xs font-medium text-gray-700">
                    {t.date}
                  </div>
                  <div className="col-span-5 min-w-0 flex items-center gap-3">
                    <div
                      className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{
                        backgroundColor: `${categoryColors[t.category] || '#71717A'}20`,
                        color: categoryColors[t.category] || '#71717A',
                      }}
                    >
                      <FileText size={12} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {t.description}
                      </p>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${conf.color} inline-block mt-0.5`}
                      >
                        {conf.label}
                      </span>
                    </div>
                  </div>
                  <div className="col-span-2">
                    <select
                      value={t.category}
                      disabled={savingId === t.id}
                      onChange={(e) => updateCategory(t.id, e.target.value)}
                      className="max-w-full rounded-full border border-transparent px-2.5 py-1 text-[11px] font-medium outline-none transition focus:border-orange-300 disabled:opacity-60"
                      style={{
                        backgroundColor: `${categoryColors[t.category] || '#71717A'}20`,
                        color: categoryColors[t.category] || '#71717A',
                      }}
                    >
                      {categoryOptions.map((cat) => (
                        <option key={cat} value={cat}>
                          {cat}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-span-3 text-right">
                    <span
                      className={`text-sm font-semibold tabular-nums ${t.amount > 0 ? 'text-green-600' : 'text-gray-900'}`}
                    >
                      {formatVND(t.amount)}
                    </span>
                  </div>
                </motion.div>
              )
            })
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between p-4 border-t border-gray-100">
            <p className="text-xs text-gray-500">
              Page <span className="font-semibold text-gray-900">{page}</span>{' '}
              of {totalPages}
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="w-8 h-8 rounded-full hover:bg-gray-100 flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronLeft size={14} />
              </button>
              {Array.from(
                {
                  length: totalPages,
                },
                (_, i) => i + 1,
              ).map((p) => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`min-w-8 h-8 px-2 rounded-full text-xs font-medium transition-colors ${page === p ? 'bg-black text-white' : 'hover:bg-gray-100 text-gray-600'}`}
                >
                  {p}
                </button>
              ))}
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="w-8 h-8 rounded-full hover:bg-gray-100 flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </AppShell>
  )
}
