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

  // Get route/entities quickly using native fetch (bypasses axios interceptors for true parallelism)
  async getRouteAndEntitiesFetch(content, sessionId = null) {
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token
    
    const response = await fetch(`${API_BASE_URL}/api/chat/route`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ content, session_id: sessionId })
    })
    
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return response.json()
  },

  // Single request approach - only call /api/chat which returns entities in response
  // DEPRECATED: Use sendMessageWithPolling for progressive updates
  async sendMessageWithEntities(content, sessionId = null, onEntities = null) {
    const startTime = Date.now()
    console.log(`[API] === START at ${startTime} ===`)
    
    // Get auth token
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token
    const headers = {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    }
    const body = JSON.stringify({ content, session_id: sessionId })
    
    const chatUrl = `${API_BASE_URL}/api/chat`
    
    console.log(`[API] Sending chat request at ${Date.now() - startTime}ms`)
    
    const chatResponse = await fetch(chatUrl, { method: 'POST', headers, body })
    console.log(`[API] Chat response received at ${Date.now() - startTime}ms`)
    
    if (!chatResponse.ok) {
      const errorText = await chatResponse.text()
      throw new Error(`HTTP ${chatResponse.status}: ${errorText}`)
    }
    const chatData = await chatResponse.json()
    console.log(`[API] Chat complete at ${Date.now() - startTime}ms`)
    
    // Call onEntities callback with entities from main response
    if (onEntities && chatData.identified_entities) {
      console.log(`[API] Calling onEntities callback at ${Date.now() - startTime}ms`)
      onEntities(chatData.identified_entities, chatData.route_used)
    }
    
    return chatData
  },

  // ============================================================
  // PROGRESSIVE RESPONSE PATTERN - Polling-based approach
  // ============================================================

  /**
   * Start a chat message processing in the background.
   * Returns immediately with a message_id for polling.
   * 
   * @param {string} content - The user's question
   * @param {string|null} sessionId - Optional session ID for saved chats
   * @param {object|null} previousContext - Context from previous message for follow-ups
   *   {question, response, route, sql_query_type, entities}
   */
  async startChat(content, sessionId = null, previousContext = null) {
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token
    
    const body = { 
      content, 
      session_id: sessionId,
      previous_context: previousContext
    }
    
    const response = await fetch(`${API_BASE_URL}/api/chat/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      },
      body: JSON.stringify(body)
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP ${response.status}: ${errorText}`)
    }
    
    return response.json()
  },

  /**
   * Poll for message status during processing.
   */
  async getMessageStatus(messageId) {
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token
    
    const response = await fetch(`${API_BASE_URL}/api/chat/status/${messageId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      }
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`HTTP ${response.status}: ${errorText}`)
    }
    
    return response.json()
  },

  /**
   * Delete a pending message (optional cleanup).
   */
  async deletePendingMessage(messageId) {
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token
    
    const response = await fetch(`${API_BASE_URL}/api/chat/pending/${messageId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {})
      }
    })
    
    if (!response.ok) {
      console.warn(`Failed to delete pending message: ${response.status}`)
    }
  },

  /**
   * Send a message with progressive updates using polling.
   * 
   * This is the NEW recommended approach:
   * 1. Calls /api/chat/start to begin processing
   * 2. Polls /api/chat/status/{id} every 300ms
   * 3. Calls onEntities as soon as entities are ready (FAST ~500-1000ms)
   * 4. Returns full response when complete (SLOW ~2-5s)
   * 
   * @param {string} content - The user's question
   * @param {string|null} sessionId - Optional session ID for saved chats
   * @param {function} onEntities - Callback when entities are ready (fast)
   * @param {object|null} previousContext - Context from previous message for follow-ups
   * @returns {Promise<object>} - Full response when complete
   */
  async sendMessageWithPolling(content, sessionId = null, onEntities = null, previousContext = null) {
    const startTime = Date.now()
    console.log(`[API-POLL] === START at ${startTime} ===`)
    console.log(`[API-POLL] Has previous context: ${previousContext !== null}`)
    
    // Step 1: Start processing (returns immediately)
    const { message_id } = await this.startChat(content, sessionId, previousContext)
    console.log(`[API-POLL] Started, message_id: ${message_id} at ${Date.now() - startTime}ms`)
    
    // Step 2: Poll for status
    const POLL_INTERVAL = 300 // ms
    const MAX_POLL_TIME = 60000 // 60 seconds timeout
    let entitiesReceived = false
    
    return new Promise((resolve, reject) => {
      const pollStartTime = Date.now()
      
      const poll = async () => {
        try {
          // Check timeout
          if (Date.now() - pollStartTime > MAX_POLL_TIME) {
            reject(new Error('Request timeout - processing took too long'))
            return
          }
          
          const status = await this.getMessageStatus(message_id)
          console.log(`[API-POLL] Status: ${status.status} at ${Date.now() - startTime}ms`)
          
          // Handle entities_ready - call callback immediately
          if (!entitiesReceived && status.identified_entities && 
              (status.status === 'entities_ready' || status.status === 'complete')) {
            entitiesReceived = true
            console.log(`[API-POLL] 🎯 Entities ready at ${Date.now() - startTime}ms`)
            if (onEntities) {
              onEntities(status.identified_entities, status.route_used)
            }
          }
          
          // Handle complete - resolve with full response
          if (status.status === 'complete') {
            console.log(`[API-POLL] ✅ Complete at ${Date.now() - startTime}ms`)
            
            // Clean up pending message (fire and forget)
            this.deletePendingMessage(message_id).catch(() => {})
            
            // Transform to match expected ChatResponse format
            resolve({
              id: message_id,
              content: content,
              response: status.response,
              route_used: status.route_used || 'unknown',
              timestamp: new Date().toISOString(),
              response_time_ms: status.response_time_ms || 0,
              session_id: sessionId,
              table_data: status.table_data,
              identified_entities: status.identified_entities
            })
            return
          }
          
          // Handle error
          if (status.status === 'error') {
            console.log(`[API-POLL] ❌ Error at ${Date.now() - startTime}ms: ${status.error_message}`)
            
            // Clean up pending message
            this.deletePendingMessage(message_id).catch(() => {})
            
            // Return error as a valid response (not throwing)
            resolve({
              id: message_id,
              content: content,
              response: status.error_message || 'Hi ha hagut un error processant la teva pregunta.',
              route_used: 'error',
              timestamp: new Date().toISOString(),
              response_time_ms: 0,
              session_id: sessionId
            })
            return
          }
          
          // Continue polling
          setTimeout(poll, POLL_INTERVAL)
          
        } catch (error) {
          console.error(`[API-POLL] Poll error:`, error)
          reject(error)
        }
      }
      
      // Start polling
      poll()
    })
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

  // El Joc del Mocador game endpoints
  async getGameQuestions(numQuestions = 10, colles = [], years = []) {
    const params = { num_questions: numQuestions }
    
    // Add colles parameter if any are selected
    if (colles && colles.length > 0) {
      params.colles = colles.join(',')
    }
    
    // Add years parameter if any are selected
    if (years && years.length > 0) {
      params.years = years.join(',')
    }
    
    const response = await api.get('/api/joc-del-mocador/questions', { params })
    return response.data
  },

  // Contact form endpoint
  async sendContactMessage({ name, email, message }) {
    const response = await api.post('/api/contact', { name, email, message })
    return response.data
  }
}

export default api
