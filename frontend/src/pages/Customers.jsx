import { useState, useEffect, useCallback } from 'react'
import { getCustomers, getCustomerStats } from '../lib/api'
import { formatRupees, lifecycleBadge, daysSince, channelIcon } from '../lib/utils'
import { Search, Filter } from 'lucide-react'

const STAGES = ['all', 'loyal', 'growing', 'new', 'at_risk', 'churned']

export default function Customers() {
  const [customers, setCustomers] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [stage, setStage] = useState('all')
  const [page, setPage] = useState(1)

  const fetchCustomers = useCallback(() => {
    setLoading(true)
    const params = { page, page_size: 50 }
    if (search) params.search = search
    if (stage !== 'all') params.lifecycle_stage = stage
    getCustomers(params).then(r => {
      setCustomers(r.data.customers || [])
      setTotal(r.data.total || 0)
      setLoading(false)
    })
  }, [search, stage, page])

  useEffect(() => {
    const t = setTimeout(fetchCustomers, 300)
    return () => clearTimeout(t)
  }, [fetchCustomers])

  return (
    <div className="flex-1 overflow-y-auto p-8 scrollbar-thin">
      <div className="mb-6">
        <h1 className="section-title mb-1">Customer Explorer</h1>
        <p className="text-roast-400 text-sm">Browse and filter your full customer base. {total.toLocaleString()} shoppers total.</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-6">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-roast-400" />
          <input
            type="text"
            placeholder="Search by name, phone, email..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            className="input w-full pl-9"
          />
        </div>

        <div className="flex gap-1">
          {STAGES.map(s => (
            <button
              key={s}
              onClick={() => { setStage(s); setPage(1) }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                stage === s
                  ? 'bg-gilt text-roast-900'
                  : 'bg-roast-800 text-roast-300 hover:bg-roast-700'
              }`}
            >
              {s === 'all' ? 'All' : s.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-roast-700">
              <th className="text-left px-5 py-3 stat-label">Customer</th>
              <th className="text-left px-5 py-3 stat-label">Stage</th>
              <th className="text-left px-5 py-3 stat-label">Channel</th>
              <th className="text-right px-5 py-3 stat-label">Spend</th>
              <th className="text-right px-5 py-3 stat-label">Orders</th>
              <th className="text-right px-5 py-3 stat-label">Last Purchase</th>
              <th className="text-right px-5 py-3 stat-label">Health</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array(10).fill(0).map((_, i) => (
                <tr key={i} className="border-b border-roast-700/50">
                  {Array(7).fill(0).map((_, j) => (
                    <td key={j} className="px-5 py-3">
                      <div className="h-4 bg-roast-700 rounded animate-pulse" />
                    </td>
                  ))}
                </tr>
              ))
            ) : customers.map(c => (
              <tr key={c.id} className="border-b border-roast-700/50 hover:bg-roast-700/30 transition-colors">
                <td className="px-5 py-3">
                  <p className="text-sm font-medium text-cream">{c.name}</p>
                  <p className="text-xs text-roast-400">{c.phone}</p>
                </td>
                <td className="px-5 py-3">
                  <span className={`badge border ${lifecycleBadge(c.lifecycle_stage)}`}>
                    {c.lifecycle_stage.replace('_', ' ')}
                  </span>
                </td>
                <td className="px-5 py-3 text-sm">
                  {channelIcon(c.channel_preference)} {c.channel_preference}
                </td>
                <td className="px-5 py-3 text-right text-sm font-medium text-gilt">
                  {formatRupees(c.total_spend)}
                </td>
                <td className="px-5 py-3 text-right text-sm text-roast-300">
                  {c.order_count}
                </td>
                <td className="px-5 py-3 text-right text-sm text-roast-300">
                  {c.last_purchase_date ? `${daysSince(c.last_purchase_date)}d ago` : '—'}
                </td>
                <td className="px-5 py-3 text-right">
                  <HealthBar score={c.health_score} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Pagination */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-roast-700">
          <p className="text-xs text-roast-400">
            Showing {((page - 1) * 50) + 1}–{Math.min(page * 50, total)} of {total}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary py-1 px-3 disabled:opacity-40"
            >
              Prev
            </button>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page * 50 >= total}
              className="btn-secondary py-1 px-3 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function HealthBar({ score }) {
  const color = score >= 70 ? 'bg-emerald-500' : score >= 40 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2 justify-end">
      <div className="w-16 h-1.5 bg-roast-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-xs text-roast-400 w-6 text-right">{score}</span>
    </div>
  )
}
