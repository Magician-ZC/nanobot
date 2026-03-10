<template>
  <div>
    <div class="page-header">
      <h2>仪表盘</h2>
      <span style="font-size:12px;color:var(--text-muted)">每 15 秒自动刷新</span>
    </div>

    <div class="stats-row">
      <div class="stat-card card">
        <div class="stat-value">{{ nodesList.length }}</div>
        <div class="stat-label">节点总数</div>
      </div>
      <div class="stat-card card">
        <div class="stat-value online">{{ onlineCount }}</div>
        <div class="stat-label">在线</div>
      </div>
      <div class="stat-card card">
        <div class="stat-value offline">{{ offlineCount }}</div>
        <div class="stat-label">离线</div>
      </div>
      <div class="stat-card card" v-if="isAdmin">
        <div class="stat-value">{{ usersList.length }}</div>
        <div class="stat-label">用户数</div>
      </div>
    </div>

    <div class="card">
      <h3 style="margin-bottom:14px">Agent 节点</h3>
      <p v-if="loading" style="color:var(--text-muted)">加载中...</p>
      <table v-else-if="nodesList.length">
        <thead>
          <tr>
            <th>主机名</th>
            <th>状态</th>
            <th>最近心跳</th>
            <th>策略版本</th>
            <th>配置版本</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="node in nodesList" :key="node.id">
            <td style="font-weight:500">{{ node.hostname }}</td>
            <td>
              <span :class="['badge', node.status === 'online' ? 'badge-online' : 'badge-offline']">
                {{ node.status === 'online' ? '在线' : '离线' }}
              </span>
            </td>
            <td>{{ formatTime(node.last_heartbeat) }}</td>
            <td>v{{ node.policy_version }}</td>
            <td>v{{ node.config_version }}</td>
            <td>
              <router-link :to="`/nodes/${node.id}`" class="btn btn-small btn-primary">详情</router-link>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">
        <div class="empty-state-icon">📡</div>
        <div class="empty-state-text">暂无节点，请先部署 Agent Node</div>
      </div>
    </div>

    <div class="card" v-if="isAdmin && usersList.length">
      <h3 style="margin-bottom:14px">用户列表</h3>
      <table>
        <thead>
          <tr>
            <th>用户名</th>
            <th>角色</th>
            <th>状态</th>
            <th>创建时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in usersList" :key="user.id">
            <td style="font-weight:500">{{ user.username }}</td>
            <td>
              <span :class="['badge', user.role === 'admin' ? 'badge-admin' : 'badge-operator']">
                {{ user.role }}
              </span>
            </td>
            <td>{{ user.is_active ? '启用' : '禁用' }}</td>
            <td>{{ formatTime(user.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
import { nodes, users, getCurrentUser } from '../api.js'

export default {
  data() {
    return { nodesList: [], usersList: [], loading: true, timer: null }
  },
  computed: {
    isAdmin() {
      const u = getCurrentUser()
      return u && u.role === 'admin'
    },
    onlineCount() { return this.nodesList.filter(n => n.status === 'online').length },
    offlineCount() { return this.nodesList.filter(n => n.status !== 'online').length },
  },
  methods: {
    async fetchData() {
      try {
        this.nodesList = await nodes.list()
        if (this.isAdmin) this.usersList = await users.list()
      } catch { /* keep last */ }
      finally { this.loading = false }
    },
    formatTime(t) {
      if (!t) return '-'
      try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
    },
  },
  mounted() {
    this.fetchData()
    this.timer = setInterval(this.fetchData, 15000)
  },
  unmounted() { clearInterval(this.timer) },
}
</script>
