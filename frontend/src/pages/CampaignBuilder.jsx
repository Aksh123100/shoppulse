import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { previewSegment, createCampaign, sendCampaign } from '../lib/api'
import { formatRupees } from '../lib/utils'
import { Sparkles, Send, Users, ArrowLeft } from 'lucide-react'

// Day 1: Basic campaign builder shell.
// Day 2: This becomes the AI-powered campaign builder with the Thinking Agent.

export default function CampaignBuilder() {
  const location = useLocation()
  const navigate = useNavigate()
  const opportunity = location.state?.opportunity

  const [name, setName] = useState(opportunity ? `${opportunity.title} — ${new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}` : '')
  const [criteria, setCriteria] = useState(opportunity?.segment_criteria || {})
  const [preview, setPreview] = useState(null)
  const [previewing, setPreviewing] = useState(false)
  const [creating, setCreating] = useState(false)

  // Auto-preview if we came from an opportunity
  useEffect(() => {
    if (opportunity && Object.keys(criteria).length > 0) {
      handlePreview()
    }
  }, [])

  const handlePreview = async () => {
    setPreviewing(true)
    try {
      const r = await previewSegment(criteria)
      setPreview(r.data)
    } catch (e) {
      console.error(e)
    }
    setPreviewing(false)
  }

  const handleCreate = async () => {
    if (!name || !preview) return
    setCreating(true)
    try {
      // Build simple template messages for Day 1
      // Day 2: AI generates personalized messages per customer
      const messages = (preview.sample_customers || []).slice(0, 5).map(c => ({
        customer_id: c.id,
        channel: c.channel_preference,
        message_text: `Hi ${c.name.split(' ')[0]}! We have something special for you from Brew & Co. ☕ Visit us today and enjoy your next cup on us.`,
        channel_confidence: 'low',
        channel_reasoning: 'Default template — AI personalization enabled on Day 2',
      }))

      const r = await createCampaign({
        name,
        opportunity_type: opportunity?.opportunity_type || 'custom',
        segment_criteria: criteria,
        estimated_revenue: opportunity?.revenue_at_stake || 0,
        ai_reasoning: opportunity ? `Triggered from opportunity: "${opportunity.title}"` : null,
        messages,
      })

      navigate(`/campaigns/${r.data.id}`)
    } catch (e) {
      console.error(e)
    }
    setCreating(false)
  }

  return (
    <div className="flex-1 overflow-y-auto p-8 scrollbar-thin">
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => navigate(-1)} className="btn-ghost p-2">
          <ArrowLeft size={16} />
        </button>
        <div>
          <h1 className="section-title mb-1">Campaign Builder</h1>
          <p className="text-roast-400 text-sm">
            {opportunity ? `Acting on: "${opportunity.title}"` : 'Create a new campaign'}
          </p>
        </div>
      </div>

      {opportunity && (
        <div className="card border-gilt/30 bg-gilt/5 mb-6">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles size={14} className="text-gilt" />
            <p className="text-xs font-medium text-gilt uppercase tracking-wider">AI Opportunity</p>
          </div>
          <p className="text-cream font-medium">{opportunity.title}</p>
          <p className="text-sm text-roast-300 mt-1">{opportunity.subtitle}</p>
          <p className="text-gilt font-display font-bold mt-2">{formatRupees(opportunity.revenue_at_stake)} at stake · {opportunity.customer_count} customers</p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="stat-label block mb-1.5">Campaign Name</label>
            <input
              className="input w-full"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Win-Back — High Value June"
            />
          </div>

          <div className="card">
            <p className="text-xs font-medium text-roast-400 uppercase tracking-wider mb-3">Segment Filters</p>
            <div className="space-y-3">
              <div>
                <label className="stat-label block mb-1">Lifecycle Stage</label>
                <select
                  className="input w-full"
                  value={criteria.lifecycle_stage || ''}
                  onChange={e => setCriteria(c => ({ ...c, lifecycle_stage: e.target.value || undefined }))}
                >
                  <option value="">All stages</option>
                  <option value="loyal">Loyal</option>
                  <option value="growing">Growing</option>
                  <option value="new">New</option>
                  <option value="at_risk">At Risk</option>
                  <option value="churned">Churned</option>
                </select>
              </div>
              <div>
                <label className="stat-label block mb-1">Min. Spend (₹)</label>
                <input
                  type="number"
                  className="input w-full"
                  value={criteria.min_spend || ''}
                  onChange={e => setCriteria(c => ({ ...c, min_spend: e.target.value ? +e.target.value : undefined }))}
                  placeholder="e.g. 500"
                />
              </div>
              <div>
                <label className="stat-label block mb-1">Min. Orders</label>
                <input
                  type="number"
                  className="input w-full"
                  value={criteria.min_orders || ''}
                  onChange={e => setCriteria(c => ({ ...c, min_orders: e.target.value ? +e.target.value : undefined }))}
                  placeholder="e.g. 3"
                />
              </div>
            </div>
            <button onClick={handlePreview} disabled={previewing} className="btn-secondary w-full mt-4 flex items-center justify-center gap-2">
              <Users size={14} />
              {previewing ? 'Previewing...' : 'Preview Segment'}
            </button>
          </div>
        </div>

        <div className="space-y-4">
          {preview && (
            <div className="card">
              <p className="text-xs font-medium text-roast-400 uppercase tracking-wider mb-3">Segment Preview</p>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <p className="stat-label">Customers</p>
                  <p className="text-3xl font-display font-bold text-cream">{preview.total}</p>
                </div>
                <div>
                  <p className="stat-label">Avg. Spend</p>
                  <p className="text-3xl font-display font-bold text-gilt">{formatRupees(preview.avg_spend)}</p>
                </div>
              </div>

              <div className="space-y-1.5 mb-4">
                {Object.entries(preview.channel_breakdown || {}).map(([ch, count]) => (
                  <div key={ch} className="flex items-center justify-between text-sm">
                    <span className="text-roast-300">{ch === 'whatsapp' ? '💬 WhatsApp' : '📱 SMS'}</span>
                    <span className="text-cream font-medium">{count}</span>
                  </div>
                ))}
              </div>

              <div className="p-3 bg-roast-900/60 rounded-lg mb-4">
                <p className="text-xs text-roast-400 mb-1.5">Sample customers</p>
                {(preview.sample_customers || []).slice(0, 3).map(c => (
                  <p key={c.id} className="text-xs text-roast-300">{c.name} · {formatRupees(c.total_spend)} · {c.lifecycle_stage}</p>
                ))}
              </div>

              <div className="p-3 bg-yellow-900/20 border border-yellow-800/50 rounded-lg mb-4">
                <p className="text-xs text-yellow-400 font-medium">⚡ Day 2 Upgrade</p>
                <p className="text-xs text-roast-300 mt-0.5">
                  AI will generate personalized messages per customer + route each to their optimal channel & time.
                </p>
              </div>

              <button
                onClick={handleCreate}
                disabled={creating || !name || preview.total === 0}
                className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-40"
              >
                <Send size={14} />
                {creating ? 'Creating...' : `Create Campaign (${Math.min(5, preview.total)} messages)`}
              </button>
            </div>
          )}

          {!preview && (
            <div className="card border-dashed text-center py-12">
              <Users size={24} className="mx-auto text-roast-600 mb-2" />
              <p className="text-roast-400 text-sm">Set filters and preview your segment</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
