<template>
  <div>
    <div class="page-header">
      <h2>节点详情</h2>
      <router-link to="/" class="btn btn-small">← 返回仪表盘</router-link>
    </div>

    <p v-if="loading" style="color:var(--text-muted)">加载中...</p>
    <p v-else-if="error" class="error-msg">{{ error }}</p>

    <template v-else>
      <!-- 基本信息 -->
      <div class="card">
        <h3 style="margin-bottom:14px">基本信息</h3>
        <div class="info-grid">
          <div><span class="info-label">主机名</span>{{ node.hostname }}</div>
          <div><span class="info-label">心跳</span>
            <span :class="['badge', node.heartbeat_online ? 'badge-online' : 'badge-offline']">{{ node.heartbeat_online ? '在线' : '离线' }}</span>
          </div>
          <div><span class="info-label">控制通道</span>
            <span :class="['badge', node.gateway_ws_connected ? 'badge-online' : 'badge-offline']">{{ node.gateway_ws_connected ? '在线' : '未连接' }}</span>
          </div>
          <div><span class="info-label">节点 ID</span><code>{{ node.id }}</code></div>
          <div><span class="info-label">最近心跳</span>{{ formatTime(node.last_heartbeat) }}</div>
          <div><span class="info-label">策略版本</span>v{{ node.policy_version }}</div>
        </div>
      </div>

      <!-- Skill 分配 -->
      <div class="card" v-if="isAdmin">
        <h3 style="margin-bottom:14px">Skill 分配</h3>
        <div v-if="allSkills.length" class="checkbox-grid">
          <label v-for="s in allSkills" :key="s.name" class="checkbox-item">
            <input type="checkbox" :value="s.name" v-model="selectedSkills" style="width:auto" />
            {{ s.name }}
            <span class="checkbox-desc">{{ s.description }}</span>
          </label>
        </div>
        <p v-else style="color:var(--text-muted)">暂无可用 Skill</p>
        <button class="btn btn-primary" style="margin-top:14px" @click="savePolicy" :disabled="saving">{{ saving ? '保存中...' : '保存分配' }}</button>
      </div>

      <!-- MCP Server 分配 -->
      <div class="card" v-if="isAdmin">
        <h3 style="margin-bottom:14px">MCP Server 分配</h3>
        <div v-if="allMcpServers.length" class="checkbox-grid">
          <label v-for="m in allMcpServers" :key="m.name" class="checkbox-item">
            <input type="checkbox" :value="m.name" v-model="selectedMcpServers" style="width:auto" />
            {{ m.name }}
            <span class="checkbox-desc">({{ m.connection_type }}) {{ m.description }}</span>
          </label>
        </div>
        <p v-else style="color:var(--text-muted)">暂无可用 MCP Server</p>
        <button class="btn btn-primary" style="margin-top:14px" @click="savePolicy" :disabled="saving">{{ saving ? '保存中...' : '保存分配' }}</button>
      </div>

      <!-- Persona 分配 -->
      <div class="card" v-if="isAdmin">
        <h3 style="margin-bottom:14px">Persona 分配</h3>
        <div v-if="allPersonas.length" class="checkbox-grid">
          <label v-for="p in allPersonas" :key="p.name" class="checkbox-item">
            <input type="checkbox" :value="p.name" v-model="selectedPersonas" style="width:auto" />
            {{ p.name }}
            <span class="checkbox-desc">{{ p.description }}</span>
          </label>
        </div>
        <p v-else style="color:var(--text-muted)">暂无可用 Persona</p>
        <button class="btn btn-primary" style="margin-top:14px" @click="savePolicy" :disabled="saving">{{ saving ? '保存中...' : '保存分配' }}</button>
      </div>

      <!-- LLM Key 分配 -->
      <div class="card" v-if="isAdmin">
        <h3 style="margin-bottom:14px">LLM Key 分配</h3>
        <p style="margin-bottom:10px;color:var(--text-secondary)">
          当前：<code v-if="assignedLlmKeyId">{{ assignedLlmKeyId }}</code><span v-else>未分配</span>
        </p>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <select v-model="selectedLlmKeyId" :disabled="assigningLlm || !allLlmKeys.length" style="max-width:360px">
            <option value="" disabled>请选择 LLM Key</option>
            <option v-for="k in allLlmKeys" :key="k.id" :value="k.id">{{ k.name }} ({{ k.provider }}) · {{ k.current_concurrent }}/{{ k.max_concurrent }}</option>
          </select>
          <label style="display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--text-secondary)">
            <input type="checkbox" v-model="replaceExisting" :disabled="assigningLlm" style="width:auto" /> 替换现有
          </label>
          <button class="btn btn-primary btn-small" @click="assignLlmKey" :disabled="assigningLlm || !selectedLlmKeyId">{{ assigningLlm ? '分配中...' : '分配' }}</button>
        </div>
        <p v-if="llmAssignError" class="error-msg">{{ llmAssignError }}</p>
        <p v-if="llmAssignMessage" class="success-msg">{{ llmAssignMessage }}</p>
      </div>

      <!-- 配置编辑器 -->
      <div class="card" v-if="isAdmin">
        <h3 style="margin-bottom:14px">节点配置 (JSON)</h3>
        <details style="margin-bottom:10px;font-size:12px;color:var(--text-muted)">
          <summary style="cursor:pointer;user-select:none">可用配置字段参考</summary>
          <div style="margin-top:8px;padding:8px 12px;background:var(--bg-secondary);border-radius:6px;line-height:1.8">
            <code>channels.telegram.group_policy</code>: <b>"mention"</b> | "open" — 群组响应策略<br/>
            <code>channels.discord.group_policy</code>: <b>"mention"</b> | "open" — 群组响应策略<br/>
            <code>channels.feishu.react_emoji</code>: <b>"THUMBSUP"</b> — 消息反应表情<br/>
            <code>agents.defaults.model</code>: 模型名称<br/>
            <code>agents.defaults.temperature</code>: <b>0.1</b> — 温度参数<br/>
            <code>agents.defaults.provider</code>: <b>"auto"</b> — 指定 provider 或自动检测<br/>
            <code>tools.mcp_servers.{name}.type</code>: "stdio" | "sse" | "streamableHttp"<br/>
          </div>
        </details>
        <textarea v-model="configText" rows="10" spellcheck="false"></textarea>
        <p v-if="configError" class="error-msg">{{ configError }}</p>
        <button class="btn btn-primary" style="margin-top:12px" @click="saveConfig" :disabled="savingConfig">{{ savingConfig ? '保存中...' : '保存配置' }}</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { nodes, skills, mcpServers, personas, policies, configs, llmKeys, getCurrentUser } from '../api.js'

