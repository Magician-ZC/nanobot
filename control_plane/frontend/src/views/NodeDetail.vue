<template>
  <div>
    <div class="page-header">
      <h2>节点详情</h2>
      <router-link to="/" class="btn btn-small btn-primary">返回仪表盘</router-link>
    </div>

    <p v-if="loading" style="color:#909399">加载中...</p>
    <p v-else-if="error" class="error-msg">{{ error }}</p>

    <template v-else>
      <!-- 基本信息 -->
      <div class="card">
        <h3 style="margin-bottom:12px">基本信息</h3>
        <div class="info-grid">
          <div><span class="info-label">主机名</span>{{ node.hostname }}</div>
          <div><span class="info-label">心跳状态</span>
            <span :class="['badge', node.heartbeat_online ? 'badge-online' : 'badge-offline']">
              {{ node.heartbeat_online ? '在线' : '离线' }}
            </span>
          </div>
          <div><span class="info-label">控制通道</span>
            <span :class="['badge', node.gateway_ws_connected ? 'badge-online' : 'badge-offline']">
              {{ node.gateway_ws_connected ? '在线' : '未连接' }}
            </span>
          </div>
          <div><span class="info-label">节点 ID</span><code>{{ node.id }}</code></div>
          <div><span class="info-label">最近心跳</span>{{ formatTime(node.last_heartbeat) }}</div>
          <div><span class="info-label">策略版本</span>v{{ node.policy_version }}</div>
          <div><span class="info-label">配置版本</span>v{{ node.config_version }}</div>
        </div>
      </div>

      <!-- Skill 分配 -->
      <div class="card" v-if="isAdmin">
        <h3 style="margin-bottom:12px">Skill 分配</h3>
        <div v-if="allSkills.length" class="checkbox-grid">
          <label v-for="s in allSkills" :key="s.name" class="checkbox-item">
            <input type="checkbox" :value="s.name" v-model="selectedSkills" />
            {{ s.name }}
            <span class="checkbox-desc">{{ s.description }}</span>
          </label>
        </div>
        <p v-else style="color:#909399">暂无可用 Skill</p>
        <button class="btn btn-primary" style="margin-top:12px" @click="savePolicy" :disabled="saving">
          {{ saving ? '保存中...' : '保存 Skill 分配' }}
        </button>
      </div>

      <!-- MCP Server 分配 -->
      <div class="card" v-if="isAdmin">
        <h3 style="margin-bottom:12px">MCP Server 分配</h3>
        <div v-if="allMcpServers.length" class="checkbox-grid">
          <label v-for="m in allMcpServers" :key="m.name" class="checkbox-item">
            <input type="checkbox" :value="m.name" v-model="selectedMcpServers" />
            {{ m.name }}
            <span class="checkbox-desc">({{ m.connection_type }}) {{ m.description }}</span>
          </label>
        </div>
        <p v-else style="color:#909399">暂无可用 MCP Server</p>
        <button class="btn btn-primary" style="margin-top:12px" @click="savePolicy" :disabled="saving">
          {{ saving ? '保存中...' : '保存 MCP 分配' }}
        </button>
      </div>

      <!-- LLM Key 分配 -->
      <div class="card" v-if="isAdmin">
        <h3 style="margin-bottom:12px">LLM Key 分配</h3>
        <p style="margin-bottom:8px;color:#606266">
          当前分配：
          <code v-if="assignedLlmKeyId">{{ assignedLlmKeyId }}</code>
          <span v-else>未分配</span>
        </p>
        <div class="llm-assign-row">
          <select v-model="selectedLlmKeyId" :disabled="assigningLlm || !allLlmKeys.length">
            <option value="" disabled>请选择 LLM Key</option>
            <option v-for="k in allLlmKeys" :key="k.id" :value="k.id">
              {{ k.name }} ({{ k.provider }}) · {{ k.current_concurrent }}/{{ k.max_concurrent }}
            </option>
          </select>
          <label class="replace-option">
            <input type="checkbox" v-model="replaceExisting" :disabled="assigningLlm" />
            允许替换现有分配
          </label>
          <button class="btn btn-primary" @click="assignLlmKey" :disabled="assigningLlm || !selectedLlmKeyId">
            {{ assigningLlm ? '分配中...' : '分配 LLM' }}
          </button>
        </div>
        <p v-if="llmAssignError" class="error-msg">{{ llmAssignError }}</p>
        <p v-if="llmAssignMessage" class="success-msg">{{ llmAssignMessage }}</p>
      </div>

      <!-- 配置编辑器 -->
      <div class="card" v-if="isAdmin">
        <h3 style="margin-bottom:12px">节点配置 (JSON)</h3>
        <textarea
          v-model="configText"
          rows="12"
          style="font-family:monospace;font-size:13px"
          spellcheck="false"
        ></textarea>
        <p v-if="configError" class="error-msg">{{ configError }}</p>
        <button class="btn btn-primary" style="margin-top:12px" @click="saveConfig" :disabled="savingConfig">
          {{ savingConfig ? '保存中...' : '保存配置' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script>
import { nodes, skills, mcpServers, policies, configs, llmKeys, getCurrentUser } from '../api.js'

export default {
  data() {
    return {
      node: null,
      loading: true,
      error: '',
      allSkills: [],
      allMcpServers: [],
      allLlmKeys: [],
      selectedSkills: [],
      selectedMcpServers: [],
      selectedLlmKeyId: '',
      assignedLlmKeyId: '',
      replaceExisting: false,
      assigningLlm: false,
      llmAssignError: '',
      llmAssignMessage: '',
      configText: '{}',
      configError: '',
      saving: false,
      savingConfig: false,
    }
  },
  computed: {
    isAdmin() {
      const u = getCurrentUser()
      return u && u.role === 'admin'
    },
  },
  methods: {
    async fetchData() {
      const id = this.$route.params.id
      this.error = ''
      try {
        if (this.isAdmin) {
          const [node, sk, mcp, keys] = await Promise.all([
            nodes.get(id),
            skills.list(),
            mcpServers.list(),
            llmKeys.list(),
          ])
          this.node = node
          this.allSkills = sk
          this.allMcpServers = mcp
          this.allLlmKeys = keys
          try {
            const policy = await policies.get(id)
            this.selectedSkills = policy.allowed_skills || []
            this.selectedMcpServers = policy.allowed_mcp_servers || []
          } catch {
            // 节点可能还没有策略
          }
          try {
            const cfg = await configs.get(id)
            this.configText = JSON.stringify(cfg.config_data, null, 2)
            this.assignedLlmKeyId = cfg.config_data?.llm_key?.key_id || ''
            if (!this.selectedLlmKeyId && this.assignedLlmKeyId) {
              this.selectedLlmKeyId = this.assignedLlmKeyId
            }
          } catch {
            this.configText = '{}'
            this.assignedLlmKeyId = ''
          }
          return
        }

        this.node = await nodes.get(id)
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    async savePolicy() {
      this.saving = true
      try {
        await policies.update(this.$route.params.id, {
          allowed_skills: this.selectedSkills,
          allowed_mcp_servers: this.selectedMcpServers,
        })
        // 刷新节点信息以更新版本号
        this.node = await nodes.get(this.$route.params.id)
      } catch (e) {
        alert('保存失败: ' + e.message)
      } finally {
        this.saving = false
      }
    },
    async saveConfig() {
      this.configError = ''
      let parsed
      try {
        parsed = JSON.parse(this.configText)
      } catch {
        this.configError = 'JSON 格式无效'
        return
      }
      this.savingConfig = true
      try {
        await configs.update(this.$route.params.id, { config_data: parsed })
        this.node = await nodes.get(this.$route.params.id)
      } catch (e) {
        this.configError = '保存失败: ' + e.message
      } finally {
        this.savingConfig = false
      }
    },
    async assignLlmKey() {
      this.llmAssignError = ''
      this.llmAssignMessage = ''
      if (!this.selectedLlmKeyId) {
        this.llmAssignError = '请选择一个 LLM Key'
        return
      }

      this.assigningLlm = true
      try {
        const result = await nodes.assignLLMKey(this.$route.params.id, {
          key_id: this.selectedLlmKeyId,
          replace_existing: this.replaceExisting,
        })
        await this.fetchData()
        this.llmAssignMessage = result.idempotent
          ? '该节点已分配此 Key（幂等成功）'
          : (result.replaced ? '已替换并分配新的 LLM Key' : 'LLM Key 分配成功')
      } catch (e) {
        this.llmAssignError = e.message
      } finally {
        this.assigningLlm = false
      }
    },
    formatTime(t) {
      if (!t) return '-'
      try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
    },
  },
  mounted() {
    this.fetchData()
  },
}
</script>

<style scoped>
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.info-label {
  display: inline-block;
  width: 90px;
  color: #909399;
  font-size: 13px;
}
code {
  font-size: 12px;
  background: #f4f4f5;
  padding: 2px 6px;
  border-radius: 3px;
}
.checkbox-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
}
.checkbox-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  cursor: pointer;
}
.checkbox-desc {
  color: #909399;
  font-size: 12px;
}
.llm-assign-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.replace-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}
.success-msg {
  color: #67c23a;
  margin-top: 8px;
}
</style>
