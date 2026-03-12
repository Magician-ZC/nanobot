<template>
  <div v-if="!loggedIn">
    <router-view />
  </div>
  <div v-else class="app-layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="sidebar-brand-title">Nanobot</div>
        <div class="sidebar-brand-sub">Control Plane</div>
      </div>
      <nav class="sidebar-nav">
        <div class="sidebar-section">
          <div class="sidebar-section-title">概览</div>
          <router-link to="/" class="sidebar-link" exact-active-class="active">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
            仪表盘
          </router-link>
          <router-link to="/tasks" class="sidebar-link">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
            任务监控
          </router-link>
        </div>
        <div class="sidebar-section" v-if="isAdmin">
          <div class="sidebar-section-title">资源管理</div>
          <router-link to="/llm-keys" class="sidebar-link">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
            Key 管理
          </router-link>
          <router-link to="/skills" class="sidebar-link">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>
            Skill
          </router-link>
          <router-link to="/mcp-servers" class="sidebar-link">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1"/><circle cx="6" cy="18" r="1"/></svg>
            MCP Server
          </router-link>
          <router-link to="/personas" class="sidebar-link">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
            Persona
          </router-link>
        </div>
        <div class="sidebar-section" v-if="isAdmin">
          <div class="sidebar-section-title">系统</div>
          <router-link to="/users" class="sidebar-link">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
            用户管理
          </router-link>
          <router-link to="/feishu-gateway" class="sidebar-link">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>
            飞书网关
          </router-link>
        </div>
      </nav>
      <div class="sidebar-footer">
        <div class="sidebar-user">
          <div class="sidebar-avatar">{{ userInitial }}</div>
          <div class="sidebar-user-info">
            <div class="sidebar-user-name">{{ userName }}</div>
            <div class="sidebar-user-role">{{ userRole }}</div>
          </div>
          <button class="btn btn-ghost btn-small" @click="logout" title="退出登录">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          </button>
        </div>
      </div>
    </aside>
    <!-- 主内容 -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getCurrentUser, removeToken } from './api.js'

const router = useRouter()
const route = useRoute()

const loggedIn = computed(() => {
  route.path // trigger reactivity on route change
  return !!getCurrentUser()
})

const isAdmin = computed(() => {
  const u = getCurrentUser()
  return u && u.role === 'admin'
})

const userRole = computed(() => {
  const u = getCurrentUser()
  return u ? u.role : ''
})

const userName = computed(() => {
  const u = getCurrentUser()
  return u ? u.userId : ''
})

const userInitial = computed(() => {
  const name = userName.value
  return name ? name.charAt(0).toUpperCase() : '?'
})

const logout = () => {
  removeToken()
  router.push('/login')
}
</script>
