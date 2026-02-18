/**
 * API 客户端 - 封装 JWT 令牌管理和 HTTP 请求
 */

const TOKEN_KEY = 'nanobot_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function isLoggedIn() {
  return !!getToken()
}

/** 解析 JWT payload（不验证签名，仅用于前端展示） */
export function parseToken(token) {
  try {
    const payload = token.split('.')[1]
    return JSON.parse(atob(payload))
  } catch {
    return null
  }
}

/** 获取当前用户信息 */
export function getCurrentUser() {
  const token = getToken()
  if (!token) return null
  const payload = parseToken(token)
  if (!payload) return null
  if (payload.exp && payload.exp * 1000 < Date.now()) {
    removeToken()
    return null
  }
  return { userId: payload.sub, role: payload.role }
}

/** 通用 fetch 封装 */
async function request(url, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(url, { ...options, headers })
  if (res.status === 401) {
    removeToken()
    window.location.hash = '#/login'
    throw new Error('Unauthorized')
  }
  if (res.status === 204) return null
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Request failed')
  return data
}

// ── Auth API ──
export const auth = {
  login: (username, password) =>
    request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
}

// ── Users API ──
export const users = {
  list: () => request('/api/users'),
  create: (data) =>
    request('/api/users', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) =>
    request(`/api/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  disable: (id) => request(`/api/users/${id}`, { method: 'DELETE' }),
}

// ── Nodes API ──
export const nodes = {
  list: () => request('/api/nodes'),
  get: (id) => request(`/api/nodes/${id}`),
  delete: (id) => request(`/api/nodes/${id}`, { method: 'DELETE' }),
}

// ── Tokens API ──
export const tokens = {
  create: (userId) =>
    request('/api/tokens', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    }),
}

// ── Skills API ──
export const skills = {
  list: () => request('/api/skills'),
  create: (data) =>
    request('/api/skills', { method: 'POST', body: JSON.stringify(data) }),
}

// ── MCP Servers API ──
export const mcpServers = {
  list: () => request('/api/mcp-servers'),
  create: (data) =>
    request('/api/mcp-servers', { method: 'POST', body: JSON.stringify(data) }),
}

// ── Policy API ──
export const policies = {
  get: (nodeId) => request(`/api/nodes/${nodeId}/policy`),
  update: (nodeId, data) =>
    request(`/api/nodes/${nodeId}/policy`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
}

// ── Config API ──
export const configs = {
  get: (nodeId) => request(`/api/nodes/${nodeId}/config`),
  update: (nodeId, data) =>
    request(`/api/nodes/${nodeId}/config`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
}

// ── Tasks API ──
export const tasks = {
  list: (nodeId) => {
    const url = nodeId ? `/api/tasks?node_id=${nodeId}` : '/api/tasks'
    return request(url)
  },
}

// ── Deploy API ──
export const deploy = {
  getScript: (tokenId, type) =>
    fetch(`/api/deploy/script?token_id=${tokenId}&type=${type}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    }).then(res => {
      if (!res.ok) throw new Error('Failed to get deploy script')
      return res.text()
    }),
}

// ── LLM Keys API ──
export const llmKeys = {
  list: () => request('/api/llm-keys'),
  create: (data) =>
    request('/api/llm-keys', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) =>
    request(`/api/llm-keys/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/api/llm-keys/${id}`, { method: 'DELETE' }),
  usage: (id) => request(`/api/llm-keys/${id}/usage`),
}

// ── Token Usage API ──
export const tokenUsage = {
  query: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/token-usage${qs ? '?' + qs : ''}`)
  },
  summary: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/token-usage/summary${qs ? '?' + qs : ''}`)
  },
  byNode: (nodeId, params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/nodes/${nodeId}/token-usage${qs ? '?' + qs : ''}`)
  },
}

