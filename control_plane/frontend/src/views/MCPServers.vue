<template>
  <div>
    <div class="page-header">
      <h2>MCP Server 注册表</h2>
      <button class="btn btn-primary" @click="openAdd">注册 MCP Server</button>
    </div>

    <!-- 添加/编辑对话框 -->
    <div v-if="showForm" class="modal-overlay" @click.self="closeForm">
      <div class="modal-card">
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

        <!-- stdio 配置 -->
        <template v-if="form.connection_type === 'stdio'">
          <div class="form-group">
            <label>命令 (command)</label>
            <input v-model="stdioForm.command" placeholder="如: npx" />
          </div>
          <div class="form-group">
            <label>参数 (args，逗号分隔)</label>
            <input v-model="stdioForm.args" placeholder="如: -y,@some/mcp-server" />
          </div>
          <div class="form-group">
            <label>环境变量 (JSON，可选)</label>
            <input v-model="stdioForm.env" placeholder='如: {"KEY":"value"}' />
          </div>
        </template>

        <!-- http 配置 -->
        <template v-if="form.connection_type === 'http'">
          <div class="form-group">
            <label>URL</label>
            <input v-model="httpForm.url" placeholder="https://your-mcp-endpoint.com/mcp" />
          </div>
          <div class="form-group">
            <label>Headers (JSON，可选)</label>
            <input v-model="httpForm.headers" placeholder='如: {"Authorization":"Bearer xxx"}' />
          </div>
        </template>

        <div class="form-group">
          <label>描述</label>
          <input v-model="form.description" placeholder="MCP Server 功能描述" />
        </div>
        <p v-if="formError" class="error-msg">{{ formError }}</p>
        <p v-if="testResult" :class="testResult.success ? 'test-ok' : 'test-fail'">
          {{ testResult.message }}
        </p>
        <div class="form-actions">
          <button class="btn btn-primary" @click="submitForm" :disabled="submitting">
            {{ submitting ? '提交中...' : '确定' }}
          </button>
          <button class="btn btn-test" @click="testConnection" :disabled="testing">
            {{ testing ? '测试中...' : '测试连接' }}
          </button>
          <button class="btn" @click="closeForm">取消</button>
        </div>
      </div>
    </div>

    <!-- Server 列表 -->
    <div class="card">
      <p v-if="loading" style="color:#909399">加载中...</p>
      <table v-else-if="servers.length">
        <thead>
          <tr>
            <th>名称</th>
            <th>连接类型</th>
            <th>配置摘要</th>
            <th>描述</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in servers" :key="s.id">
            <td>{{ s.name }}</td>
            <td><span class="badge badge-type">{{ s.connection_type }}</span></td>
            <td><code>{{ configSummary(s) }}</code></td>
            <td>{{ s.description || '-' }}</td>
            <td>{{ formatTime(s.created_at) }}</td>
            <td class="action-cell">
              <div class="action-buttons">
                <button class="btn btn-small btn-test" @click="testExisting(s)" :disabled="s._testing">
                  {{ s._testing ? '...' : '测试' }}
                </button>
                <button class="btn btn-small btn-primary" @click="startEdit(s)">编辑</button>
                <button class="btn btn-small btn-danger" @click="removeServer(s)">删除</button>
              </div>
              <div v-if="s._testResult" :class="['test-result', s._testResult.success ? 'test-ok' : 'test-fail']">
                {{ s._testResult.message }}
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else style="color:#909399">暂无 MCP Server，点击右上角注册</p>
    </div>
  </div>
</template>

<script>
import { mcpServers } from '../api.js'

