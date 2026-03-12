<template>
  <div>
    <div class="page-header">
      <h2>用户管理</h2>
      <button class="btn btn-primary" @click="showCreate = true">创建用户</button>
    </div>

    <div class="card">
      <table v-if="usersList.length">
        <thead>
          <tr><th>用户名</th><th>角色</th><th>状态</th><th>创建时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="user in usersList" :key="user.id">
            <td style="font-weight:500">{{ user.username }}</td>
            <td><span :class="['badge', user.role === 'admin' ? 'badge-admin' : 'badge-operator']">{{ user.role }}</span></td>
            <td>{{ user.is_active ? '启用' : '禁用' }}</td>
            <td>{{ formatTime(user.created_at) }}</td>
            <td class="action-cell">
              <button class="btn btn-small" @click="startEdit(user)">编辑</button>
              <button class="btn btn-small btn-danger" v-if="user.is_active" @click="disableUser(user.id)">禁用</button>
              <button class="btn btn-small btn-success" @click="generateToken(user.id)">生成令牌</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">
        <div class="empty-state-icon">👤</div>
        <div class="empty-state-text">暂无用户</div>
      </div>
    </div>

    <!-- 令牌展示 -->
    <div class="card" v-if="generatedToken">
      <h3 style="margin-bottom:10px">注册令牌</h3>
      <p style="font-size:13px;color:var(--text-muted);margin-bottom:10px">此令牌仅显示一次，24 小时内有效。</p>
      <div class="token-display">
        <code style="flex:1;font-size:13px;word-break:break-all">{{ generatedToken.id }}</code>
        <button class="btn btn-small btn-primary" @click="copyToken">复制</button>
      </div>
      <p style="font-size:12px;color:var(--text-muted);margin-top:8px">过期: {{ formatTime(generatedToken.expires_at) }}</p>

      <h4 style="margin-top:18px;margin-bottom:8px;font-size:14px">一键部署命令</h4>
      <div style="margin-bottom:14px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
          <span style="font-size:13px;font-weight:600">🐳 Docker 部署</span>
          <button class="btn btn-small" @click="copyDeployCmd('docker')">复制</button>
        </div>
        <pre class="deploy-cmd">{{ dockerCmd }}</pre>
      </div>
      <div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
          <span style="font-size:13px;font-weight:600">🐍 pip 部署</span>
          <button class="btn btn-small" @click="copyDeployCmd('pip')">复制</button>
        </div>
        <pre class="deploy-cmd">{{ pipCmd }}</pre>
      </div>
    </div>

    <!-- 创建/编辑弹窗 -->
    <div class="modal-overlay" v-if="showCreate || editingUser" @click.self="closeModal">
      <div class="modal-card" style="width:440px">
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
          <div class="form-actions">
            <button class="btn" type="button" @click="closeModal">取消</button>
            <button class="btn btn-primary" type="submit">{{ editingUser ? '保存' : '创建' }}</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { users, tokens } from '../api.js'

const usersList = ref([])
const showCreate = ref(false)
const editingUser = ref(null)
const form = ref({ username: '', password: '', role: 'operator' })
const formError = ref('')
const generatedToken = ref(null)

const baseUrl = computed(() => window.location.origin)

const dockerCmd = computed(() => {
  if (!generatedToken.value) return ''
  return `docker run -d --name nanobot \\\n  --restart unless-stopped \\\n  -v ~/.nanobot:/root/.nanobot \\\n  -e NANOBOT_REGISTER_TOKEN=${generatedToken.value.id} \\\n  -e NANOBOT_CONTROL_PLANE_URL=${baseUrl.value} \\\n  nanobot-ai gateway`
})

const pipCmd = computed(() => {
  if (!generatedToken.value) return ''
  return `curl -sSL "${baseUrl.value}/api/deploy/script?token_id=${generatedToken.value.id}&type=pip" | bash`
})

const fetchUsers = async () => {
  try {
    usersList.value = await users.list()
  } catch (e) {
    console.error('Failed to fetch users:', e)
  }
}

const startEdit = (user) => {
  editingUser.value = user
  form.value = { username: user.username, password: '', role: user.role }
  formError.value = ''
}

const closeModal = () => {
  showCreate.value = false
  editingUser.value = null
  form.value = { username: '', password: '', role: 'operator' }
  formError.value = ''
}

const submitCreate = async () => {
  formError.value = ''
  try {
    await users.create(form.value)
    closeModal()
    fetchUsers()
  } catch (e) {
    formError.value = e.message
  }
}

const submitEdit = async () => {
  formError.value = ''
  const data = { role: form.value.role }
  if (form.value.password) data.password = form.value.password
  try {
    await users.update(editingUser.value.id, data)
    closeModal()
    fetchUsers()
  } catch (e) {
    formError.value = e.message
  }
}

const disableUser = async (id) => {
  if (!confirm('确定要禁用此用户？')) return
  try {
    await users.disable(id)
    fetchUsers()
  } catch (e) {
    alert('操作失败: ' + e.message)
  }
}

const generateToken = async (userId) => {
  try {
    generatedToken.value = await tokens.create(userId)
  } catch (e) {
    alert('生成令牌失败: ' + e.message)
  }
}

const copyToken = () => {
  navigator.clipboard.writeText(generatedToken.value.id)
}

const copyDeployCmd = (type) => {
  navigator.clipboard.writeText(type === 'docker' ? dockerCmd.value : pipCmd.value)
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
  fetchUsers()
})
</script>

<style scoped>
.token-display {
  display: flex; align-items: center; gap: 12px;
  background: #f9fafb; padding: 12px 14px; border-radius: 8px; border: 1px solid var(--border);
}
.deploy-cmd {
  background: #1e1e2e; color: #cdd6f4; padding: 14px 16px;
  border-radius: 8px; font-size: 12px; line-height: 1.7;
  overflow-x: auto; white-space: pre-wrap; word-break: break-all; margin: 0;
}
</style>
