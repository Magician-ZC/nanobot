<template>
  <div>
    <div class="page-header">
      <h2>MCP Server 注册表</h2>
      <button class="btn btn-primary" @click="openAdd">注册 MCP Server</button>
    </div>

    <!-- 添加/编辑对话框 -->
    <div v-if="showForm" class="modal-overlay" @click.self="closeForm">
      <div class="modal-card" style="width:500px">
        <h3>{{ editingServer ? '编辑 MCP Server' : '注册新 MCP Server' }}</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="form.name" placeholder="如: my-mcp-server" />
        </div>
        <div class="form-group">
          <label>连接类型</label>
          <select v-model="form.connection_type" @change="onTypeChange">
            <option value="stdio">stdio</option>
            <option value="sse">sse</option>
            <option value="streamableHttp">streamableHttp</option>
            <option value="http">http (legacy)</option>
          </select>
          <small style="color:var(--text-muted);display:block;margin-top:4px">stdio: 本地进程 | sse: Server-Sent Events | streamableHttp: HTTP 流式传输</small>
        </div>
        <template v-if="form.connection_type === 'stdio'">
          <div class="form-group">
            <label>命令</label>
            <input v-model="stdioForm.command" placeholder="如: npx" />
          </div>
          <div class="form-group">
            <label>参数 (逗号分隔)</label>
            <input v-model="stdioForm.args" placeholder="如: -y,@some/mcp-server" />
          </div>
          <div class="form-group">
            <label>环境变量 (JSON)</label>
            <input v-model="stdioForm.env" placeholder='{"KEY":"value"}' />
          </div>
        </template>
        <template v-if="form.connection_type === 'sse' || form.connection_type === 'streamableHttp' || form.connection_type === 'http'">
          <div class="form-group">
            <label>URL</label>
            <input v-model="httpForm.url" placeholder="https://your-mcp-endpoint.com/mcp" />
          </div>
          <div class="form-group">
            <label>Headers (JSON)</label>
            <input v-model="httpForm.headers" placeholder='{"Authorization":"Bearer xxx"}' />
          </div>
          <div class="form-group">
            <label>Tool Timeout (秒)</label>
            <input v-model.number="httpForm.tool_timeout" type="number" min="1" placeholder="30" />
          </div>
        </template>
        <div class="form-group">
          <label>描述</label>
          <input v-model="form.description" placeholder="功能描述" />
        </div>
        <p v-if="formError" class="error-msg">{{ formError }}</p>
        <p v-if="testResult" :class="testResult.success ? 'success-msg' : 'error-msg'">{{ testResult.message }}</p>
        <div class="form-actions">
          <button class="btn" @click="testConnection" :disabled="testing">{{ testing ? '测试中...' : '测试连接' }}</button>
          <button class="btn" @click="closeForm">取消</button>
          <button class="btn btn-primary" @click="submitForm" :disabled="submitting">{{ submitting ? '提交中...' : '确定' }}</button>
        </div>
      </div>
    </div>

    <div class="card">
      <p v-if="loading" style="color:var(--text-muted)">加载中...</p>
      <table v-else-if="servers.length">
        <thead><tr><th>名称</th><th>类型</th><th>配置</th><th>描述</th><th>创建时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="s in servers" :key="s.id">
            <td style="font-weight:500">{{ s.name }}</td>
            <td><span class="badge badge-info">{{ s.connection_type }}</span></td>
            <td><code style="font-size:11px">{{ configSummary(s) }}</code></td>
            <td>{{ s.description || '-' }}</td>
            <td>{{ formatTime(s.created_at) }}</td>
            <td class="action-cell">
              <button class="btn btn-small" @click="testExisting(s)" :disabled="s._testing">{{ s._testing ? '...' : '测试' }}</button>
              <button class="btn btn-small" @click="startEdit(s)">编辑</button>
              <button class="btn btn-small btn-danger" @click="removeServer(s)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">
        <div class="empty-state-icon">🔌</div>
        <div class="empty-state-text">暂无 MCP Server</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { mcpServers } from '../api.js'

const servers = ref([])
const loading = ref(true)
const showForm = ref(false)
const editingServer = ref(null)

const form = ref({ name: '', connection_type: 'stdio', description: '' })
const stdioForm = ref({ command: '', args: '', env: '' })
const httpForm = ref({ url: '', headers: '', tool_timeout: 30 })

const formError = ref('')
const submitting = ref(false)
const testing = ref(false)
const testResult = ref(null)

const fetchData = async () => {
  try {
    const list = await mcpServers.list()
    servers.value = list.map(s => ({ ...s, _testing: false, _testResult: null }))
  } catch (e) {
    console.error('Failed to fetch MCP servers:', e)
  } finally {
    loading.value = false
  }
}

