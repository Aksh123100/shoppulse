import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getOpportunities, getCustomerStats } from '../lib/api'
import { formatRupees, urgencyLabel } from '../lib/utils'
import { ArrowRight, RefreshCw, TrendingUp, Users, AlertTriangle } from 'lucide-react'

export default function OpportunityFeed() {
  const [opportunities, setOpportunities] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([getOpportunities(), getCustomerStats()]).then(([oppRes, statsRes]) => {
      setOpportunities(oppRes.data.opportunities || [])
      setStats(statsRes.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const totalAtStake = opportunities.reduce((sum, o) => sum + o.revenue_at_stake, 0)

  return (
    <div className="flex-1 overflow-y-auto p-8 scrollbar-thin">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="font-display text-3xl font-bold text-cream">
            Good morning. <span className="text-gilt">Here's what matters today.</span>
          </h1>
          <p className="text-roast-300 mt-1 text-sm">
            AI has scanned your 500 customers and found {opportunities.length} revenue opportunities.
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); getOpportunities().then(r => { setOpportunities(r.data.opportunities); setLoading(false) }) }}
          className="btn-ghost flex items-center gap-2"
        >
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="card">
            <p className="stat-label mb-1">Total Customers</p>
            <p className="stat-value">{stats.total_customers.toLocaleString()}</p>
          </div>
          <div className="card">
            <p className="stat-label mb-1">Revenue At Stake</p>
            <p className="stat-value rupee">{formatRupees(totalAtStake)}</p>
          </div>
          <div className="card">
            <p className="stat-label mb-1">At Risk</p>
            <p className="stat-value text-orange-400">{(stats.stage_breakdown?.at_risk || 0).toLocaleString()}</p>
          </div>
          <div className="card">
            <p className="stat-label mb-1">Loyal</p>
            <p className="stat-value text-emerald-400">{(stats.stage_breakdown?.loyal || 0).toLocaleString()}</p>
          </div>
        </div>
      )}

      {/* Opportunity Cards */}
      <div className="space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2 h-2 rounded-full bg-gilt live-dot" />
          <p className="text-xs text-roast-400 uppercase tracking-wider font-medium">Live Opportunities — AI Ranked by Revenue</p>
        </div>

        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="card animate-pulse h-40 bg-roast-700" />
            ))}
          </div>
        ) : opportunities.length === 0 ? (
          <div className="card text-center py-16">
            <TrendingUp size={32} className="mx-auto text-roast-500 mb-3" />
            <p className="text-roast-300">No opportunities right now. Check back after seeding data.</p>
          </div>
        ) : (
          opportunities.map((opp, i) => (
            <OpportunityCard
              key={opp.id}
              opp={opp}
              rank={i + 1}
              onAct={() => navigate('/campaigns/new', { state: { opportunity: opp } })}
            />
          ))
        )}
      </div>
    </div>
  )
}

function OpportunityCard({ opp, rank, onAct }) {
  const urgencyStyles = {
    critical: 'border-red-700 bg-red-950/20',
    high: 'border-orange-700 bg-orange-950/20',
    medium: 'border-yellow-800 bg-yellow-950/10',
  }

  return (
    <div className={`rounded-xl border p-6 transition-all hover:border-gilt/50 ${urgencyStyles[opp.urgency] || 'border-roast-700 bg-roast-800'}`}>
      <div className="flex items-start justify-between gap-6">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-xs font-mono text-roast-500">#{rank}</span>
            <span className={`badge ${
              opp.urgency === 'critical' ? 'badge-critical' :
              opp.urgency === 'high' ? 'badge-high' : 'badge-medium'
            }`}>
              {urgencyLabel(opp.urgency)}
            </span>
            <span className="badge bg-roast-700 text-roast-300 border-roast-600">
              {opp.opportunity_type}
            </span>
          </div>

          <h3 className="text-lg font-display font-semibold text-cream mb-1">
            {opp.title}
          </h3>
          <p className="text-roast-300 text-sm mb-4 text-balance">
            {opp.subtitle}
          </p>

          <div className="flex items-center gap-6 text-sm">
            <div>
              <p className="stat-label">Revenue at stake</p>
              <p className="text-xl font-display font-bold text-gilt mt-0.5">
                {formatRupees(opp.revenue_at_stake)}
              </p>
            </div>
            <div>
              <p className="stat-label">Customers</p>
              <p className="text-xl font-display font-bold text-cream mt-0.5">
                {opp.customer_count}
              </p>
            </div>
          </div>

          {opp.window_note && (
            <div className="flex items-start gap-2 mt-4 p-3 bg-roast-900/60 rounded-lg">
              <AlertTriangle size={13} className="text-gilt mt-0.5 flex-shrink-0" />
              <p className="text-xs text-roast-300">{opp.window_note}</p>
            </div>
          )}
        </div>

        <button
          onClick={onAct}
          className="flex-shrink-0 flex items-center gap-2 bg-gilt text-roast-900 font-semibold px-5 py-3 rounded-xl hover:bg-espresso-400 transition-colors text-sm whitespace-nowrap"
        >
          {opp.cta}
          <ArrowRight size={15} />
        </button>
      </div>
    </div>
  )
}
