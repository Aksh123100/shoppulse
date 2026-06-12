import { NavLink } from 'react-router-dom'
import { Zap, BarChart3, Users, Send, Clock, MessageSquare } from 'lucide-react'

const navItems = [
  { to: '/', icon: Zap, label: 'Opportunities', end: true },
  { to: '/campaigns/new', icon: Send, label: 'New Campaign' },
  { to: '/campaigns', icon: BarChart3, label: 'Campaigns' },
  { to: '/customers', icon: Users, label: 'Customers' },
  { to: '/replies', icon: MessageSquare, label: 'Replies' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 flex-shrink-0 bg-roast-900 border-r border-roast-700 flex flex-col">
      {/* Brand */}
      <div className="px-5 py-6 border-b border-roast-700">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gilt flex items-center justify-center text-roast-900 font-bold text-sm">
            B
          </div>
          <div>
            <p className="font-display font-semibold text-cream text-sm leading-tight">ShopPulse</p>
            <p className="text-roast-400 text-xs">by Brew & Co.</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => isActive ? 'nav-item-active' : 'nav-item'}
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-roast-700">
        <p className="text-xs text-roast-500">Powered by</p>
        <p className="text-xs text-roast-400 font-medium">ShopPulse AI Engine</p>
      </div>
    </aside>
  )
}
