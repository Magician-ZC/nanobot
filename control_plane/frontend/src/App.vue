<template>
  <div id="app-root">
    <nav v-if="loggedIn" class="navbar">
      <div class="nav-brand">
        <router-link to="/">Nanobot Control Plane</router-link>
      </div>
      <div class="nav-links">
        <router-link to="/">仪表盘</router-link>
        <router-link to="/users" v-if="isAdmin">用户管理</router-link>
        <router-link to="/tasks">任务监控</router-link>
        <router-link to="/token-usage">Token 用量</router-link>
        <router-link to="/feishu-gateway" v-if="isAdmin">飞书网关</router-link>
        <span class="nav-user">{{ userRole }}</span>
        <button class="btn btn-small btn-danger" @click="logout">退出</button>
      </div>
    </nav>
    <main class="container">
      <router-view />
    </main>
  </div>
</template>

<script>
import { getCurrentUser, removeToken } from './api.js'

export default {
  computed: {
    loggedIn() {
      // 响应路由变化重新计算
      this.$route
      return !!getCurrentUser()
    },
    isAdmin() {
      const u = getCurrentUser()
      return u && u.role === 'admin'
    },
    userRole() {
      const u = getCurrentUser()
      return u ? u.role : ''
    },
  },
  methods: {
    logout() {
      removeToken()
      this.$router.push('/login')
    },
  },
}
</script>

<style scoped>
.navbar {
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  padding: 0 24px;
  display: flex;
  align-items: center;
  height: 56px;
  margin-bottom: 20px;
}
.nav-brand a {
  font-size: 18px;
  font-weight: 700;
  color: #333;
}
.nav-links {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 16px;
}
.nav-links a {
  font-size: 14px;
  color: #606266;
}
.nav-links a.router-link-active {
  color: #409eff;
  font-weight: 600;
}
.nav-user {
  font-size: 13px;
  color: #909399;
  padding: 2px 8px;
  background: #f4f4f5;
  border-radius: 4px;
}
</style>
