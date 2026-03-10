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
            <option value="http">http</option>
          </select>
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
        <template v-if="form.connection_type === 'http'">
          <div class="form-group">
            <label>URL</label>
            <input v-model="httpForm.url" placeholder="https://your-mcp-endpoint.com/mcp" />
          </div>
          <div class="form-group">
            <label>Headers (JSON)</label>
            <input v-model="httpForm.headers" placeholder='{"Authorization":"Bearer xxx"}' />
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

<script>
import { mcpServers } from '../api.js'

export default {
  data() {
    return {
      servers: [], loading: true, showForm: false, editingServer: null,
      form: { name: '', connection_type: 'stdio', description: '' },
      stdioForm: { command: '', args: '', env: '' },
      httpForm: { url: '', headers: '' },
      formError: '', submitting: false, testing: false, testResult: null,
    }
  },
  methods: {
    async fetchData() {
      try { this.servers = (await mcpServers.list()).map(s => ({ ...s, _testing: false, _testResult: null })) }
      catch { /* keep */ }
      finally { this.loading = false }
    },
    resetSubForms() {
      this.stdioForm = { command: '', args: '', env: '' }
      this.httpForm = { url: '', headers: '' }
    },
    onTypeChange() { this.resetSubForms() },
    openAdd() {
      this.editingServer = null
      this.form = { name: '', connection_type: 'stdio', description: '' }
      this.resetSubForms(); this.formError = ''; this.testResult = null; this.showForm = true
    },
    startEdit(s) {
      this.editingServer = s
      this.form = { name: s.name, connection_type: s.connection_type, description: s.description || '' }
      this.resetSubForms()
      const c = s.config || {}
      if (s.connection_type === 'stdio') {
        this.stdioForm.command = c.command || ''
        this.stdioForm.args = (c.args || []).join(', ')
        this.stdioForm.env = c.env ? JSON.stringify(c.env) : ''
      } else {
        this.httpForm.url = c.url || ''
        this.httpForm.headers = c.headers ? JSON.stringify(c.headers) : ''
      }
      this.formError = ''; this.testResult = null; this.showForm = true
    },
    closeForm() {
      this.showForm = false; this.editingServer = null
      this.form = { name: '', connection_type: 'stdio', description: '' }
      this.resetSubForms(); this.formError = ''; this.testResult = null
    },
    buildConfig() {
      if (this.form.connection_type === 'stdio') {
        const cfg = { command: this.stdioForm.command }
        if (this.stdioForm.args) cfg.args = this.stdioForm.args.split(',').map(s => s.trim())
        if (this.stdioForm.env) {
          try { cfg.env = JSON.parse(this.stdioForm.env) } catch { throw new Error('环境变量 JSON 无效') }
        }
        return cfg
      } else {
        const cfg = { url: this.httpForm.url }
        if (this.httpForm.headers) {
          try { cfg.headers = JSON.parse(this.httpForm.headers) } catch { throw new Error('Headers JSON 无效') }
        }
        return cfg
      }
    },
    async submitForm() {
      this.formError = ''
      if (!this.form.name) { this.formError = '请填写名称'; return }
      let config
      try { config = this.buildConfig() } catch (e) { this.formError = e.message; return }
      if (this.form.connection_type === 'stdio' && !config.command) { this.formError = '请填写命令'; return }
      if (this.form.connection_type === 'http' && !config.url) { this.formError = '请填写 URL'; return }
      this.submitting = true
      try {
        const data = { name: this.form.name, connection_type: this.form.connection_type, config, description: this.form.description }
        if (this.editingServer) await mcpServers.update(this.editingServer.id, data)
        else await mcpServers.create(data)
        this.closeForm(); await this.fetchData()
      } catch (e) { this.formError = e.message }
      finally { this.submitting = false }
    },
    async removeServer(s) {
      if (!confirm(`确定删除 "${s.name}"？`)) return
      try { await mcpServers.delete(s.id); await this.fetchData() }
      catch (e) { alert('删除失败: ' + e.message) }
    },
    async testConnection() {
      this.testResult = null
      let config
      try { config = this.buildConfig() } catch (e) { this.testResult = { success: false, message: e.message }; return }
      this.testing = true
      try { this.testResult = await mcpServers.testConnection({ name: this.form.name || 'test', connection_type: this.form.connection_type, config }) }
      catch (e) { this.testResult = { success: false, message: e.message } }
      finally { this.testing = false }
    },
    async testExisting(s) {
      s._testing = true; s._testResult = null
      try { s._testResult = await mcpServers.testConnection({ name: s.name, connection_type: s.connection_type, config: s.config }) }
      catch (e) { s._testResult = { success: false, message: e.message } }
      finally { s._testing = false }
    },
    configSummary(s) {
      const c = s.config || {}
      if (s.connection_type === 'stdio') return c.command ? `${c.command} ${(c.args || []).join(' ')}` : '-'
      return c.url || '-'
    },
    formatTime(t) {
      if (!t) return '-'
      try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
    },
  },
  mounted() { this.fetchData() },
}
</script>
