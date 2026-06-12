import { useState, useEffect } from 'react'
import { getFlaggedReplies, respondToReply } from '../lib/api'
import { MessageSquare, Check } from 'lucide-react'

export default function Replies() {
  const [replies, setReplies] = useState([])
  const [loading, setLoading] = useState(true)
  const [responding, setResponding] = useState({})

  useEffect(() => {
    getFlaggedReplies().then(r => {
      setReplies(r.data || [])
      setLoading(false)
    })
  }, [])

  const handleRespond = async (reply) => {
    const text = prompt(`Reply to ${reply.customer_name}:`, 'We apologise for any inconvenience. You have been removed from our list.')
    if (!text) return
    setResponding(r => ({ ...r, [reply.id]: true }))
    await respondToReply(reply.id, text)
    setReplies(prev => prev.filter(r => r.id !== reply.id))
    setResponding(r => ({ ...r, [reply.id]: false }))
  }

  return (
    <div className="flex-1 overflow-y-auto p-8 scrollbar-thin">
      <div className="mb-6">
        <h1 className="section-title mb-1">Flagged Replies</h1>
        <p className="text-roast-400 text-sm">Customer replies that need your attention.</p>
      </div>

      {loading ? (
        <div className="space-y-3">{Array(3).fill(0).map((_, i) => <div key={i} className="card h-20 animate-pulse bg-roast-700" />)}</div>
      ) : replies.length === 0 ? (
        <div className="card text-center py-16">
          <MessageSquare size={32} className="mx-auto text-roast-500 mb-3" />
          <p className="text-roast-300">No flagged replies right now. You're all caught up.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {replies.map(r => (
            <div key={r.id} className="card border-orange-800 bg-orange-950/10">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-cream text-sm">{r.customer_name}</p>
                  <p className="text-xs text-roast-400 mb-2">{new Date(r.created_at).toLocaleString('en-IN')}</p>
                  <p className="text-sm text-roast-200 bg-roast-900/60 rounded-lg p-3">"{r.message}"</p>
                </div>
                <button
                  onClick={() => handleRespond(r)}
                  disabled={responding[r.id]}
                  className="btn-primary flex items-center gap-2 flex-shrink-0"
                >
                  <Check size={13} />
                  Respond
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