const route = useRoute()

const node = ref(null)
const loading = ref(true)
const error = ref('')

const allSkills = ref([])
const allMcpServers = ref([])
const allPersonas = ref([])
const allLlmKeys = ref([])

const selectedSkills = ref([])
const selectedMcpServers = ref([])
const selectedPersonas = ref([])
const selectedLlmKeyId = ref('')
const assignedLlmKeyId = ref('')
const replaceExisting = ref(false)

const assigningLlm = ref(false)
const llmAssignError = ref('')
const llmAssignMessage = ref('')

const configText = ref('{}')
const configError = ref('')
const saving = ref(false)
const savingConfig = ref(false)

const isAdmin = computed(() => {
  const u = getCurrentUser()
  return u && u.role === 'admin'
})

const fetchData = async () => {
  const id = route.params.id
  error.value = ''
  try {
    if (isAdmin.value) {
      const [n, sk, mcp, ps, keys] = await Promise.all([
        nodes.get(id), skills.list(), mcpServers.list(), personas.list(), llmKeys.list(),
      ])
      node.value = n
      allSkills.value = sk
      allMcpServers.value = mcp
      allPersonas.value = ps
      allLlmKeys.value = keys
      
      try {
        const policy = await policies.get(id)
        selectedSkills.value = policy.allowed_skills || []
        selectedMcpServers.value = policy.allowed_mcp_servers || []
        selectedPersonas.value = policy.allowed_personas || []
      } catch { /* no policy yet */ }
      
      try {
        const cfg = await configs.get(id)
        configText.value = JSON.stringify(cfg.config_data, null, 2)
        assignedLlmKeyId.value = cfg.config_data?.llm_key?.key_id || ''
        if (!selectedLlmKeyId.value && assignedLlmKeyId.value) {
          selectedLlmKeyId.value = assignedLlmKeyId.value
        }
      } catch {
        configText.value = '{}'
        assignedLlmKeyId.value = ''
      }
      return
    }
    node.value = await nodes.get(id)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const savePolicy = async () => {
  saving.value = true
  try {
    await policies.update(route.params.id, {
      allowed_skills: selectedSkills.value,
      allowed_mcp_servers: selectedMcpServers.value,
      allowed_personas: selectedPersonas.value,
    })
    node.value = await nodes.get(route.params.id)
  } catch (e) {
    alert('保存失败: ' + e.message)
  } finally {
    saving.value = false
  }
}

const saveConfig = async () => {
  configError.value = ''
  let parsed
  try {
    parsed = JSON.parse(configText.value)
  } catch {
    configError.value = 'JSON 格式无效'
    return
  }
  savingConfig.value = true
  try {
    await configs.update(route.params.id, { config_data: parsed })
    node.value = await nodes.get(route.params.id)
  } catch (e) {
    configError.value = '保存失败: ' + e.message
  } finally {
    savingConfig.value = false
  }
}

const assignLlmKey = async () => {
  llmAssignError.value = ''
  llmAssignMessage.value = ''
  if (!selectedLlmKeyId.value) {
    llmAssignError.value = '请选择 Key'
    return
  }
  assigningLlm.value = true
  try {
    const r = await nodes.assignLLMKey(route.params.id, {
      key_id: selectedLlmKeyId.value,
      replace_existing: replaceExisting.value
    })
    await fetchData()
    llmAssignMessage.value = r.idempotent ? '已分配此 Key（幂等）' : (r.replaced ? '已替换 LLM Key' : '分配成功')
  } catch (e) {
    llmAssignError.value = e.message
  } finally {
    assigningLlm.value = false
  }
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

<style scoped>
.info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.info-label { display: inline-block; width: 90px; color: var(--text-muted); font-size: 13px; }
</style>
