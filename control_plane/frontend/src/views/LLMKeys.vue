<template>
  <div>
    <div class="page-header">
      <h2>LLM Key 管理</h2>
      <button class="btn btn-primary" @click="showAdd = true">添加 Key</button>
    </div>

    <!-- 添加/编辑对话框 -->
    <div v-if="showAdd || editingKey" class="modal-overlay" @click.self="closeForm">
      <div class="modal-card">
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
        </div>
        <div class="form-group" v-if="!editingKey">
          <label>API Key</label>
          <input v-model="form.api_key" type="password" placeholder="sk-..." />
        </div>
        <div class="form-group">
          <label>最大并发数</label>
          <input v-model.number="form.max_concurrent" type="number" min="1" />
        </div>
        <div class="form-group">
          <label>用量上限 (0=不限)</label>
          <input v-model.number="form.usage_limit" type="number" min="0" />
        </div>
        <div v-if="editingKey" class="form-group">
          <label>
            <input type="checkbox" v-model="form.is_active" /> 启用
          </label>
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

    <!-- Key 列表 -->
    <div class="card">
      <p v-if="loading" style="color:#909399">加载中...</p>
      <table v-else-if="keys.length">
        <thead>
          <tr>
            <th>名称</th>
            <th>Provider</th>
            <th>Key 预览</th>
            <th>并发 (当前/上限)</th>
            <th>用量 / 上限</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="k in keys" :key="k.id">
            <td>{{ k.name }}</td>
            <td>{{ k.provider }}</td>
            <td><code>{{ k.api_key_preview }}</code></td>
            <td>{{ k.current_concurrent }} / {{ k.max_concurrent }}</td>
            <td>{{ k.total_usage }} / {{ k.usage_limit || '∞' }}</td>
            <td>
              <span :class="['badge', k.is_active ? 'badge-online' : 'badge-offline']">
                {{ k.is_active ? '启用' : '禁用' }}
              </span>
            </td>
            <td class="action-cell">
              <button class="btn btn-small btn-primary" @click="startEdit(k)">编辑</button>
              <button class="btn btn-small btn-danger" @click="removeKey(k)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else style="color:#909399">暂无 LLM Key，点击右上角添加</p>
    </div>

    <!-- Token 用量统计 -->
    <div class="section">
      <h3>Token 用量统计</h3>
      <div class="summary-cards">
        <div class="summary-card">
          <div class="card-label">总 Token 用量</div>
          <div class="card-value">{{ summary.total_tokens?.toLocaleString() || 0 }}</div>
        </div>
        <div class="summary-card">
          <div class="card-label">Prompt Tokens</div>
          <div class="card-value">{{ summary.total_prompt_tokens?.toLocaleString() || 0 }}</div>
        </div>
        <div class="summary-card">
          <div class="card-label">Completion Tokens</div>
          <div class="card-value">{{ summary.total_completion_tokens?.toLocaleString() || 0 }}</div>
        </div>
        <div class="summary-card">
          <div class="card-label">调用次数</div>
          <div class="card-value">{{ summary.record_count || 0 }}</div>
        </div>
      </div>
    </div>

    <!-- 按节点用量 -->
    <div class="section">
      <h3>节点用量明细</h3>
      <table v-if="nodeUsage.length">
        <thead>
          <tr>
            <th>节点</th>
            <th>Prompt Tokens</th>
            <th>Completion Tokens</th>
            <th>Total Tokens</th>
            <th>调用次数</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="n in nodeUsage" :key="n.node_id">
            <td>{{ n.hostname }}</td>
            <td>{{ n.prompt_tokens.toLocaleString() }}</td>
            <td>{{ n.completion_tokens.toLocaleString() }}</td>
            <td>{{ n.total_tokens.toLocaleString() }}</td>
            <td>{{ n.record_count }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else style="color:#909399">暂无用量记录</p>
    </div>

    <!-- 最近调用记录 -->
    <div class="section">
      <h3>最近调用记录</h3>
      <table v-if="records.length">
        <thead>
          <tr>
            <th>时间</th>
            <th>节点</th>
            <th>模型</th>
            <th>Prompt</th>
            <th>Completion</th>
            <th>Total</th>
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
      <p v-else style="color:#909399">暂无调用记录</p>
    </div>
  </div>
</template>

<script>
import { llmKeys, tokenUsage } from '../api.js'

const PROVIDERS = [
  'openai', 'anthropic', 'deepseek', 'openrouter', 'groq',
  'zhipu', 'dashscope', 'gemini', 'moonshot', 'minimax',
  'aihubmix', 'siliconflow', 'volcengine', 'vllm', 'custom',
]

export default {
  data() {
    return {
      keys: [],
      loading: true,
      providers: PROVIDERS,
      showAdd: false,
      editingKey: null,
      form: this.emptyForm(),
      formError: '',
      submitting: false,
      summary: {},
      nodeUsage: [],
      records: [],
    }
  },
  methods: {
    emptyForm() {
      return { name: '', provider: '', api_key: '', max_concurrent: 5, usage_limit: 0, is_active: true }
    },
    async fetchData() {
      try {
        this.keys = await llmKeys.list()
        this.summary = await tokenUsage.summary()
        this.nodeUsage = await tokenUsage.byNode()
        this.records = await tokenUsage.query({ limit: 50 })
      } catch { /* keep last data */ }
      finally { this.loading = false }
    },
    closeForm() {
      this.showAdd = false
      this.editingKey = null
      this.form = this.emptyForm()
      this.formError = ''
    },
    startEdit(k) {
      this.editingKey = k
      this.form = {
        name: k.name,
        provider: k.provider,
        api_key: '',
        max_concurrent: k.max_concurrent,
        usage_limit: k.usage_limit,
        is_active: k.is_active,
      }
    },
    async submitForm() {
      this.formError = ''
      if (!this.editingKey && (!this.form.name || !this.form.provider || !this.form.api_key)) {
        this.formError = '请填写名称、Provider 和 API Key'
        return
      }
      this.submitting = true
      try {
        if (this.editingKey) {
          await llmKeys.update(this.editingKey.id, {
            name: this.form.name,
            max_concurrent: this.form.max_concurrent,
            usage_limit: this.form.usage_limit,
            is_active: this.form.is_active,
          })
        } else {
          await llmKeys.create(this.form)
        }
        this.closeForm()
        await this.fetchData()
      } catch (e) {
        this.formError = e.message
      } finally {
        this.submitting = false
      }
    },
    async removeKey(k) {
      if (!confirm(`确定删除 Key "${k.name}"？`)) return
      try {
        await llmKeys.delete(k.id)
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
  background: #fff; border-radius: 8px; padding: 24px; width: 460px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.modal-card h3 { margin-bottom: 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 13px; color: #606266; margin-bottom: 4px; }
.form-group input, .form-group select {
  width: 100%; padding: 8px 10px; border: 1px solid #dcdfe6; border-radius: 4px; font-size: 14px; box-sizing: border-box;
}
.form-actions { display: flex; gap: 8px; margin-top: 16px; }
.action-cell { display: flex; gap: 6px; }
code { font-size: 12px; background: #f4f4f5; padding: 2px 6px; border-radius: 3px; }
.section { margin-top: 32px; }
.section h3 { margin-bottom: 12px; font-size: 16px; }
.summary-cards { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.summary-card { background: #f8f9fa; border-radius: 8px; padding: 16px 24px; min-width: 160px; }
.card-label { font-size: 13px; color: #666; }
.card-value { font-size: 24px; font-weight: 600; margin-top: 4px; }
</style>
