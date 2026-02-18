<template>
  <div class="login-wrapper">
    <div class="login-card card">
      <h2>Nanobot Control Plane</h2>
      <p class="login-subtitle">请登录以继续</p>
      <form @submit.prevent="handleLogin">
        <div class="form-group">
          <label for="username">用户名</label>
          <input id="username" v-model="username" autocomplete="username" required />
        </div>
        <div class="form-group">
          <label for="password">密码</label>
          <input id="password" v-model="password" type="password" autocomplete="current-password" required />
        </div>
        <p v-if="error" class="error-msg">{{ error }}</p>
        <button class="btn btn-primary" style="width:100%" :disabled="loading">
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
  min-height: 80vh;
}
.login-card {
  width: 380px;
  text-align: center;
}
.login-card h2 {
  margin-bottom: 4px;
}
.login-subtitle {
  color: #909399;
  font-size: 14px;
  margin-bottom: 24px;
}
.login-card .form-group {
  text-align: left;
}
</style>
