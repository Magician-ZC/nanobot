<template>
  <div>
    <div class="page-header">
      <h2>Skill 注册表</h2>
      <div style="display:flex;gap:8px">
        <button class="btn btn-primary" @click="openCreate('manual')">手动创建</button>
        <button class="btn btn-success" @click="openCreate('ai')">AI 生成</button>
      </div>
    </div>

    <!-- 手动创建/编辑对话框 -->
    <div v-if="showManual || editingItem" class="modal-overlay" @click.self="closeForm">
      <div class="modal-card" style="width:580px">
        <h3>{{ editingItem ? '编辑 Skill' : '手动创建 Skill' }}</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="form.name" placeholder="如: browser" :disabled="!!editingItem" />
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
        <div class="form-group">
          <label>Skill 内容（SKILL.md）</label>
          <textarea v-model="form.content" rows="12" placeholder="定义该 Skill 的执行步骤、质量标准等..."></textarea>
        </div>
        <p v-if="formError" class="error-msg">{{ formError }}</p>
        <div class="form-actions">
          <button class="btn" @click="closeForm">取消</button>
          <button class="btn btn-primary" @click="submitManual" :disabled="submitting">
            {{ submitting ? '提交中...' : '确定' }}
          </button>
        </div>
      </div>
    </div>

    <!-- AI 生成对话框 -->
    <div v-if="showAI" class="modal-overlay" @click.self="closeForm">
      <div class="modal-card" style="width:620px">
        <h3>AI 生成 Skill</h3>
        <!-- 输入阶段 -->
        <template v-if="!aiPreview">
          <div class="form-group">
            <label>名称</label>
            <input v-model="aiForm.name" placeholder="如: article-writer" />
          </div>
          <div class="form-group">
            <label>用途/目标</label>
            <textarea v-model="aiForm.purpose" rows="3" placeholder="描述这个 Skill 要完成什么任务..."></textarea>
          </div>
          <div class="form-group">
            <label>补充描述（可选）</label>
            <input v-model="aiForm.description" placeholder="额外的需求说明" />
          </div>
          <div style="display:flex;gap:12px">
            <div class="form-group" style="flex:1">
              <label>可用工具提示（可选）</label>
              <input v-model="aiForm.tools_hint" placeholder="如: web_search, filesystem" />
            </div>
            <div class="form-group" style="flex:1">
              <label>输出语言</label>
              <input v-model="aiForm.language" placeholder="中文" />
            </div>
          </div>
          <p v-if="formError" class="error-msg">{{ formError }}</p>
          <div class="form-actions">
            <button class="btn" @click="closeForm">取消</button>
            <button class="btn btn-primary" @click="aiGenPreview" :disabled="generating">{{ generating ? '生成中...' : '预览生成' }}</button>
            <button class="btn btn-success" @click="aiGenDirect" :disabled="generating">{{ generating ? '生成中...' : '直接创建' }}</button>
          </div>
        </template>

        <!-- 预览阶段 -->
        <template v-else>
          <div class="form-group">
            <label>生成的 Skill 定义（可编辑后保存）</label>
            <textarea v-model="aiPreview" rows="16"></textarea>
          </div>
          <p v-if="formError" class="error-msg">{{ formError }}</p>
          <div class="form-actions">
            <button class="btn" @click="aiPreview = null">返回修改</button>
            <button class="btn btn-primary" @click="aiSavePreview" :disabled="submitting">{{ submitting ? '保存中...' : '保存创建' }}</button>
          </div>
        </template>
      </div>
    </div>

    <!-- 内容查看对话框 -->
    <div v-if="viewingContent" class="modal-overlay" @click.self="viewingContent = null">
      <div class="modal-card" style="width:700px;max-height:85vh;overflow-y:auto">
        <h3>{{ viewingContent.name }} — Skill 内容</h3>
        <pre class="content-block">{{ viewingContent.content || '（空）' }}</pre>
        <div class="form-actions"><button class="btn" @click="viewingContent = null">关闭</button></div>
      </div>
    </div>

    <!-- Skill 列表 -->
    <div class="card">
      <p v-if="loading" style="color:var(--text-muted)">加载中...</p>
      <table v-else-if="skillsList.length">
        <thead>
          <tr><th>名称</th><th>描述</th><th>来源</th><th>版本</th><th>创建时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="s in skillsList" :key="s.id">
            <td style="font-weight:500">{{ s.name }}</td>
            <td>{{ s.description || '-' }}</td>
            <td><span class="badge badge-info">{{ s.source }}</span></td>
            <td>v{{ s.version }}</td>
            <td>{{ formatTime(s.created_at) }}</td>
            <td class="action-cell">
              <button v-if="s.content" class="btn btn-small" @click="viewingContent = s">查看</button>
              <button class="btn btn-small" @click="startEdit(s)">编辑</button>
              <button class="btn btn-small btn-danger" @click="removeSkill(s)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">
        <div class="empty-state-icon">🧩</div>
        <div class="empty-state-text">暂无 Skill，点击右上角创建或用 AI 生成</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { skills } from '../api.js'

