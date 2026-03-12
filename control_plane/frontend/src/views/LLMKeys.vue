<template>
  <div>
    <div class="page-header">
      <h2>LLM Key 管理</h2>
      <button class="btn btn-primary" @click="showAdd = true">添加 Key</button>
    </div>

    <!-- 添加/编辑对话框 -->
    <div v-if="showAdd || editingKey" class="modal-overlay" @click.self="closeForm">
      <div class="modal-card" style="width:480px">
        <h3>{{ editingKey ? '编辑 Key' : '添加 LLM Key' }}</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="form.name" placeholder="如: openai-key-1" />
        </div>
        <div class="form-group" v-if="!editingKey">
          <label>Provider</label>
          <select v-model="form.provider">
            <option value="">请选择</option>
            <option v-for="p in providers" :key="p" :value="p">{{ p }}</option>
          </select>
          <small style="color:var(--text-muted);display:block;margin-top:4px">使用小写 provider 名称</small>
        </div>
        <div class="form-group" v-if="!editingKey">
          <label>API Key</label>
          <input v-model="form.api_key" type="password" placeholder="sk-..." />
        </div>
        <div class="form-group">
          <label>API Base (可选)</label>
          <input v-model="form.api_base" placeholder="https://api.example.com/v1" />
        </div>
        <div style="display:flex;gap:12px">
          <div class="form-group" style="flex:1">
            <label>最大并发</label>
            <input v-model.number="form.max_concurrent" type="number" min="1" />
          </div>
          <div class="form-group" style="flex:1">
            <label>用量上限 (0=不限)</label>
            <input v-model.number="form.usage_limit" type="number" min="0" />
          </div>
        </div>
        <div v-if="editingKey" class="form-group">
          <label><input type="checkbox" v-model="form.is_active" style="width:auto;margin-right:6px" />启用</label>
        </div>
        <p v-if="formError" class="error-msg">{{ formError }}</p>
        <div class="form-actions">
          <button class="btn" @click="closeForm">取消</button>
          <button class="btn btn-primary" @click="submitForm" :disabled="submitting">{{ submitting ? '提交中...' : '确定' }}</button>
        </div>
      </div>
    </div>

    <!-- Key 列表 -->
    <div class="card">
      <p v-if="loading" style="color:var(--text-muted)">加载中...</p>
      <table v-else-if="keys.length">
        <thead>
          <tr><th>名称</th><th>Provider</th><th>Key</th><th>API Base</th><th>并发</th><th>用量</th><th>状态</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="k in keys" :key="k.id">
            <td style="font-weight:500">{{ k.name }}</td>
            <td>{{ k.provider }}</td>
            <td><code>{{ k.api_key_preview }}</code></td>
            <td><code v-if="k.api_base" style="font-size:11px">{{ k.api_base }}</code><span v-else style="color:var(--text-muted)">-</span></td>
            <td>{{ k.current_concurrent }}/{{ k.max_concurrent }}</td>
            <td>{{ k.total_usage }}/{{ k.usage_limit || '∞' }}</td>
            <td><span :class="['badge', k.is_active ? 'badge-online' : 'badge-offline']">{{ k.is_active ? '启用' : '禁用' }}</span></td>
            <td class="action-cell">
              <button class="btn btn-small" @click="startEdit(k)">编辑</button>
              <button class="btn btn-small btn-danger" @click="removeKey(k)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty-state">
        <div class="empty-state-icon">🔑</div>
        <div class="empty-state-text">暂无 LLM Key</div>
      </div>
    </div>

    <!-- Token 用量统计 -->
    <div class="stats-row" style="margin-top:8px">
      <div class="stat-card card">
        <div class="stat-value" style="font-size:22px">{{ summary.total_tokens?.toLocaleString() || 0 }}</div>
        <div class="stat-label">总 Token</div>
      </div>
      <div class="stat-card card">
        <div class="stat-value" style="font-size:22px">{{ summary.total_prompt_tokens?.toLocaleString() || 0 }}</div>
        <div class="stat-label">Prompt</div>
      </div>
      <div class="stat-card card">
        <div class="stat-value" style="font-size:22px">{{ summary.total_completion_tokens?.toLocaleString() || 0 }}</div>
        <div class="stat-label">Completion</div>
      </div>
      <div class="stat-card card">
        <div class="stat-value" style="font-size:22px">{{ summary.record_count || 0 }}</div>
        <div class="stat-label">调用次数</div>
      </div>
    </div>

    <!-- 节点用量 -->
    <div class="card" v-if="nodeUsage.length">
      <h3 style="margin-bottom:14px">节点用量明细</h3>
      <table>
        <thead><tr><th>节点</th><th>Prompt</th><th>Completion</th><th>Total</th><th>次数</th></tr></thead>
        <tbody>
          <tr v-for="n in nodeUsage" :key="n.node_id">
            <td style="font-weight:500">{{ n.hostname }}</td>
            <td>{{ n.prompt_tokens.toLocaleString() }}</td>
            <td>{{ n.completion_tokens.toLocaleString() }}</td>
            <td>{{ n.total_tokens.toLocaleString() }}</td>
            <td>{{ n.record_count }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 最近调用 -->
    <div class="card" v-if="records.length">
      <h3 style="margin-bottom:14px">最近调用记录</h3>
      <table>
        <thead><tr><th>时间</th><th>节点</th><th>模型</th><th>Prompt</th><th>Completion</th><th>Total</th></tr></thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td>{{ formatTime(r.timestamp) }}</td>
            <td><code>{{ r.node_id.slice(0, 8) }}</code></td>
            <td>{{ r.model }}</td>
            <td>{{ r.prompt_tokens }}</td>
            <td>{{ r.completion_tokens }}</td>
            <td>{{ r.total_tokens }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { llmKeys, tokenUsage } from '../api.js'

const PROVIDERS = [
  'openai', 'anthropic', 'deepseek', 'openrouter', 'groq',
  'zhipu', 'dashscope', 'gemini', 'moonshot', 'minimax',
  'aihubmix', 'siliconflow', 'volcengine', 'vllm', 'custom',
  'azure_openai',
]

const emptyForm = () => ({
  name: '', provider: '', api_key: '', api_base: '',
  max_concurrent: 5, usage_limit: 0, is_active: true
})

const keys = ref([])
const loading = ref(true)
const providers = ref(PROVIDERS)
const showAdd = ref(false)
const editingKey = ref(null)

const form = ref(emptyForm())
const formError = ref('')
const submitting = ref(false)

const summary = ref({})
const nodeUsage = ref([])
const records = ref([])

const fetchData = async () => {
  try {
    keys.value = await llmKeys.list()
    summary.value = await tokenUsage.summary()
    nodeUsage.value = await tokenUsage.byNode()
    records.value = await tokenUsage.query({ limit: 50 })
  } catch (e) {
    console.error('Failed to fetch LLM keys data:', e)
  } finally {
    loading.value = false
  }
}

const closeForm = () => {
  showAdd.value = false
  editingKey.value = null
  form.value = emptyForm()
  formError.value = ''
}

const startEdit = (k) => {
  editingKey.value = k
  form.value = {
    name: k.name,
    provider: k.provider,
    api_key: '',
    api_base: k.api_base || '',
    max_concurrent: k.max_concurrent,
    usage_limit: k.usage_limit,
    is_active: k.is_active
  }
}

const submitForm = async () => {
  formError.value = ''
  if (!editingKey.value && (!form.value.name || !form.value.provider || !form.value.api_key)) {
    formError.value = '请填写名称、Provider 和 API Key'
    return
  }
  submitting.value = true
  try {
    if (editingKey.value) {
      await llmKeys.update(editingKey.value.id, {
        name: form.value.name,
        max_concurrent: form.value.max_concurrent,
        usage_limit: form.value.usage_limit,
        is_active: form.value.is_active
      })
    } else {
      await llmKeys.create({
        name: form.value.name,
        provider: form.value.provider,
        api_key: form.value.api_key,
        api_base: form.value.api_base,
        max_concurrent: form.value.max_concurrent,
        usage_limit: form.value.usage_limit
      })
    }
    closeForm()
    await fetchData()
  } catch (e) {
    formError.value = e.message
  } finally {
    submitting.value = false
  }
}

const removeKey = async (k) => {
  if (!confirm(`确定删除 Key "${k.name}"？`)) return
  try {
    await llmKeys.delete(k.id)
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
