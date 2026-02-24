<template>
  <div>
    <div class="page-header">
      <h2>Skill 注册表</h2>
      <button class="btn btn-primary" @click="showAdd = true">注册 Skill</button>
    </div>

    <!-- 添加/编辑对话框 -->
    <div v-if="showAdd || editingSkill" class="modal-overlay" @click.self="closeForm">
      <div class="modal-card">
        <h3>{{ editingSkill ? '编辑 Skill' : '注册新 Skill' }}</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="form.name" placeholder="如: browser" />
        </div>
        <div class="form-group">
          <label>描述</label>
          <input v-model="form.description" placeholder="Skill 功能描述" />
        </div>
        <div class="form-group">
          <label>来源</label>
          <select v-model="form.source">
            <option value="builtin">builtin</option>
            <option value="workspace">workspace</option>
            <option value="custom">custom</option>
          </select>
        </div>
        <p v-if="formError" class="error-msg">{{ formError }}</p>
        <div class="form-actions">
          <button class="btn btn-primary" @click="submitForm" :disabled="submitting">
            {{ submitting ? '提交中...' : '确定' }}
          </button>
          <button class="btn" @click="closeForm">取消</button>
        </div>
      </div>
    </div>

    <!-- Skill 列表 -->
    <div class="card">
      <p v-if="loading" style="color:#909399">加载中...</p>
      <table v-else-if="skillsList.length">
        <thead>
          <tr>
            <th>名称</th>
            <th>描述</th>
            <th>来源</th>
            <th>版本</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in skillsList" :key="s.id">
            <td>{{ s.name }}</td>
            <td>{{ s.description || '-' }}</td>
            <td><span class="badge badge-source">{{ s.source }}</span></td>
            <td>v{{ s.version }}</td>
            <td>{{ formatTime(s.created_at) }}</td>
            <td class="action-cell">
              <button class="btn btn-small btn-primary" @click="startEdit(s)">编辑</button>
              <button class="btn btn-small btn-danger" @click="removeSkill(s)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else style="color:#909399">暂无 Skill，点击右上角注册</p>
    </div>
  </div>
</template>

<script>
import { skills } from '../api.js'

export default {
  data() {
    return {
      skillsList: [],
      loading: true,
      showAdd: false,
      editingSkill: null,
      form: { name: '', description: '', source: 'custom' },
      formError: '',
      submitting: false,
    }
  },
  methods: {
    async fetchData() {
      try { this.skillsList = await skills.list() }
      catch { /* keep last */ }
      finally { this.loading = false }
    },
    closeForm() {
      this.showAdd = false
      this.editingSkill = null
      this.form = { name: '', description: '', source: 'custom' }
      this.formError = ''
    },
    startEdit(s) {
      this.editingSkill = s
      this.form = { name: s.name, description: s.description || '', source: s.source }
    },
    async submitForm() {
      this.formError = ''
      if (!this.form.name) { this.formError = '请填写 Skill 名称'; return }
      this.submitting = true
      try {
        if (this.editingSkill) {
          await skills.update(this.editingSkill.id, this.form)
        } else {
          await skills.create(this.form)
        }
        this.closeForm()
        await this.fetchData()
      } catch (e) {
        this.formError = e.message
      } finally { this.submitting = false }
    },
    async removeSkill(s) {
      if (!confirm(`确定删除 Skill "${s.name}"？`)) return
      try {
        await skills.delete(s.id)
        await this.fetchData()
      } catch (e) {
        alert('删除失败: ' + e.message)
      }
    },
    formatTime(t) {
      if (!t) return '-'
      try { return new Date(t).toLocaleString('zh-CN') } catch { return t }
    },
  },
  mounted() { this.fetchData() },
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal-card {
  background: #fff; border-radius: 8px; padding: 24px; width: 420px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.modal-card h3 { margin-bottom: 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 13px; color: #606266; margin-bottom: 4px; }
.form-group input, .form-group select {
  width: 100%; padding: 8px 10px; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 14px; box-sizing: border-box;
}
.form-actions { display: flex; gap: 8px; margin-top: 16px; }
.action-cell { display: flex; gap: 6px; }
.badge-source { background: #e6f7ff; color: #1890ff; padding: 2px 8px; border-radius: 3px; font-size: 12px; }
</style>
