<template>
  <div>
    <div class="page-header">
      <h2>飞书网关</h2>
      <span class="auto-refresh-hint">每 15 秒自动刷新状态</span>
    </div>

    <!-- Tab 导航 -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >{{ tab.label }}</button>
    </div>

    <!-- ═══ 网关配置 & 状态 ═══ -->
    <template v-if="activeTab === 'config'">
      <!-- 连接状态 -->
      <div class="card">
        <h3 style="margin-bottom:12px">连接状态</h3>
        <div class="info-grid">
          <div>
            <span class="info-label">状态</span>
            <span :class="['badge', gwStatus.is_connected ? 'badge-online' : 'badge-offline']">
              {{ gwStatus.is_connected ? '已连接' : '未连接' }}
            </span>
          </div>
          <div><span class="info-label">已连接时长</span>{{ formatDuration(gwStatus.connected_since) }}</div>
          <div><span class="info-label">在线节点</span>{{ gwStatus.connected_nodes ?? 0 }}</div>
          <div><span class="info-label">绑定总数</span>{{ gwStatus.total_bindings ?? 0 }}</div>
          <div><span class="info-label">最近消息</span>{{ formatTime(gwStatus.last_message_at) }}</div>
        </div>
        <div style="margin-top:14px;display:flex;gap:8px">
          <button class="btn btn-success" @click="startGateway" :disabled="gwStatus.is_connected">启动</button>
          <button class="btn btn-danger" @click="stopGateway" :disabled="!gwStatus.is_connected">停止</button>
        </div>
      </div>

      <!-- 配置表单 -->
      <div class="card">
        <h3 style="margin-bottom:12px">飞书应用配置</h3>
        <form @submit.prevent="saveConfig">
          <div class="form-row">
            <div class="form-group">
              <label>App ID</label>
              <input v-model="configForm.app_id" required placeholder="飞书应用 App ID" />
            </div>
            <div class="form-group">
              <label>App Secret</label>
              <input v-model="configForm.app_secret" type="password" required placeholder="飞书应用 App Secret" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Encrypt Key（可选）</label>
              <input v-model="configForm.encrypt_key" placeholder="事件加密 Key" />
            </div>
            <div class="form-group">
              <label>Verification Token（可选）</label>
              <input v-model="configForm.verification_token" placeholder="验证 Token" />
            </div>
          </div>
          <p v-if="configError" class="error-msg">{{ configError }}</p>
          <p v-if="configSuccess" class="success-msg">{{ configSuccess }}</p>
          <button class="btn btn-primary" type="submit">保存配置</button>
        </form>
      </div>
    </template>

    <!-- ═══ 绑定管理 ═══ -->
    <template v-if="activeTab === 'bindings'">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3>用户绑定列表</h3>
          <button class="btn btn-primary" @click="showBindingModal = true">创建绑定</button>
        </div>
        <table v-if="bindings.length">
          <thead>
            <tr>
              <th>飞书用户</th>
              <th>Open ID</th>
              <th>绑定节点</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in bindings" :key="b.id">
              <td>{{ b.feishu_name || '-' }}</td>
              <td><code>{{ b.feishu_open_id }}</code></td>
              <td>{{ b.node_hostname || b.node_id }}</td>
              <td>{{ formatTime(b.created_at) }}</td>
              <td>
                <button class="btn btn-small btn-danger" @click="removeBinding(b.id)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else style="color:#909399">暂无绑定记录</p>
      </div>

      <!-- 绑定码管理 -->
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3>绑定码</h3>
          <button class="btn btn-primary" @click="showBindCodeModal = true">生成绑定码</button>
        </div>
        <table v-if="bindCodes.length">
          <thead>
            <tr>
              <th>绑定码</th>
              <th>目标节点</th>
              <th>状态</th>
              <th>过期时间</th>
              <th>创建时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in bindCodes" :key="c.id">
              <td><code class="bind-code">{{ c.code }}</code></td>
              <td>{{ getNodeName(c.node_id) }}</td>
              <td>
                <span :class="['badge', c.is_used ? 'badge-offline' : 'badge-online']">
                  {{ c.is_used ? '已使用' : '有效' }}
                </span>
              </td>
              <td>{{ formatTime(c.expires_at) }}</td>
              <td>{{ formatTime(c.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else style="color:#909399">暂无绑定码</p>
      </div>
    </template>

    <!-- ═══ 对话记录 ═══ -->
    <template v-if="activeTab === 'conversations'">
      <!-- 会话列表 -->
      <div class="card" v-if="!selectedSession">
        <h3 style="margin-bottom:12px">会话列表</h3>
        <div class="filter-row">
          <div class="form-group" style="flex:1">
            <label>节点</label>
            <select v-model="sessionFilter.node_id" @change="fetchSessions">
              <option value="">全部节点</option>
              <option v-for="n in nodesList" :key="n.id" :value="n.id">{{ n.hostname }}</option>
            </select>
          </div>
        </div>
        <table v-if="sessions.length">
          <thead>
            <tr>
              <th>飞书用户</th>
              <th>Open ID</th>
              <th>消息数</th>
              <th>最近消息</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in sessions" :key="s.feishu_open_id" class="session-row" @click="openSession(s)">
              <td>{{ s.feishu_name || '-' }}</td>
              <td><code>{{ s.feishu_open_id }}</code></td>
              <td>{{ s.message_count }}</td>
              <td>{{ formatTime(s.last_message_at) }}</td>
              <td><button class="btn btn-small btn-primary" @click.stop="openSession(s)">查看</button></td>
            </tr>
          </tbody>
        </table>
        <p v-else style="color:#909399">暂无会话记录</p>
      </div>

      <!-- 会话详情 -->
      <div class="card" v-if="selectedSession">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3>
            <button class="btn btn-small" @click="selectedSession = null" style="margin-right:8px">← 返回</button>
            {{ selectedSession.feishu_name || selectedSession.feishu_open_id }} 的对话
          </h3>
        </div>
        <div class="chat-container">
          <div
            v-for="msg in sessionMessages"
            :key="msg.id"
            :class="['chat-bubble', msg.direction === 'inbound' ? 'bubble-inbound' : 'bubble-outbound']"
          >
            <div class="bubble-meta">
              <span>{{ msg.direction === 'inbound' ? '用户' : 'Bot' }}</span>
              <span>{{ formatTime(msg.created_at) }}</span>
            </div>
            <div class="bubble-content">{{ msg.content }}</div>
          </div>
        </div>
        <p v-if="!sessionMessages.length" style="color:#909399">暂无消息</p>
      </div>
    </template>

    <!-- ═══ 创建绑定弹窗 ═══ -->
    <div class="modal-overlay" v-if="showBindingModal" @click.self="showBindingModal = false">
      <div class="modal card">
        <h3>创建绑定</h3>
        <form @submit.prevent="submitBinding">
          <div class="form-group">
            <label>飞书 Open ID</label>
            <input v-model="bindingForm.feishu_open_id" required placeholder="ou_xxxxxxxx" />
          </div>
          <div class="form-group">
            <label>飞书用户名（可选）</label>
            <input v-model="bindingForm.feishu_name" placeholder="用于展示" />
          </div>
          <div class="form-group">
            <label>目标节点</label>
            <select v-model="bindingForm.node_id" required>
              <option value="" disabled>请选择节点</option>
              <option v-for="n in nodesList" :key="n.id" :value="n.id">{{ n.hostname }}</option>
            </select>
          </div>
          <p v-if="bindingError" class="error-msg">{{ bindingError }}</p>
          <div style="display:flex;gap:8px;margin-top:16px">
            <button class="btn btn-primary" type="submit">创建</button>
            <button class="btn" type="button" @click="showBindingModal = false" style="background:#eee">取消</button>
          </div>
        </form>
      </div>
    </div>

    <!-- ═══ 生成绑定码弹窗 ═══ -->
    <div class="modal-overlay" v-if="showBindCodeModal" @click.self="showBindCodeModal = false">
      <div class="modal card">
        <h3>生成绑定码</h3>
        <form @submit.prevent="submitBindCode">
          <div class="form-group">
            <label>目标节点</label>
            <select v-model="bindCodeForm.node_id" required>
              <option value="" disabled>请选择节点</option>
              <option v-for="n in nodesList" :key="n.id" :value="n.id">{{ n.hostname }}</option>
            </select>
          </div>
          <div class="form-group">
            <label>有效期（分钟）</label>
            <input v-model.number="bindCodeForm.expires_minutes" type="number" min="1" max="1440" />
          </div>
          <p v-if="bindCodeError" class="error-msg">{{ bindCodeError }}</p>
          <div style="display:flex;gap:8px;margin-top:16px">
            <button class="btn btn-primary" type="submit">生成</button>
            <button class="btn" type="button" @click="showBindCodeModal = false" style="background:#eee">取消</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { feishuGateway, nodes } from '../api.js'

export default {
  data() {
    return {
      activeTab: 'config',
      tabs: [
        { key: 'config', label: '网关配置' },
        { key: 'bindings', label: '绑定管理' },
        { key: 'conversations', label: '对话记录' },
      ],
      // 状态
      gwStatus: {},
      // 配置表单
      configForm: { app_id: '', app_secret: '', encrypt_key: '', verification_token: '' },
      configError: '',
      configSuccess: '',
      // 节点列表
      nodesList: [],
      // 绑定
      bindings: [],
      showBindingModal: false,
      bindingForm: { feishu_open_id: '', feishu_name: '', node_id: '' },
      bindingError: '',
      // 绑定码
      bindCodes: [],
      showBindCodeModal: false,
      bindCodeForm: { node_id: '', expires_minutes: 30 },
      bindCodeError: '',
      // 对话记录
      sessions: [],
      sessionFilter: { node_id: '' },
      selectedSession: null,
      sessionMessages: [],
      // 定时器
      timer: null,
    }
  },
  computed: {},
  watch: {
    activeTab(tab) {
      if (tab === 'bindings') {
        this.fetchBindings()
        this.fetchBindCodes()
      } else if (tab === 'conversations') {
        this.fetchSessions()
      }
    },
  },
  methods: {
    // ── 数据获取 ──
    async fetchStatus() {
      try {
        this.gwStatus = await feishuGateway.getStatus()
      } catch { /* 静默 */ }
    },
    async fetchConfig() {
      try {
        const cfg = await feishuGateway.getConfig()
        this.configForm.app_id = cfg.app_id || ''
        // secret 和 key 不回填（脱敏值）
      } catch { /* 可能尚未配置 */ }
    },
    async fetchNodes() {
      try {
        this.nodesList = await nodes.list()
      } catch { /* ignore */ }
    },
    async fetchBindings() {
      try {
        this.bindings = await feishuGateway.listBindings()
      } catch { /* ignore */ }
    },
    async fetchBindCodes() {
      try {
        this.bindCodes = await feishuGateway.listBindCodes()
      } catch { /* ignore */ }
    },
    async fetchSessions() {
      try {
        const nodeId = this.sessionFilter.node_id || undefined
        this.sessions = await feishuGateway.listSessions(nodeId)
      } catch { /* ignore */ }
    },
    async openSession(session) {
      this.selectedSession = session
      try {
        this.sessionMessages = await feishuGateway.getConversation(session.feishu_open_id, 200)
      } catch { this.sessionMessages = [] }
    },

    // ── 操作 ──
    async saveConfig() {
      this.configError = ''
      this.configSuccess = ''
      try {
        await feishuGateway.saveConfig(this.configForm)
        this.configSuccess = '配置已保存'
        this.configForm.app_secret = ''
        this.fetchStatus()
      } catch (e) {
        this.configError = e.message
      }
    },
    async startGateway() {
      try {
        await feishuGateway.start()
        this.fetchStatus()
      } catch (e) {
        alert('启动失败: ' + e.message)
      }
    },
    async stopGateway() {
      try {
        await feishuGateway.stop()
        this.fetchStatus()
      } catch (e) {
        alert('停止失败: ' + e.message)
      }
    },
    async submitBinding() {
      this.bindingError = ''
      try {
        await feishuGateway.createBinding(this.bindingForm)
        this.showBindingModal = false
        this.bindingForm = { feishu_open_id: '', feishu_name: '', node_id: '' }
        this.fetchBindings()
      } catch (e) {
        this.bindingError = e.message
      }
    },
    async removeBinding(id) {
      if (!confirm('确定要删除此绑定？')) return
      try {
        await feishuGateway.deleteBinding(id)
        this.fetchBindings()
      } catch (e) {
        alert('删除失败: ' + e.message)
      }
    },
    async submitBindCode() {
      this.bindCodeError = ''
      try {
        await feishuGateway.createBindCode(this.bindCodeForm)
        this.showBindCodeModal = false
        this.bindCodeForm = { node_id: '', expires_minutes: 30 }
        this.fetchBindCodes()
      } catch (e) {
        this.bindCodeError = e.message
      }
    },

    // ── 辅助 ──
    getNodeName(nodeId) {
      const n = this.nodesList.find(n => n.id === nodeId)
      return n ? n.hostname : nodeId
    },
    formatTime(t) {
      if (!t) return '-'
      try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
    },
    formatDuration(since) {
      if (!since) return '-'
      const ms = Date.now() - new Date(since).getTime()
      if (ms < 0) return '-'
      const h = Math.floor(ms / 3600000)
      const m = Math.floor((ms % 3600000) / 60000)
      return h > 0 ? `${h}小时${m}分钟` : `${m}分钟`
    },
  },
  mounted() {
    this.fetchStatus()
    this.fetchConfig()
    this.fetchNodes()
    this.fetchBindings()
    this.timer = setInterval(this.fetchStatus, 15000)
  },
  unmounted() {
    clearInterval(this.timer)
  },
}
</script>

<style scoped>
.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  border-bottom: 2px solid #ebeef5;
}
.tab-btn {
  padding: 10px 20px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 14px;
  color: #606266;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.2s;
}
.tab-btn.active {
  color: #409eff;
  border-bottom-color: #409eff;
  font-weight: 600;
}
.tab-btn:hover {
  color: #409eff;
}
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.info-label {
  display: inline-block;
  width: 100px;
  color: #909399;
  font-size: 13px;
}
.form-row {
  display: flex;
  gap: 16px;
}
.form-row .form-group {
  flex: 1;
}
.filter-row {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.filter-row .form-group {
  margin-bottom: 0;
}
code {
  font-size: 12px;
  background: #f4f4f5;
  padding: 2px 6px;
  border-radius: 3px;
}
.bind-code {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #409eff;
  background: #ecf5ff;
}
.msg-content {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 16px;
}
.success-msg {
  color: #67c23a;
  font-size: 13px;
  margin-top: 4px;
  margin-bottom: 8px;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
}
.modal {
  width: 460px;
}
.modal h3 {
  margin-bottom: 16px;
}
.auto-refresh-hint {
  font-size: 12px;
  color: #909399;
}
.session-row {
  cursor: pointer;
}
.session-row:hover {
  background: #f5f7fa;
}
.chat-container {
  max-height: 500px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 0;
}
.chat-bubble {
  max-width: 75%;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
}
.bubble-inbound {
  align-self: flex-start;
  background: #f4f4f5;
  color: #303133;
}
.bubble-outbound {
  align-self: flex-end;
  background: #ecf5ff;
  color: #303133;
}
.bubble-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
}
.bubble-content {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
