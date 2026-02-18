<template>
  <div>
    <div class="page-header">
      <h2>用户管理</h2>
      <button class="btn btn-primary" @click="showCreate = true">创建用户</button>
    </div>

    <!-- 用户列表 -->
    <div class="card">
      <table v-if="usersList.length">
        <thead>
          <tr>
            <th>用户名</th>
            <th>角色</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in usersList" :key="user.id">
            <td>{{ user.username }}</td>
            <td>
              <span :class="['badge', user.role === 'admin' ? 'badge-admin' : 'badge-operator']">
                {{ user.role }}
              </span>
            </td>
            <td>{{ user.is_active ? '启用' : '禁用' }}</td>
            <td>{{ formatTime(user.created_at) }}</td>
            <td>
              <button class="btn btn-small btn-primary" @click="startEdit(user)">编辑</button>
              <button
                class="btn btn-small btn-danger"
                v-if="user.is_active"
                @click="disableUser(user.id)"
                style="margin-left:6px"
              >禁用</button>
              <button
                class="btn btn-small btn-success"
                @click="generateToken(user.id)"
                style="margin-left:6px"
              >生成令牌</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else style="color:#909399">暂无用户</p>
    </div>

    <!-- 注册令牌展示 -->
    <div class="card" v-if="generatedToken">
      <h3 style="margin-bottom:8px">注册令牌</h3>
      <p style="font-size:13px;color:#909399;margin-bottom:8px">此令牌仅显示一次，24 小时内有效，一次性使用。</p>
      <div class="token-display">
        <code>{{ generatedToken.id }}</code>
        <button class="btn btn-small btn-primary" @click="copyToken">复制</button>
      </div>
      <p style="font-size:12px;color:#909399;margin-top:6px">
        过期时间: {{ formatTime(generatedToken.expires_at) }}
      </p>

      <!-- 一键部署命令 -->
      <h4 style="margin-top:16px;margin-bottom:8px">一键部署命令</h4>
      <p style="font-size:13px;color:#909399;margin-bottom:8px">复制以下命令发送给用户，在目标电脑上执行即可完成安装和注册。</p>

      <div style="margin-bottom:12px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
          <span style="font-size:13px;font-weight:600">🐳 Docker 部署（推荐）</span>
          <button class="btn btn-small btn-primary" @click="copyDeployCmd('docker')">复制</button>
        </div>
        <pre class="deploy-cmd">{{ dockerCmd }}</pre>
      </div>

      <div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
          <span style="font-size:13px;font-weight:600">🐍 pip 部署（需要 Python 3.11+）</span>
          <button class="btn btn-small btn-primary" @click="copyDeployCmd('pip')">复制</button>
        </div>
        <pre class="deploy-cmd">{{ pipCmd }}</pre>
      </div>
    </div>

    <!-- 创建/编辑弹窗 -->
    <div class="modal-overlay" v-if="showCreate || editingUser" @click.self="closeModal">
      <div class="modal card">
        <h3>{{ editingUser ? '编辑用户' : '创建用户' }}</h3>
        <form @submit.prevent="editingUser ? submitEdit() : submitCreate()">
          <div class="form-group">
            <label>用户名</label>
            <input v-model="form.username" required :disabled="!!editingUser" />
          </div>
          <div class="form-group">
            <label>密码{{ editingUser ? '（留空不修改）' : '' }}</label>
            <input v-model="form.password" type="password" :required="!editingUser" autocomplete="new-password" />
          </div>
          <div class="form-group">
            <label>角色</label>
            <select v-model="form.role">
              <option value="operator">operator</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <p v-if="formError" class="error-msg">{{ formError }}</p>
          <div style="display:flex;gap:8px;margin-top:16px">
            <button class="btn btn-primary" type="submit">{{ editingUser ? '保存' : '创建' }}</button>
            <button class="btn" type="button" @click="closeModal" style="background:#eee">取消</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import { users, tokens } from '../api.js'

export default {
  data() {
    return {
      usersList: [],
      showCreate: false,
      editingUser: null,
      form: { username: '', password: '', role: 'operator' },
      formError: '',
      generatedToken: null,
    }
  },
  computed: {
    baseUrl() {
      return window.location.origin
    },
    dockerCmd() {
      if (!this.generatedToken) return ''
      return `docker run -d --name nanobot \\\n  --restart unless-stopped \\\n  -v ~/.nanobot:/root/.nanobot \\\n  -e NANOBOT_REGISTER_TOKEN=${this.generatedToken.id} \\\n  -e NANOBOT_CONTROL_PLANE_URL=${this.baseUrl} \\\n  nanobot-ai gateway`
    },
    pipCmd() {
      if (!this.generatedToken) return ''
      return `curl -sSL "${this.baseUrl}/api/deploy/script?token_id=${this.generatedToken.id}&type=pip" | bash`
    },
  },
  methods: {
    async fetchUsers() {
      try {
        this.usersList = await users.list()
      } catch { /* ignore */ }
    },
    startEdit(user) {
      this.editingUser = user
      this.form = { username: user.username, password: '', role: user.role }
      this.formError = ''
    },
    closeModal() {
      this.showCreate = false
      this.editingUser = null
      this.form = { username: '', password: '', role: 'operator' }
      this.formError = ''
    },
    async submitCreate() {
      this.formError = ''
      try {
        await users.create(this.form)
        this.closeModal()
        this.fetchUsers()
      } catch (e) {
        this.formError = e.message
      }
    },
    async submitEdit() {
      this.formError = ''
      const data = { role: this.form.role }
      if (this.form.password) data.password = this.form.password
      try {
        await users.update(this.editingUser.id, data)
        this.closeModal()
        this.fetchUsers()
      } catch (e) {
        this.formError = e.message
      }
    },
    async disableUser(id) {
      if (!confirm('确定要禁用此用户？')) return
      try {
        await users.disable(id)
        this.fetchUsers()
      } catch (e) {
        alert('操作失败: ' + e.message)
      }
    },
    async generateToken(userId) {
      try {
        this.generatedToken = await tokens.create(userId)
      } catch (e) {
        alert('生成令牌失败: ' + e.message)
      }
    },
    copyToken() {
      navigator.clipboard.writeText(this.generatedToken.id)
    },
    copyDeployCmd(type) {
      const cmd = type === 'docker' ? this.dockerCmd : this.pipCmd
      navigator.clipboard.writeText(cmd)
    },
    formatTime(t) {
      if (!t) return '-'
      try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
    },
  },
  mounted() {
    this.fetchUsers()
  },
}
</script>

<style scoped>
.token-display {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #f5f7fa;
  padding: 10px 14px;
  border-radius: 6px;
}
.token-display code {
  font-size: 13px;
  word-break: break-all;
  flex: 1;
}
.deploy-cmd {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 12px 14px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
}
.modal {
  width: 420px;
}
.modal h3 {
  margin-bottom: 16px;
}
</style>
