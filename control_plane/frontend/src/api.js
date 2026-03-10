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
  assignLLMKey: (id, data) =>
    request(`/api/nodes/${id}/llm-assignment`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
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
  update: (id, data) =>
    request(`/api/skills/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/api/skills/${id}`, { method: 'DELETE' }),
  generate: (data) =>
    request('/api/skills/generate', { method: 'POST', body: JSON.stringify(data) }),
  generatePreview: (data) =>
    request('/api/skills/generate-preview', { method: 'POST', body: JSON.stringify(data) }),
}

// ── MCP Servers API ──
export const mcpServers = {
  list: () => request('/api/mcp-servers'),
  create: (data) =>
    request('/api/mcp-servers', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) =>
    request(`/api/mcp-servers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/api/mcp-servers/${id}`, { method: 'DELETE' }),
  testConnection: (data) =>
    request('/api/mcp-servers/test-connection', { method: 'POST', body: JSON.stringify(data) }),
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
  byNode: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/token-usage/by-node${qs ? '?' + qs : ''}`)
  },
  byNodeId: (nodeId, params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/nodes/${nodeId}/token-usage${qs ? '?' + qs : ''}`)
  },
}

// ── Personas API ──
export const personas = {
  list: () => request('/api/personas'),
  create: (data) =>
    request('/api/personas', { method: 'POST', body: JSON.stringify(data) }),
  get: (id) => request(`/api/personas/${id}`),
  update: (id, data) =>
    request(`/api/personas/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id) => request(`/api/personas/${id}`, { method: 'DELETE' }),
  getMemory: (id) => request(`/api/personas/${id}/memory`),
  merge: (id) => request(`/api/personas/${id}/merge`, { method: 'POST' }),
  compress: (id) => request(`/api/personas/${id}/compress`, { method: 'POST' }),
  compressAll: () => request('/api/personas/compress-all', { method: 'POST' }),
  generate: (data) =>
    request('/api/personas/generate', { method: 'POST', body: JSON.stringify(data) }),
  generatePreview: (data) =>
    request('/api/personas/generate-preview', { method: 'POST', body: JSON.stringify(data) }),
}

// ── Feishu Gateway API ──
export const feishuGateway = {
  // 配置
  getConfig: () => request('/api/gateway/config'),
  saveConfig: (data) =>
    request('/api/gateway/config', { method: 'POST', body: JSON.stringify(data) }),
  getStatus: () => request('/api/gateway/status'),
  start: () => request('/api/gateway/start', { method: 'POST' }),
  stop: () => request('/api/gateway/stop', { method: 'POST' }),
  // 绑定
  listBindings: (nodeId) => {
    const url = nodeId ? `/api/gateway/bindings?node_id=${nodeId}` : '/api/gateway/bindings'
    return request(url)
  },
  createBinding: (data) =>
    request('/api/gateway/bindings', { method: 'POST', body: JSON.stringify(data) }),
  deleteBinding: (id) =>
    request(`/api/gateway/bindings/${id}`, { method: 'DELETE' }),
  // 绑定码
  listBindCodes: (nodeId) => {
    const url = nodeId ? `/api/gateway/bind-codes?node_id=${nodeId}` : '/api/gateway/bind-codes'
    return request(url)
  },
  createBindCode: (data) =>
    request('/api/gateway/bind-codes', { method: 'POST', body: JSON.stringify(data) }),
  // 对话记录
  listSessions: (nodeId) => {
    const url = nodeId ? `/api/gateway/sessions?node_id=${nodeId}` : '/api/gateway/sessions'
    return request(url)
  },
  listConversations: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/gateway/conversations${qs ? '?' + qs : ''}`)
  },
  getConversation: (openId, limit = 50) =>
    request(`/api/gateway/conversations/${openId}?limit=${limit}`),
}

