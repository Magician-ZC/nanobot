<template>
  <div>
    <div class="page-header">
      <h2>任务监控</h2>
      <span style="font-size:12px;color:var(--text-muted)">每 10 秒自动刷新</span>
    </div>
    <div class="card">
      <h3 style="margin-bottom:14px">活跃任务锁</h3>
      <p v-if="loading" style="color:var(--text-muted)">加载中...</p>
      <table v-else-if="tasksList.length">
        <thead><tr><th>资源</th><th>描述</th><th>节点</th><th>获取时间</th><th>过期时间</th></tr></thead>
        <tbody>
          <tr v-for="task in tasksList" :key="task.id">
            <td><code>{{ task.resource }}</code></td>
            <td>{{ task.description || '-' }}</td>
            <td><router-link :to="`/nodes/${task.node_id}`">{{ task.node_id.slice(0, 8) }}...</router-link></td>
            <td>{{ formatTime(task.acquired_at) }}</td>
            <td>{{ formatTime(task.expires_at) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">
        <div class="empty-state-icon">✅</div>
        <div class="empty-state-text">当前没有活跃的任务锁</div>
      </div>
    </div>
  </div>
</template>

<script>
import { tasks } from '../api.js'

export default {
  data() { return { tasksList: [], loading: true, timer: null } },
  methods: {
    async fetchTasks() {
      try { this.tasksList = await tasks.list() }
      catch { /* silent */ }
      finally { this.loading = false }
    },
    formatTime(t) {
      if (!t) return '-'
      try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
    },
  },
  mounted() {
    this.fetchTasks()
    this.timer = setInterval(this.fetchTasks, 10000)
  },
  unmounted() { clearInterval(this.timer) },
}
</script>
