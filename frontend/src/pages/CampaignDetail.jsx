import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getCampaign, getCampaignLive } from '../lib/api'
import { formatRupees, formatPercent } from '../lib/utils'
import { ArrowLeft, TrendingUp, CheckCircle, XCircle, Eye, MousePointer, ShoppingBag } from 'lucide-react'

export default function CampaignDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [campaign, setCampaign] = useState(null)
  const [live, setLive] = useState(null)
  const [loading, setLoading] = useState(true)
  const intervalRef = useRef(null)

  useEffect(() => {
    getCampaign(id).then(r => {
      setCampaign(r.data)
      setLoading(false)
    })
    getCampaignLive(id).then(r => setLive(r.data))

    // Poll live stats every 3s if campaign is live
    intervalRef.current = setInterval(() => {
      getCampaignLive(id).then(r => {
        setLive(r.data)
        if (r.data.pending === 0 && r.data.sent === 0) {
          clearInterval(intervalRef.current)
        }
      })
    }, 3000)

    return () => clearInterval(intervalRef.current)
  }, [id])

  if (loading) {
    return (
      <div className="flex-1 p-8">
        <div className="space-y-4">
          {Array(3).fill(0).map((_, i) => <div key={i} className="card h-24 animate-pulse bg-roast-700" />)}
        </div>
      </div>
    )
  }

  if (!campaign) return <div className="flex-1 p-8 text-roast-400">Campaign not found.</div>

  const isLive = campaign.status === 'live'
  const isCompleted = campaign.status === 'completed'

  return (
    <div className="flex-1 overflow-y-auto p-8 scrollbar-thin">
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate('/campaigns')} className="btn-ghost p-2">
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="section-title">{campaign.name}</h1>
            {isLive && (
              <span className="badge bg-emerald-900/50 text-emerald-300 border-emerald-800 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 live-dot" />
                Live
              </span>
            )}
            {isCompleted && <span className="badge bg-roast-700 text-roast-400">Completed</span>}
          </div>
          <p className="text-xs text-roast-400 mt-0.5">
            {campaign.total_customers} customers · {campaign.opportunity_type} · Est. {formatRupees(campaign.estimated_revenue || 0)}
          </p>
        </div>
      </div>

      {/* Live stats */}
      {live && (
        <div className="grid grid-cols-6 gap-3 mb-6">
          <StatCard icon={<TrendingUp size={14} />} label="Sent" value={live.sent} color="text-cream" />
          <StatCard icon={<CheckCircle size={14} />} label="Delivered" value={live.delivered} color="text-blue-400"
            sub={live.sent > 0 ? `${formatPercent(live.delivery_rate)}` : null} />
          <StatCard icon={<XCircle size={14} />} label="Failed" value={live.failed} color="text-red-400" />
          <StatCard icon={<Eye size={14} />} label="Opened" value={live.opened} color="text-purple-400"
            sub={live.delivered > 0 ? `${formatPercent(live.open_rate)}` : null} />
          <StatCard icon={<MousePointer size={14} />} label="Clicked" value={live.clicked} color="text-yellow-400"
            sub={live.opened > 0 ? `${formatPercent(live.click_rate)}` : null} />
          <StatCard icon={<ShoppingBag size={14} />} label="Purchased" value={live.purchased} color="text-emerald-400"
            sub={live.clicked > 0 ? `${formatPercent(live.conversion_rate)}` : null} />
        </div>
      )}

      {/* AI Reasoning */}
      {campaign.ai_reasoning && (
        <div className="card mb-6">
          <p className="text-xs text-roast-400 uppercase tracking-wider font-medium mb-2">AI Reasoning</p>
          <p className="text-sm text-roast-200 leading-relaxed">{campaign.ai_reasoning}</p>
        </div>
      )}

      {/* Campaign Memory / Autopsy */}
      {isCompleted && campaign.memory && (
        <div className="card">
          <p className="text-xs text-roast-400 uppercase tracking-wider font-medium mb-4">Campaign Autopsy</p>
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div>
              <p className="stat-label">Open Rate</p>
              <p className="text-2xl font-display font-bold text-cream">{formatPercent(campaign.memory.open_rate)}</p>
            </div>
            <div>
              <p className="stat-label">Click Rate</p>
              <p className="text-2xl font-display font-bold text-cream">{formatPercent(campaign.memory.click_rate)}</p>
            </div>
            <div>
              <p className="stat-label">Conversion</p>
              <p className="text-2xl font-display font-bold text-cream">{formatPercent(campaign.memory.conversion_rate)}</p>
            </div>
            <div>
              <p className="stat-label">Revenue Recovered</p>
              <p className="text-2xl font-display font-bold text-gilt">{formatRupees(campaign.memory.revenue_recovered)}</p>
            </div>
          </div>

          {campaign.memory.learnings && (
            <div className="space-y-3">
              <LearningRow emoji="✅" label="What worked" text={campaign.memory.learnings.what_worked} />
              <LearningRow emoji="❌" label="What didn't" text={campaign.memory.learnings.what_didnt} />
              <LearningRow emoji="💡" label="Next time" text={campaign.memory.learnings.next_time} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StatCard({ icon, label, value, color, sub }) {
  return (
    <div className="card p-4">
      <div className={`flex items-center gap-1.5 mb-2 ${color}`}>
        {icon}
        <p className="stat-label" style={{ color: 'inherit', opacity: 0.8 }}>{label}</p>
      </div>
      <p className={`text-2xl font-display font-bold ${color}`}>{value ?? '—'}</p>
      {sub && <p className="text-xs text-roast-400 mt-0.5">{sub}</p>}
    </div>
  )
}

function LearningRow({ emoji, label, text }) {
  return (
    <div className="flex gap-3 p-3 bg-roast-900/60 rounded-lg">
      <span className="text-sm flex-shrink-0">{emoji}</span>
      <div>
        <p className="text-xs font-medium text-roast-400 mb-0.5">{label}</p>
        <p className="text-sm text-roast-200">{text}</p>
      </div>
    </div>
  )
}
