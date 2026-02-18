<template>
  <div class="page">
    <h2>Token 用量统计</h2>

    <!-- 汇总卡片 -->
    <div class="summary-cards">
      <div class="card">
        <div class="card-label">总 Token 用量</div>
        <div class="card-value">{{ summary.total_tokens?.toLocaleString() || 0 }}</div>
      </div>
      <div class="card">
        <div class="card-label">Prompt Tokens</div>
        <div class="card-value">{{ summary.total_prompt_tokens?.toLocaleString() || 0 }}</div>
      </div>
      <div class="card">
        <div class="card-label">Completion Tokens</div>
        <div class="card-value">{{ summary.total_completion_tokens?.toLocaleString() || 0 }}</div>
      </div>
      <div class="card">
        <div class="card-label">调用次数</div>
        <div class="card-value">{{ summary.record_count || 0 }}</div>
      </div>
    </div>

    <!-- LLM Key 管理 -->
    <div class="section">
      <h3>LLM API Key 管理</h3>
      <div class="toolbar">
        <button @click="showAddKey = true">添加 Key</button>
      </div>
      <table v-if="keys.length">
        <thead>
          <tr>
            <th>名称</th><th>提供商</th><th>Key 预览</th>
            <th>并发 (当前/上限)</th><th>用量 (已用/上限)</th>
            <th>状态</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="k in keys" :key="k.id">
            <td>{{ k.name }}</td>
            <td>{{ k.provider }}</td>
            <td><code>{{ k.api_key_preview }}</code></td>
            <td>{{ k.current_concurrent }} / {{ k.max_concurrent }}</td>
            <td>{{ k.total_usage.toLocaleString() }} / {{ k.usage_limit || '∞' }}</td>
            <td>
              <span :class="k.is_active ? 'status-on' : 'status-off'">
                {{ k.is_active ? '启用' : '禁用' }}
              </span>
            </td>
            <td>
              <button @click="toggleKey(k)">{{ k.is_active ? '禁用' : '启用' }}</button>
              <button @click="deleteKey(k.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">暂无 LLM Key</p>
    </div>

    <!-- 用量明细 -->
    <div class="section">
      <h3>用量明细</h3>
      <table v-if="records.length">
        <thead>
          <tr>
            <th>时间</th><th>节点</th><th>模型</th>
            <th>Prompt</th><th>Completion</th><th>Total</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in records" :key="r.id">
            <td>{{ formatTime(r.timestamp) }}</td>
            <td>{{ r.node_id.slice(0, 8) }}...</td>
            <td>{{ r.model }}</td>
            <td>{{ r.prompt_tokens }}</td>
            <td>{{ r.completion_tokens }}</td>
            <td>{{ r.total_tokens }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="empty">暂无用量记录</p>
    </div>

    <!-- 添加 Key 对话框 -->
    <div v-if="showAddKey" class="modal-overlay" @click.self="showAddKey = false">
      <div class="modal">
        <h3>添加 LLM API Key</h3>
        <label>名称 <input v-model="newKey.name" /></label>
        <label>提供商 <input v-model="newKey.provider" placeholder="openai" /></label>
        <label>API Key <input v-model="newKey.api_key" type="password" /></label>
        <label>并发上限 <input v-model.number="newKey.max_concurrent" type="number" /></label>
        <label>用量上限 (0=无限) <input v-model.number="newKey.usage_limit" type="number" /></label>
        <div class="modal-actions">
          <button @click="addKey">添加</button>
          <button @click="showAddKey = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { llmKeys, tokenUsage } from '../api.js'

const keys = ref([])
const records = ref([])
const summary = ref({})
const showAddKey = ref(false)
const newKey = ref({ name: '', provider: 'openai', api_key: '', max_concurrent: 5, usage_limit: 0 })

async function loadData() {
  try {
    keys.value = await llmKeys.list()
    records.value = await tokenUsage.query({ limit: 50 })
    summary.value = await tokenUsage.summary()
  } catch (e) { console.error(e) }
}

async function addKey() {
  try {
    await llmKeys.create(newKey.value)
    showAddKey.value = false
    newKey.value = { name: '', provider: 'openai', api_key: '', max_concurrent: 5, usage_limit: 0 }
    await loadData()
  } catch (e) { alert(e.message) }
}

async function toggleKey(k) {
  await llmKeys.update(k.id, { is_active: !k.is_active })
  await loadData()
}

async function deleteKey(id) {
  if (!confirm('确定删除此 Key？')) return
  await llmKeys.delete(id)
  await loadData()
}

function formatTime(ts) {
  return new Date(ts).toLocaleString()
}

onMounted(loadData)
</script>

<style scoped>
.summary-cards { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.card { background: #f8f9fa; border-radius: 8px; padding: 16px 24px; min-width: 160px; }
.card-label { font-size: 13px; color: #666; }
.card-value { font-size: 24px; font-weight: 600; margin-top: 4px; }
.section { margin-bottom: 32px; }
.toolbar { margin-bottom: 12px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }
th { background: #f5f5f5; font-weight: 600; }
code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
.status-on { color: #22c55e; }
.status-off { color: #ef4444; }
.empty { color: #999; font-style: italic; }
button { padding: 4px 12px; margin-right: 4px; cursor: pointer; border: 1px solid #ddd; border-radius: 4px; background: #fff; }
button:hover { background: #f0f0f0; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; padding: 24px; border-radius: 8px; min-width: 360px; }
.modal label { display: block; margin-bottom: 12px; }
.modal input { display: block; width: 100%; margin-top: 4px; padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; }
.modal-actions { display: flex; gap: 8px; margin-top: 16px; }
</style>
