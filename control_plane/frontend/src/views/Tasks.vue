<template>
  <div>
    <div class="page-header">
      <h2>任务监控</h2>
      <span class="auto-refresh-hint">每 10 秒自动刷新</span>
    </div>

    <div class="card">
      <h3 style="margin-bottom:12px">活跃任务锁</h3>
      <p v-if="loading" style="color:#909399">加载中...</p>
      <table v-else-if="tasksList.length">
        <thead>
          <tr>
            <th>资源</th>
            <th>描述</th>
            <th>节点 ID</th>
            <th>获取时间</th>
            <th>过期时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasksList" :key="task.id">
            <td><code>{{ task.resource }}</code></td>
            <td>{{ task.description || '-' }}</td>
            <td>
              <router-link :to="`/nodes/${task.node_id}`">
                {{ task.node_id.slice(0, 8) }}...
              </router-link>
            </td>
            <td>{{ formatTime(task.acquired_at) }}</td>
            <td>{{ formatTime(task.expires_at) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else style="color:#909399">当前没有活跃的任务锁</p>
    </div>
  </div>
</template>

<script>
import { tasks } from '../api.js'

export default {
  data() {
    return { tasksList: [], loading: true, timer: null }
  },
  methods: {
    async fetchTasks() {
      try {
        this.tasksList = await tasks.list()
      } catch {
        // 静默处理
      } finally {
        this.loading = false
      }
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
  unmounted() {
    clearInterval(this.timer)
  },
}
</script>

<style scoped>
.auto-refresh-hint {
  font-size: 12px;
  color: #909399;
}
code {
  font-size: 12px;
  background: #f4f4f5;
  padding: 2px 6px;
  border-radius: 3px;
}
</style>