export default {
  data() {
    return {
      servers: [],
      loading: true,
      showForm: false,
      editingServer: null,
      form: { name: '', connection_type: 'stdio', description: '' },
      stdioForm: { command: '', args: '', env: '' },
      httpForm: { url: '', headers: '' },
      formError: '',
      submitting: false,
      testing: false,
      testResult: null,
    }
  },
  methods: {
    async fetchData() {
      try {
        const list = await mcpServers.list()
        this.servers = list.map(s => ({ ...s, _testing: false, _testResult: null }))
      }
      catch { /* keep last */ }
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
      this.resetSubForms()
      this.formError = ''
      this.showForm = true
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
      this.formError = ''
      this.showForm = true
    },
    closeForm() {
      this.showForm = false
      this.editingServer = null
      this.form = { name: '', connection_type: 'stdio', description: '' }
      this.resetSubForms()
      this.formError = ''
      this.testResult = null
    },
    buildConfig() {
      if (this.form.connection_type === 'stdio') {
        const cfg = { command: this.stdioForm.command }
        if (this.stdioForm.args) cfg.args = this.stdioForm.args.split(',').map(s => s.trim())
        if (this.stdioForm.env) {
          try { cfg.env = JSON.parse(this.stdioForm.env) }
          catch { throw new Error('环境变量 JSON 格式无效') }
        }
        return cfg
      } else {
        const cfg = { url: this.httpForm.url }
        if (this.httpForm.headers) {
          try { cfg.headers = JSON.parse(this.httpForm.headers) }
          catch { throw new Error('Headers JSON 格式无效') }
        }
        return cfg
      }
    },
    async submitForm() {
      this.formError = ''
      if (!this.form.name) { this.formError = '请填写名称'; return }
      let config
      try { config = this.buildConfig() }
      catch (e) { this.formError = e.message; return }

      if (this.form.connection_type === 'stdio' && !config.command) {
        this.formError = '请填写命令'; return
      }
      if (this.form.connection_type === 'http' && !config.url) {
        this.formError = '请填写 URL'; return
      }

      this.submitting = true
      try {
        const data = {
          name: this.form.name,
          connection_type: this.form.connection_type,
          config,
          description: this.form.description,
        }
        if (this.editingServer) {
          await mcpServers.update(this.editingServer.id, data)
        } else {
          await mcpServers.create(data)
        }
        this.closeForm()
        await this.fetchData()
      } catch (e) {
        this.formError = e.message
      } finally { this.submitting = false }
    },
    async removeServer(s) {
      if (!confirm(`确定删除 MCP Server "${s.name}"？`)) return
      try {
        await mcpServers.delete(s.id)
        await this.fetchData()
      } catch (e) {
        alert('删除失败: ' + e.message)
      }
    },
    async testConnection() {
      this.testResult = null
      let config
      try { config = this.buildConfig() } catch (e) { this.testResult = { success: false, message: e.message }; return }
      this.testing = true
      try {
        this.testResult = await mcpServers.testConnection({
          name: this.form.name || 'test',
          connection_type: this.form.connection_type,
          config,
        })
      } catch (e) {
        this.testResult = { success: false, message: e.message }
      } finally { this.testing = false }
    },
    async testExisting(s) {
      s._testing = true
      s._testResult = null
      try {
        const result = await mcpServers.testConnection({
          name: s.name,
          connection_type: s.connection_type,
          config: s.config,
        })
        s._testResult = result
      } catch (e) {
        s._testResult = { success: false, message: e.message }
      } finally { s._testing = false }
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

<style scoped>
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal-card {
  background: #fff; border-radius: 8px; padding: 24px; width: 480px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.modal-card h3 { margin-bottom: 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 13px; color: #606266; margin-bottom: 4px; }
.form-group input, .form-group select {
  width: 100%; padding: 8px 10px; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 14px; box-sizing: border-box;
}
.form-actions { display: flex; gap: 8px; margin-top: 16px; }
.action-cell { min-width: 180px; }
.action-buttons { display: flex; gap: 6px; white-space: nowrap; }
.test-result { font-size: 12px; margin-top: 4px; max-width: 260px; word-break: break-all; line-height: 1.4; }
.badge-type { background: #f0f5ff; color: #2f54eb; padding: 2px 8px; border-radius: 3px; font-size: 12px; }
code { font-size: 12px; background: #f4f4f5; padding: 2px 6px; border-radius: 3px; }
.test-ok { color: #22c55e; font-size: 13px; }
.test-fail { color: #ef4444; font-size: 13px; }
.btn-test { background: #e6f7ff; color: #1890ff; border-color: #91d5ff; }
.btn-test:hover { background: #bae7ff; }
</style>