const resetSubForms = () => {
  stdioForm.value = { command: '', args: '', env: '' }
  httpForm.value = { url: '', headers: '', tool_timeout: 30 }
}

const onTypeChange = () => {
  resetSubForms()
}

const openAdd = () => {
  editingServer.value = null
  form.value = { name: '', connection_type: 'stdio', description: '' }
  resetSubForms()
  formError.value = ''
  testResult.value = null
  showForm.value = true
}

const startEdit = (s) => {
  editingServer.value = s
  form.value = { name: s.name, connection_type: s.connection_type, description: s.description || '' }
  resetSubForms()
  const c = s.config || {}
  if (s.connection_type === 'stdio') {
    stdioForm.value.command = c.command || ''
    stdioForm.value.args = (c.args || []).join(', ')
    stdioForm.value.env = c.env ? JSON.stringify(c.env) : ''
  } else {
    httpForm.value.url = c.url || ''
    httpForm.value.headers = c.headers ? JSON.stringify(c.headers) : ''
    httpForm.value.tool_timeout = c.tool_timeout || 30
  }
  formError.value = ''
  testResult.value = null
  showForm.value = true
}

const closeForm = () => {
  showForm.value = false
  editingServer.value = null
  form.value = { name: '', connection_type: 'stdio', description: '' }
  resetSubForms()
  formError.value = ''
  testResult.value = null
}

const buildConfig = () => {
  if (form.value.connection_type === 'stdio') {
    const cfg = { command: stdioForm.value.command }
    if (stdioForm.value.args) cfg.args = stdioForm.value.args.split(',').map(s => s.trim())
    if (stdioForm.value.env) {
      try {
        cfg.env = JSON.parse(stdioForm.value.env)
      } catch {
        throw new Error('环境变量 JSON 无效')
      }
    }
    return cfg
  } else {
    const cfg = { url: httpForm.value.url, type: form.value.connection_type }
    if (httpForm.value.headers) {
      try {
        cfg.headers = JSON.parse(httpForm.value.headers)
      } catch {
        throw new Error('Headers JSON 无效')
      }
    }
    if (httpForm.value.tool_timeout && httpForm.value.tool_timeout !== 30) {
      cfg.tool_timeout = httpForm.value.tool_timeout
    }
    return cfg
  }
}

const submitForm = async () => {
  formError.value = ''
  if (!form.value.name) {
    formError.value = '请填写名称'
    return
  }
  let config
  try {
    config = buildConfig()
  } catch (e) {
    formError.value = e.message
    return
  }
  if (form.value.connection_type === 'stdio' && !config.command) {
    formError.value = '请填写命令'
    return
  }
  if (form.value.connection_type !== 'stdio' && !config.url) {
    formError.value = '请填写 URL'
    return
  }
  submitting.value = true
  try {
    const data = {
      name: form.value.name,
      connection_type: form.value.connection_type,
      config,
      description: form.value.description
    }
    if (editingServer.value) {
      await mcpServers.update(editingServer.value.id, data)
    } else {
      await mcpServers.create(data)
    }
    closeForm()
    await fetchData()
  } catch (e) {
    formError.value = e.message
  } finally {
    submitting.value = false
  }
}

const removeServer = async (s) => {
  if (!confirm(`确定删除 "${s.name}"？`)) return
  try {
    await mcpServers.delete(s.id)
    await fetchData()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

const testConnection = async () => {
  testResult.value = null
  let config
  try {
    config = buildConfig()
  } catch (e) {
    testResult.value = { success: false, message: e.message }
    return
  }
  testing.value = true
  try {
    testResult.value = await mcpServers.testConnection({
      name: form.value.name || 'test',
      connection_type: form.value.connection_type,
      config
    })
  } catch (e) {
    testResult.value = { success: false, message: e.message }
  } finally {
    testing.value = false
  }
}

const testExisting = async (s) => {
  s._testing = true
  s._testResult = null
  try {
    s._testResult = await mcpServers.testConnection({
      name: s.name,
      connection_type: s.connection_type,
      config: s.config
    })
  } catch (e) {
    s._testResult = { success: false, message: e.message }
  } finally {
    s._testing = false
  }
}

const configSummary = (s) => {
  const c = s.config || {}
  if (s.connection_type === 'stdio') {
    return c.command ? `${c.command} ${(c.args || []).join(' ')}` : '-'
  }
  return c.url || '-'
}

const formatTime = (t) => {
  if (!t) return '-'
  try {
    return new Date(t).toLocaleString('zh-CN')
  } catch {
    return t
  }
}

onMounted(() => {
  fetchData()
})
</script>
