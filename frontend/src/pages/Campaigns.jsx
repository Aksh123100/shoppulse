import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getCampaigns } from '../lib/api'
import { formatRupees, formatPercent } from '../lib/utils'
import { BarChart3, ChevronRight, Plus } from 'lucide-react'

const STATUS_STYLES = {
  draft: 'bg-roast-700 text-roast-300',
  scheduled: 'bg-blue-900/50 text-blue-300',
  live: 'bg-emerald-900/50 text-emerald-300',
  completed: 'bg-roast-700 text-roast-400',
}

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    getCampaigns().then(r => {
      setCampaigns(r.data || [])
      setLoading(false)
    })
  }, [])

  const liveCampaigns = campaigns.filter(c => c.status === 'live')
  const completedCampaigns = campaigns.filter(c => c.status === 'completed')

  return (
    <div className="flex-1 overflow-y-auto p-8 scrollbar-thin">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="section-title mb-1">Campaigns</h1>
          <p className="text-roast-400 text-sm">{campaigns.length} total campaigns</p>
        </div>
        <button onClick={() => navigate('/campaigns/new')} className="btn-primary flex items-center gap-2">
          <Plus size={14} />
          New Campaign
        </button>
      </div>

      {liveCampaigns.length > 0 && (
        <div className="mb-8">
          <p className="text-xs text-roast-400 uppercase tracking-wider font-medium mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 live-dot" />
            Live Now
          </p>
          <div className="space-y-3">
            {liveCampaigns.map(c => <CampaignRow key={c.id} campaign={c} onClick={() => navigate(`/campaigns/${c.id}`)} />)}
          </div>
        </div>
      )}

      <div>
        <p className="text-xs text-roast-400 uppercase tracking-wider font-medium mb-3">Campaign History</p>
        {loading ? (
          <div className="space-y-3">
            {Array(5).fill(0).map((_, i) => <div key={i} className="card h-20 animate-pulse bg-roast-700" />)}
          </div>
        ) : (
          <div className="space-y-3">
            {completedCampaigns.map(c => <CampaignRow key={c.id} campaign={c} onClick={() => navigate(`/campaigns/${c.id}`)} />)}
          </div>
        )}
      </div>
    </div>
  )
}

function CampaignRow({ campaign: c, onClick }) {
  return (
    <div
      onClick={onClick}
      className="card cursor-pointer hover:border-roast-500 transition-all p-4 flex items-center gap-4"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 mb-1">
          <p className="font-medium text-cream text-sm truncate">{c.name}</p>
          <span className={`badge border-0 text-xs ${STATUS_STYLES[c.status] || 'bg-roast-700 text-roast-300'}`}>
            {c.status}
          </span>
        </div>
        <p className="text-xs text-roast-400">
          {c.total_customers} customers · {c.opportunity_type} · {c.created_at ? new Date(c.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }) : ''}
        </p>
      </div>

      {c.stats && c.status === 'completed' && (
        <div className="flex items-center gap-6 text-right text-xs">
          <div>
            <p className="stat-label">Open</p>
            <p className="text-sm font-medium text-cream">{formatPercent(c.stats.open_rate || 0)}</p>
          </div>
          <div>
            <p className="stat-label">Purchased</p>
            <p className="text-sm font-medium text-emerald-400">{c.stats.purchased || 0}</p>
          </div>
          <div>
            <p className="stat-label">Revenue</p>
            <p className="text-sm font-bold text-gilt">{formatRupees(c.estimated_revenue || 0)}</p>
          </div>
        </div>
      )}

      {c.status === 'live' && c.stats && (
        <div className="flex items-center gap-6 text-right text-xs">
          <div>
            <p className="stat-label">Sent</p>
            <p className="text-sm font-medium text-cream">{c.stats.sent || 0}</p>
          </div>
          <div>
            <p className="stat-label">Opened</p>
            <p className="text-sm font-medium text-blue-400">{c.stats.opened || 0}</p>
          </div>
        </div>
      )}

      <ChevronRight size={16} className="text-roast-500 flex-shrink-0" />
    </div>
  )
}
