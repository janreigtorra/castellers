// apiService.js
import axios from 'axios'
import { supabase } from './supabaseClient'

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000'

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add request interceptor to include auth token
api.interceptors.request.use(
  async (config) => {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      console.log('[API] Session check:', session ? 'Found' : 'Not found')
      if (session?.access_token) {
        config.headers.Authorization = `Bearer ${session.access_token}`
        console.log('[API] Token added to request:', session.access_token.substring(0, 20) + '...')
      } else {
        console.log('[API] No access token in session')
      }
    } catch (error) {
      console.error('[API] Error getting session:', error)
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Add response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid, sign out user
      await supabase.auth.signOut()
      window.location.reload()
    }
    return Promise.reject(error)
  }
)

// API service functions
export const apiService = {
  // Chat endpoints
  async sendMessage(content, sessionId = null) {
    const response = await api.post('/api/chat', {
      content,
      session_id: sessionId
    })
    return response.data
  },

  async getChatHistory(sessionId = null, limit = 50) {
    const params = { limit }
    if (sessionId) params.session_id = sessionId
    
    const response = await api.get('/api/chat/history', { params })
    return response.data
  },

  // Session endpoints
  async createSession(title = 'New Chat') {
    const response = await api.post('/api/sessions', { title })
    return response.data
  },

  async getSessions() {
    const response = await api.get('/api/sessions')
    return response.data
  },

  async updateSession(sessionId, title) {
    const response = await api.put(`/api/sessions/${sessionId}`, null, {
      params: { title }
    })
    return response.data
  },

  async deleteSession(sessionId) {
    const response = await api.delete(`/api/sessions/${sessionId}`)
    return response.data
  },

  async saveChatSession(title, messages) {
    const response = await api.post('/api/sessions/save', {
      title,
      messages
    })
    return response.data
  },

  // User profile endpoints
  async getUserProfile() {
    const response = await api.get('/api/user/profile')
    return response.data
  },

  // Auth endpoints (these use our backend, not Supabase directly)
  async login(email, password) {
    const response = await api.post('/api/auth/login', {
      email,
      password
    })
    return response.data
  },

  async register(email, password, username = null) {
    const response = await api.post('/api/auth/register', {
      email,
      password,
      username
    })
    return response.data
  },

  async logout() {
    const response = await api.post('/api/auth/logout')
    return response.data
  },

  // PassaFaixa game endpoints
  async getGameQuestions(numQuestions = 10) {
    const response = await api.get('/api/passafaixa/questions', {
      params: { num_questions: numQuestions }
    })
    return response.data
  }
}

export default api
