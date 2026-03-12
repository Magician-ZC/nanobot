<template>
  <div>
    <div class="page-header">
      <h2>Persona 管理</h2>
      <div style="display:flex;gap:8px">
        <button class="btn btn-small" @click="compressAll" :disabled="compressingAll">{{ compressingAll ? '压缩中...' : '批量压缩记忆' }}</button>
        <button class="btn btn-primary" @click="openCreate('manual')">手动创建</button>
        <button class="btn btn-success" @click="openCreate('ai')">AI 生成</button>
      </div>
    </div>

    <!-- 手动创建/编辑对话框 -->
    <div v-if="showManual || editingItem" class="modal-overlay" @click.self="closeForm">
      <div class="modal-card" style="width:580px">
        <h3>{{ editingItem ? '编辑 Persona' : '手动创建 Persona' }}</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="form.name" placeholder="如: assistant-alpha" :disabled="!!editingItem" />
        </div>
        <div class="form-group">
          <label>描述</label>
          <input v-model="form.description" placeholder="Persona 功能描述" />
        </div>
        <div class="form-group">
          <label>人格定义</label>
          <textarea v-model="form.persona_content" rows="10" placeholder="定义该 Agent 的人格、行为准则、语气风格等..."></textarea>
        </div>
        <div class="form-group">
          <label>记忆上限（字符）</label>
          <input v-model.number="form.max_memory_chars" type="number" min="1000" step="1000" />
        </div>
        <p v-if="formError" class="error-msg">{{ formError }}</p>
        <div class="form-actions">
          <button class="btn" @click="closeForm">取消</button>
          <button class="btn btn-primary" @click="submitManual" :disabled="submitting">{{ submitting ? '提交中...' : '确定' }}</button>
        </div>
      </div>
    </div>

    <!-- AI 生成对话框 -->
    <div v-if="showAI" class="modal-overlay" @click.self="closeForm">
      <div class="modal-card" style="width:620px">
        <h3>AI 生成 Persona</h3>
        <!-- 输入阶段 -->
        <template v-if="!aiPreview">
          <div class="form-group">
            <label>名称</label>
            <input v-model="aiForm.name" placeholder="如: sales-expert" />
          </div>
          <div style="display:flex;gap:12px">
            <div class="form-group" style="flex:1">
              <label>年龄</label>
              <input v-model="aiForm.age" placeholder="如: 28岁" />
            </div>
            <div class="form-group" style="flex:1">
              <label>职业</label>
              <input v-model="aiForm.profession" placeholder="如: 资深销售顾问" />
            </div>
          </div>
          <div class="form-group">
            <label>用途/职责</label>
            <textarea v-model="aiForm.purpose" rows="3" placeholder="描述这个 Agent 的主要用途和职责..."></textarea>
          </div>
          <div class="form-group">
            <label>额外性格特征（可选）</label>
            <input v-model="aiForm.traits" placeholder="如: 耐心、幽默、善于倾听" />
          </div>
          <div style="display:flex;gap:12px">
            <div class="form-group" style="flex:1">
              <label>回复语言</label>
              <input v-model="aiForm.language" placeholder="中文" />
            </div>
            <div class="form-group" style="flex:1">
              <label>记忆上限（字符）</label>
              <input v-model.number="aiForm.max_memory_chars" type="number" min="1000" step="1000" />
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
            <label>生成的人格定义（可编辑后保存）</label>
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

    <!-- 记忆查看对话框 -->
    <div v-if="viewingMemory" class="modal-overlay" @click.self="viewingMemory = null">
      <div class="modal-card" style="width:720px;max-height:85vh;overflow-y:auto">
        <h3>{{ viewingMemory.persona_name }} — 记忆详情</h3>
        <div style="display:flex;gap:8px;margin-bottom:16px">
          <button class="btn btn-small btn-primary" @click="doMerge" :disabled="merging">{{ merging ? '合并中...' : 'LLM 智能合并' }}</button>
          <button class="btn btn-small" @click="doCompress" :disabled="compressing">{{ compressing ? '压缩中...' : '压缩记忆' }}</button>
        </div>
        <p v-if="memoryActionMsg" :class="memoryActionMsg.startsWith('错误') ? 'error-msg' : 'success-msg'">{{ memoryActionMsg }}</p>

        <h4 style="margin:14px 0 8px;font-size:14px">全局记忆
          <span v-if="viewingMemory.global_memory" class="badge badge-online" style="margin-left:6px">v{{ viewingMemory.global_memory.merge_version }}</span>
        </h4>
        <pre class="memory-block">{{ viewingMemory.global_memory?.memory_content || '（空）' }}</pre>

        <h4 style="margin:18px 0 8px;font-size:14px">节点记忆（{{ viewingMemory.node_memories?.length || 0 }} 个节点）</h4>
        <div v-for="nm in (viewingMemory.node_memories || [])" :key="nm.node_id" style="margin-bottom:14px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
            <code>{{ nm.node_id.substring(0, 12) }}...</code>
            <span class="badge badge-info">v{{ nm.memory_version }}</span>
            <span style="color:var(--text-muted);font-size:12px">{{ formatTime(nm.updated_at) }}</span>
          </div>
          <pre class="memory-block">{{ nm.memory_content || '（空）' }}</pre>
        </div>
        <p v-if="!viewingMemory.node_memories?.length" style="color:var(--text-muted)">暂无节点记忆</p>
        <div class="form-actions"><button class="btn" @click="viewingMemory = null">关闭</button></div>
      </div>
    </div>

    <!-- Persona 列表 -->
    <div class="card">
      <p v-if="loading" style="color:var(--text-muted)">加载中...</p>
      <table v-else-if="list.length">
        <thead><tr><th>名称</th><th>描述</th><th>版本</th><th>记忆上限</th><th>创建时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="p in list" :key="p.id">
            <td style="font-weight:500">{{ p.name }}</td>
            <td>{{ p.description || '-' }}</td>
            <td>v{{ p.version }}</td>
            <td>{{ (p.max_memory_chars / 1000).toFixed(0) }}K</td>
            <td>{{ formatTime(p.created_at) }}</td>
            <td class="action-cell">
              <button class="btn btn-small" @click="viewMemory(p)">记忆</button>
              <button class="btn btn-small" @click="startEdit(p)">编辑</button>
              <button class="btn btn-small btn-danger" @click="removeItem(p)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">
        <div class="empty-state-icon">🤖</div>
        <div class="empty-state-text">暂无 Persona，点击右上角创建或用 AI 生成</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { personas } from '../api.js'

