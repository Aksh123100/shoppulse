import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
})

// Customers
export const getCustomers = (params = {}) => api.get('/customers', { params })
export const getCustomerStats = () => api.get('/customers/stats')
export const getCustomer = (id) => api.get(`/customers/${id}`)
export const getChannelProfile = (id) => api.get(`/customers/${id}/channel-profile`)

// Opportunities
export const getOpportunities = () => api.get('/opportunities')

// Segments
export const previewSegment = (criteria) => api.post('/segments/preview', criteria)

// Campaigns
export const getCampaigns = (params = {}) => api.get('/campaigns', { params })
export const getCampaign = (id) => api.get(`/campaigns/${id}`)
export const createCampaign = (payload) => api.post('/campaigns', payload)
export const sendCampaign = (id) => api.post(`/campaigns/${id}/send`)
export const getCampaignLive = (id) => api.get(`/campaigns/${id}/live`)

// Agent
export const thinkAgent = (payload) => api.post('/agent/think', payload)
export const draftMessages = (payload) => api.post('/agent/message-draft', payload)

// Replies
export const getFlaggedReplies = () => api.get('/replies/flagged')
export const respondToReply = (id, text) => api.post(`/replies/${id}/respond`, { response_text: text })

// Seed
export const seedData = () => api.post('/seed')

export default api
