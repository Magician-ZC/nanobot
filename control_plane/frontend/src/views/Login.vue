<template>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="login-logo">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
      </div>
      <h2>Nanobot Control Plane</h2>
      <p class="login-subtitle">登录以管理你的 Agent 集群</p>
      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label for="username">用户名</label>
          <input id="username" v-model="username" autocomplete="username" required placeholder="请输入用户名" />
        </div>
        <div class="form-group">
          <label for="password">密码</label>
          <input id="password" v-model="password" type="password" autocomplete="current-password" required placeholder="请输入密码" />
        </div>
        <p v-if="error" class="error-msg">{{ error }}</p>
        <button class="btn btn-primary login-btn" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script>
import { auth, setToken } from '../api.js'

export default {
  data() {
    return { username: '', password: '', error: '', loading: false }
  },
  methods: {
    async handleLogin() {
      this.error = ''
      this.loading = true
      try {
        const res = await auth.login(this.username, this.password)
        setToken(res.access_token)
        this.$router.push('/')
      } catch (e) {
        this.error = e.message === 'Unauthorized' ? '用户名或密码错误' : e.message
      } finally {
        this.loading = false
      }
    },
  },
}
</script>

<style scoped>
.login-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1d23 0%, #2d1b69 100%);
}
.login-card {
  width: 400px;
  background: #fff;
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  text-align: center;
}
.login-logo { margin-bottom: 16px; }
.login-card h2 {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 4px;
  color: var(--text-primary);
}
.login-subtitle {
  color: var(--text-muted);
  font-size: 14px;
  margin-bottom: 28px;
}
.login-card .form-group { text-align: left; }
.login-btn { width: 100%; padding: 11px; font-size: 14px; margin-top: 4px; }
</style>
