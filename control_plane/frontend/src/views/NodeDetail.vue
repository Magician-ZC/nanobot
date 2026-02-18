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
          <div><span class="info-label">状态</span>
            <span :class="['badge', node.status === 'online' ? 'badge-online' : 'badge-offline']">
              {{ node.status === 'online' ? '在线' : '离线' }}
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
import { nodes, skills, mcpServers, policies, configs, getCurrentUser } from '../api.js'

export default {
  data() {
    return {
      node: null,
      loading: true,
      error: '',
      allSkills: [],
      allMcpServers: [],
      selectedSkills: [],
      selectedMcpServers: [],
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
      try {
        this.node = await nodes.get(id)
        if (this.isAdmin) {
          const [sk, mcp] = await Promise.all([skills.list(), mcpServers.list()])
          this.allSkills = sk
          this.allMcpServers = mcp
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
          } catch {
            this.configText = '{}'
          }
        }
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
</style>