const skillsList = ref([])
const loading = ref(true)

const showManual = ref(false)
const showAI = ref(false)
const editingItem = ref(null)

const form = ref({ name: '', description: '', source: 'custom', content: '' })
const aiForm = ref({ name: '', purpose: '', description: '', tools_hint: '', language: '中文' })

const aiPreview = ref(null)
const viewingContent = ref(null)

const formError = ref('')
const submitting = ref(false)
const generating = ref(false)

const fetchData = async () => {
  try {
    skillsList.value = await skills.list()
  } catch (e) {
    console.error('Failed to fetch skills:', e)
  } finally {
    loading.value = false
  }
}

const openCreate = (mode) => {
  closeForm()
  if (mode === 'ai') showAI.value = true
  else showManual.value = true
}

const closeForm = () => {
  showManual.value = false
  showAI.value = false
  editingItem.value = null
  form.value = { name: '', description: '', source: 'custom', content: '' }
  aiForm.value = { name: '', purpose: '', description: '', tools_hint: '', language: '中文' }
  aiPreview.value = null
  formError.value = ''
}

const startEdit = (s) => {
  editingItem.value = s
  form.value = { name: s.name, description: s.description || '', source: s.source, content: s.content || '' }
}

const submitManual = async () => {
  formError.value = ''
  if (!form.value.name) {
    formError.value = '请填写名称'
    return
  }
  submitting.value = true
  try {
    if (editingItem.value) {
      await skills.update(editingItem.value.id, {
        name: form.value.name,
        description: form.value.description,
        source: form.value.source,
        content: form.value.content,
      })
    } else {
      await skills.create(form.value)
    }
    closeForm()
    await fetchData()
  } catch (e) {
    formError.value = e.message
  } finally {
    submitting.value = false
  }
}

const _validateAiForm = () => {
  if (!aiForm.value.name) {
    formError.value = '请填写名称'
    return false
  }
  if (!aiForm.value.purpose) {
    formError.value = '请填写用途/目标'
    return false
  }
  return true
}

const aiGenPreview = async () => {
  formError.value = ''
  if (!_validateAiForm()) return
  generating.value = true
  try {
    const r = await skills.generatePreview(aiForm.value)
    aiPreview.value = r.content
  } catch (e) {
    formError.value = e.message
  } finally {
    generating.value = false
  }
}

const aiGenDirect = async () => {
  formError.value = ''
  if (!_validateAiForm()) return
  generating.value = true
  try {
    await skills.generate(aiForm.value)
    closeForm()
    await fetchData()
  } catch (e) {
    formError.value = e.message
  } finally {
    generating.value = false
  }
}

const aiSavePreview = async () => {
  formError.value = ''
  submitting.value = true
  try {
    const desc = aiForm.value.description || aiForm.value.purpose.substring(0, 100)
    await skills.create({
      name: aiForm.value.name,
      description: desc,
      source: 'custom',
      content: aiPreview.value
    })
    closeForm()
    await fetchData()
  } catch (e) {
    formError.value = e.message
  } finally {
    submitting.value = false
  }
}

const removeSkill = async (s) => {
  if (!confirm(`确定删除 Skill "${s.name}"？`)) return
  try {
    await skills.delete(s.id)
    await fetchData()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
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
  fetchData()
})
</script>

<style scoped>
.content-block {
  background: #f9fafb; border: 1px solid var(--border); border-radius: 8px; padding: 14px;
  font-size: 13px; white-space: pre-wrap; word-break: break-all; max-height: 500px; overflow-y: auto;
  font-family: 'SF Mono', 'Fira Code', monospace; line-height: 1.6;
}
</style>