const list = ref([])
const loading = ref(true)

const showManual = ref(false)
const showAI = ref(false)
const editingItem = ref(null)

const form = ref({ name: '', description: '', persona_content: '', max_memory_chars: 50000 })
const aiForm = ref({ name: '', purpose: '', age: '', profession: '', traits: '', language: '中文', max_memory_chars: 50000 })
const aiPreview = ref(null)

const formError = ref('')
const submitting = ref(false)
const generating = ref(false)

const viewingMemory = ref(null)
const merging = ref(false)
const compressing = ref(false)
const compressingAll = ref(false)
const memoryActionMsg = ref('')

const fetchData = async () => {
  try {
    list.value = await personas.list()
  } catch (e) {
    console.error('Failed to fetch personas:', e)
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
  form.value = { name: '', description: '', persona_content: '', max_memory_chars: 50000 }
  aiForm.value = { name: '', purpose: '', age: '', profession: '', traits: '', language: '中文', max_memory_chars: 50000 }
  aiPreview.value = null
  formError.value = ''
}

const startEdit = (p) => {
  editingItem.value = p
  form.value = {
    name: p.name,
    description: p.description || '',
    persona_content: p.persona_content || '',
    max_memory_chars: p.max_memory_chars
  }
}

const submitManual = async () => {
  formError.value = ''
  if (!form.value.name) {
    formError.value = '请填写名称'
    return
  }
  if (!form.value.persona_content) {
    formError.value = '请填写人格定义'
    return
  }
  submitting.value = true
  try {
    if (editingItem.value) {
      await personas.update(editingItem.value.id, {
        persona_content: form.value.persona_content,
        description: form.value.description,
        max_memory_chars: form.value.max_memory_chars
      })
    } else {
      await personas.create(form.value)
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
    formError.value = '请填写用途/职责'
    return false
  }
  return true
}

const aiGenPreview = async () => {
  formError.value = ''
  if (!_validateAiForm()) return
  generating.value = true
  try {
    const r = await personas.generatePreview(aiForm.value)
    aiPreview.value = r.persona_content
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
    await personas.generate(aiForm.value)
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
    const desc = `${aiForm.value.profession || ''} | ${aiForm.value.purpose}`.trim().replace(/^\||\|$/g, '').trim()
    await personas.create({
      name: aiForm.value.name,
      persona_content: aiPreview.value,
      description: desc,
      max_memory_chars: aiForm.value.max_memory_chars
    })
    closeForm()
    await fetchData()
  } catch (e) {
    formError.value = e.message
  } finally {
    submitting.value = false
  }
}

const removeItem = async (p) => {
  if (!confirm(`确定删除 "${p.name}"？所有记忆也会被删除。`)) return
  try {
    await personas.delete(p.id)
    await fetchData()
  } catch (e) {
    alert('删除失败: ' + e.message)
  }
}

const viewMemory = async (p) => {
  memoryActionMsg.value = ''
  try {
    const data = await personas.getMemory(p.id)
    viewingMemory.value = { ...data, _id: p.id }
  } catch (e) {
    alert('获取记忆失败: ' + e.message)
  }
}

const doMerge = async () => {
  merging.value = true
  memoryActionMsg.value = ''
  try {
    const r = await personas.merge(viewingMemory.value._id)
    memoryActionMsg.value = `合并完成 (${r.method})，v${r.merge_version}，${r.chars} 字符`
    const data = await personas.getMemory(viewingMemory.value._id)
    viewingMemory.value = { ...data, _id: viewingMemory.value._id }
  } catch (e) {
    memoryActionMsg.value = '错误: ' + e.message
  } finally {
    merging.value = false
  }
}

const doCompress = async () => {
  compressing.value = true
  memoryActionMsg.value = ''
  try {
    const r = await personas.compress(viewingMemory.value._id)
    if (r.status === 'skipped') {
      memoryActionMsg.value = '跳过: ' + r.message
    } else {
      memoryActionMsg.value = `压缩: ${r.before_chars} → ${r.after_chars} 字符`
      const data = await personas.getMemory(viewingMemory.value._id)
      viewingMemory.value = { ...data, _id: viewingMemory.value._id }
    }
  } catch (e) {
    memoryActionMsg.value = '错误: ' + e.message
  } finally {
    compressing.value = false
  }
}

const compressAll = async () => {
  if (!confirm('批量压缩所有 Persona 记忆？')) return
  compressingAll.value = true
  try {
    const r = await personas.compressAll()
    alert(`完成，共压缩 ${r.compressed} 个`)
  } catch (e) {
    alert('失败: ' + e.message)
  } finally {
    compressingAll.value = false
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
.memory-block {
  background: #f9fafb; border: 1px solid var(--border); border-radius: 8px; padding: 14px;
  font-size: 13px; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto;
  font-family: 'SF Mono', 'Fira Code', monospace; line-height: 1.6;
}
</style>
