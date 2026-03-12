<template>
  <div>
    <div class="page-header">
      <h2>飞书网关</h2>
      <span style="font-size:12px;color:var(--text-muted)">每 15 秒自动刷新状态</span>
    </div>

    <div class="tab-bar">
      <button v-for="tab in tabs" :key="tab.key" :class="['tab-btn', { active: activeTab === tab.key }]" @click="activeTab = tab.key">{{ tab.label }}</button>
    </div>

    <!-- 网关配置 -->
    <template v-if="activeTab === 'config'">
      <div class="card">
        <h3 style="margin-bottom:14px">连接状态</h3>
        <div class="info-grid">
          <div><span class="info-label">状态</span><span :class="['badge', gwStatus.is_connected ? 'badge-online' : 'badge-offline']">{{ gwStatus.is_connected ? '已连接' : '未连接' }}</span></div>
          <div><span class="info-label">已连接</span>{{ formatDuration(gwStatus.connected_since) }}</div>
          <div><span class="info-label">在线节点</span>{{ gwStatus.connected_nodes ?? 0 }}</div>
          <div><span class="info-label">绑定总数</span>{{ gwStatus.total_bindings ?? 0 }}</div>
          <div><span class="info-label">最近消息</span>{{ formatTime(gwStatus.last_message_at) }}</div>
        </div>
        <div style="margin-top:14px;display:flex;gap:8px">
          <button class="btn btn-success btn-small" @click="startGateway" :disabled="gwStatus.is_connected">启动</button>
          <button class="btn btn-danger btn-small" @click="stopGateway" :disabled="!gwStatus.is_connected">停止</button>
        </div>
      </div>
      <div class="card">
        <h3 style="margin-bottom:14px">飞书应用配置</h3>
        <form @submit.prevent="saveConfig">
          <div style="display:flex;gap:12px">
            <div class="form-group" style="flex:1"><label>App ID</label><input v-model="configForm.app_id" required placeholder="App ID" /></div>
            <div class="form-group" style="flex:1"><label>App Secret</label><input v-model="configForm.app_secret" type="password" required placeholder="App Secret" /></div>
          </div>
          <div style="display:flex;gap:12px">
            <div class="form-group" style="flex:1"><label>Encrypt Key</label><input v-model="configForm.encrypt_key" placeholder="可选" /></div>
            <div class="form-group" style="flex:1"><label>Verification Token</label><input v-model="configForm.verification_token" placeholder="可选" /></div>
          </div>
          <p v-if="configError" class="error-msg">{{ configError }}</p>
          <p v-if="configSuccess" class="success-msg">{{ configSuccess }}</p>
          <button class="btn btn-primary" type="submit">保存配置</button>
        </form>
      </div>
    </template>

    <!-- 绑定管理 -->
    <template v-if="activeTab === 'bindings'">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
          <h3>用户绑定</h3>
          <button class="btn btn-primary btn-small" @click="showBindingModal = true">创建绑定</button>
        </div>
        <table v-if="bindings.length">
          <thead><tr><th>飞书用户</th><th>Open ID</th><th>绑定节点</th><th>创建时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="b in bindings" :key="b.id">
              <td>{{ b.feishu_name || '-' }}</td>
              <td><code>{{ b.feishu_open_id }}</code></td>
              <td>{{ b.node_hostname || b.node_id }}</td>
              <td>{{ formatTime(b.created_at) }}</td>
              <td><button class="btn btn-small btn-danger" @click="removeBinding(b.id)">删除</button></td>
            </tr>
          </tbody>
        </table>
        <p v-else style="color:var(--text-muted)">暂无绑定</p>
      </div>
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
          <h3>绑定码</h3>
          <button class="btn btn-primary btn-small" @click="showBindCodeModal = true">生成绑定码</button>
        </div>
        <table v-if="bindCodes.length">
          <thead><tr><th>绑定码</th><th>目标节点</th><th>状态</th><th>过期时间</th></tr></thead>
          <tbody>
            <tr v-for="c in bindCodes" :key="c.id">
              <td><code class="bind-code">{{ c.code }}</code></td>
              <td>{{ getNodeName(c.node_id) }}</td>
              <td><span :class="['badge', c.is_used ? 'badge-offline' : 'badge-online']">{{ c.is_used ? '已使用' : '有效' }}</span></td>
              <td>{{ formatTime(c.expires_at) }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else style="color:var(--text-muted)">暂无绑定码</p>
      </div>
    </template>

    <!-- 对话记录 -->
    <template v-if="activeTab === 'conversations'">
      <div class="card" v-if="!selectedSession">
        <h3 style="margin-bottom:14px">会话列表</h3>
        <div style="margin-bottom:14px">
          <select v-model="sessionFilter.node_id" @change="fetchSessions" style="max-width:300px">
            <option value="">全部节点</option>
            <option v-for="n in nodesList" :key="n.id" :value="n.id">{{ n.hostname }}</option>
          </select>
        </div>
        <table v-if="sessions.length">
          <thead><tr><th>飞书用户</th><th>Open ID</th><th>消息数</th><th>最近消息</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="s in sessions" :key="s.feishu_open_id" style="cursor:pointer" @click="openSession(s)">
              <td>{{ s.feishu_name || '-' }}</td>
              <td><code>{{ s.feishu_open_id }}</code></td>
              <td>{{ s.message_count }}</td>
              <td>{{ formatTime(s.last_message_at) }}</td>
              <td><button class="btn btn-small btn-primary" @click.stop="openSession(s)">查看</button></td>
            </tr>
          </tbody>
        </table>
        <p v-else style="color:var(--text-muted)">暂无会话</p>
      </div>
      <div class="card" v-if="selectedSession">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
          <button class="btn btn-small" @click="selectedSession = null">← 返回</button>
          <h3>{{ selectedSession.feishu_name || selectedSession.feishu_open_id }}</h3>
        </div>
        <div class="chat-container">
          <div v-for="msg in sessionMessages" :key="msg.id" :class="['chat-bubble', msg.direction === 'inbound' ? 'bubble-in' : 'bubble-out']">
            <div class="bubble-meta">
              <span>{{ msg.direction === 'inbound' ? '用户' : 'Bot' }}</span>
              <span>{{ formatTime(msg.created_at) }}</span>
            </div>
            <div style="white-space:pre-wrap;word-break:break-word">{{ msg.content }}</div>
          </div>
        </div>
        <p v-if="!sessionMessages.length" style="color:var(--text-muted)">暂无消息</p>
      </div>
    </template>

    <!-- 创建绑定弹窗 -->
    <div class="modal-overlay" v-if="showBindingModal" @click.self="showBindingModal = false">
      <div class="modal-card" style="width:440px">
        <h3>创建绑定</h3>
        <form @submit.prevent="submitBinding">
          <div class="form-group"><label>飞书 Open ID</label><input v-model="bindingForm.feishu_open_id" required placeholder="ou_xxxxxxxx" /></div>
          <div class="form-group"><label>飞书用户名</label><input v-model="bindingForm.feishu_name" placeholder="可选" /></div>
          <div class="form-group"><label>目标节点</label>
            <select v-model="bindingForm.node_id" required>
              <option value="" disabled>请选择</option>
              <option v-for="n in nodesList" :key="n.id" :value="n.id">{{ n.hostname }}</option>
            </select>
          </div>
          <p v-if="bindingError" class="error-msg">{{ bindingError }}</p>
          <div class="form-actions">
            <button class="btn" type="button" @click="showBindingModal = false">取消</button>
            <button class="btn btn-primary" type="submit">创建</button>
          </div>
        </form>
      </div>
    </div>

    <!-- 生成绑定码弹窗 -->
    <div class="modal-overlay" v-if="showBindCodeModal" @click.self="showBindCodeModal = false">
      <div class="modal-card" style="width:440px">
        <h3>生成绑定码</h3>
        <form @submit.prevent="submitBindCode">
          <div class="form-group"><label>目标节点</label>
            <select v-model="bindCodeForm.node_id" required>
              <option value="" disabled>请选择</option>
              <option v-for="n in nodesList" :key="n.id" :value="n.id">{{ n.hostname }}</option>
            </select>
          </div>
          <div class="form-group"><label>有效期（分钟）</label><input v-model.number="bindCodeForm.expires_minutes" type="number" min="1" max="1440" /></div>
          <p v-if="bindCodeError" class="error-msg">{{ bindCodeError }}</p>
          <div class="form-actions">
            <button class="btn" type="button" @click="showBindCodeModal = false">取消</button>
            <button class="btn btn-primary" type="submit">生成</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { feishuGateway, nodes } from '../api.js'

const activeTab = ref('config')
const tabs = ref([
  { key: 'config', label: '网关配置' },
  { key: 'bindings', label: '绑定管理' },
  { key: 'conversations', label: '对话记录' }
])

const gwStatus = ref({})
const configForm = ref({ app_id: '', app_secret: '', encrypt_key: '', verification_token: '' })
const configError = ref('')
const configSuccess = ref('')
const nodesList = ref([])

const bindings = ref([])
const showBindingModal = ref(false)
const bindingForm = ref({ feishu_open_id: '', feishu_name: '', node_id: '' })
const bindingError = ref('')

const bindCodes = ref([])
const showBindCodeModal = ref(false)
const bindCodeForm = ref({ node_id: '', expires_minutes: 30 })
const bindCodeError = ref('')

const sessions = ref([])
const sessionFilter = ref({ node_id: '' })
const selectedSession = ref(null)
const sessionMessages = ref([])

let timer = null

const fetchStatus = async () => {
  try {
    gwStatus.value = await feishuGateway.getStatus()
  } catch { /* silent */ }
}

const fetchConfig = async () => {
  try {
    const cfg = await feishuGateway.getConfig()
    configForm.value.app_id = cfg.app_id || ''
  } catch { /* not configured */ }
}

const fetchNodes = async () => {
  try {
    nodesList.value = await nodes.list()
  } catch { /* ignore */ }
}

const fetchBindings = async () => {
  try {
    bindings.value = await feishuGateway.listBindings()
  } catch { /* ignore */ }
}

const fetchBindCodes = async () => {
  try {
    bindCodes.value = await feishuGateway.listBindCodes()
  } catch { /* ignore */ }
}

const fetchSessions = async () => {
  try {
    sessions.value = await feishuGateway.listSessions(sessionFilter.value.node_id || undefined)
  } catch { /* ignore */ }
}

const openSession = async (s) => {
  selectedSession.value = s
  try {
    sessionMessages.value = await feishuGateway.getConversation(s.feishu_open_id, 200)
  } catch {
    sessionMessages.value = []
  }
}

const saveConfig = async () => {
  configError.value = ''
  configSuccess.value = ''
  try {
    await feishuGateway.saveConfig(configForm.value)
    configSuccess.value = '配置已保存'
    configForm.value.app_secret = ''
    fetchStatus()
  } catch (e) {
    configError.value = e.message
  }
}

const startGateway = async () => {
  try {
    await feishuGateway.start()
    fetchStatus()
  } catch (e) {
    alert('启动失败: ' + e.message)
  }
}

const stopGateway = async () => {
  try {
    await feishuGateway.stop()
    fetchStatus()
  } catch (e) {
    alert('停止失败: ' + e.message)
  }
}

const submitBinding = async () => {
  bindingError.value = ''
  try {
    await feishuGateway.createBinding(bindingForm.value)
    showBindingModal.value = false
    bindingForm.value = { feishu_open_id: '', feishu_name: '', node_id: '' }
    fetchBindings()
  } catch (e) {
    bindingError.value = e.message
  }
}

const removeBinding = async (id) => {
  if (!confirm('确定删除此绑定？')) return
  try {
    await feishuGateway.deleteBinding(id)
    fetchBindings()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

const submitBindCode = async () => {
  bindCodeError.value = ''
  try {
    await feishuGateway.createBindCode(bindCodeForm.value)
    showBindCodeModal.value = false
    bindCodeForm.value = { node_id: '', expires_minutes: 30 }
    fetchBindCodes()
  } catch (e) {
    bindCodeError.value = e.message
  }
}

const getNodeName = (nodeId) => {
  const n = nodesList.value.find(n => n.id === nodeId)
  return n ? n.hostname : nodeId
}

const formatTime = (t) => {
  if (!t) return '-'
  try {
    return new Date(t).toLocaleString('zh-CN')
  } catch {
    return t
  }
}

const formatDuration = (since) => {
  if (!since) return '-'
  const ms = Date.now() - new Date(since).getTime()
  if (ms < 0) return '-'
  const h = Math.floor(ms / 3600000)
  const m = Math.floor((ms % 3600000) / 60000)
  return h > 0 ? `${h}小时${m}分钟` : `${m}分钟`
}

watch(activeTab, (tab) => {
  if (tab === 'bindings') {
    fetchBindings()
    fetchBindCodes()
  } else if (tab === 'conversations') {
    fetchSessions()
  }
})

onMounted(() => {
  fetchStatus()
  fetchConfig()
  fetchNodes()
  fetchBindings()
  timer = setInterval(fetchStatus, 15000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.info-label { display: inline-block; width: 100px; color: var(--text-muted); font-size: 13px; }
.bind-code { font-size: 16px; font-weight: 700; letter-spacing: 2px; color: var(--accent); background: var(--accent-light); }
.chat-container { max-height: 500px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding: 8px 0; }
.chat-bubble { max-width: 75%; padding: 10px 14px; border-radius: 10px; font-size: 14px; line-height: 1.5; }
.bubble-in { align-self: flex-start; background: #f3f4f6; }
.bubble-out { align-self: flex-end; background: var(--accent-light); }
.bubble-meta { display: flex; justify-content: space-between; gap: 12px; font-size: 11px; color: var(--text-muted); margin-bottom: 4px; }
</style>
