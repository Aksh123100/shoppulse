import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import OpportunityFeed from './pages/OpportunityFeed'
import Customers from './pages/Customers'
import Campaigns from './pages/Campaigns'
import CampaignBuilder from './pages/CampaignBuilder'
import CampaignDetail from './pages/CampaignDetail'
import Replies from './pages/Replies'

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-hidden flex flex-col min-w-0">
          <Routes>
            <Route path="/" element={<OpportunityFeed />} />
            <Route path="/customers" element={<Customers />} />
            <Route path="/campaigns" element={<Campaigns />} />
            <Route path="/campaigns/new" element={<CampaignBuilder />} />
            <Route path="/campaigns/:id" element={<CampaignDetail />} />
            <Route path="/replies" element={<Replies />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
