export const formatRupees = (amount) => {
  if (amount >= 100000) return `₹${(amount / 100000).toFixed(1)}L`
  if (amount >= 1000) return `₹${(amount / 1000).toFixed(1)}K`
  return `₹${Math.round(amount)}`
}

export const formatPercent = (rate) => `${Math.round(rate * 100)}%`

export const daysSince = (dateStr) => {
  if (!dateStr) return null
  const diff = Date.now() - new Date(dateStr).getTime()
  return Math.floor(diff / (1000 * 60 * 60 * 24))
}

export const lifecycleColor = (stage) => ({
  loyal: 'text-emerald-400',
  growing: 'text-blue-400',
  new: 'text-purple-400',
  at_risk: 'text-orange-400',
  churned: 'text-red-400',
}[stage] || 'text-gray-400')

export const lifecycleBadge = (stage) => ({
  loyal: 'bg-emerald-900/50 text-emerald-300 border-emerald-800',
  growing: 'bg-blue-900/50 text-blue-300 border-blue-800',
  new: 'bg-purple-900/50 text-purple-300 border-purple-800',
  at_risk: 'bg-orange-900/50 text-orange-300 border-orange-800',
  churned: 'bg-red-900/50 text-red-300 border-red-800',
}[stage] || 'bg-gray-800 text-gray-300 border-gray-700')

export const urgencyBadge = (urgency) => ({
  critical: 'badge-critical',
  high: 'badge-high',
  medium: 'badge-medium',
}[urgency] || 'badge')

export const urgencyLabel = (urgency) => ({
  critical: '🔴 URGENT',
  high: '🟠 HIGH',
  medium: '🟡 MEDIUM',
}[urgency] || urgency)

export const channelIcon = (channel) => channel === 'whatsapp' ? '💬' : '📱'
