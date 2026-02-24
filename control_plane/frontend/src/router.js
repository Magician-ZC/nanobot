import { createRouter, createWebHashHistory } from 'vue-router'
import { isLoggedIn } from './api.js'

import Login from './views/Login.vue'
import Dashboard from './views/Dashboard.vue'
import NodeDetail from './views/NodeDetail.vue'
import Users from './views/Users.vue'
import Tasks from './views/Tasks.vue'
import TokenUsage from './views/TokenUsage.vue'
import FeishuGateway from './views/FeishuGateway.vue'
import LLMKeys from './views/LLMKeys.vue'
import Skills from './views/Skills.vue'
import MCPServers from './views/MCPServers.vue'

const routes = [
  { path: '/login', component: Login, meta: { public: true } },
  { path: '/', component: Dashboard },
  { path: '/nodes/:id', component: NodeDetail },
  { path: '/users', component: Users },
  { path: '/tasks', component: Tasks },
  { path: '/token-usage', component: TokenUsage },
  { path: '/feishu-gateway', component: FeishuGateway },
  { path: '/llm-keys', component: LLMKeys },
  { path: '/skills', component: Skills },
  { path: '/mcp-servers', component: MCPServers },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  if (!to.meta.public && !isLoggedIn()) {
    return '/login'
  }
})

export default router
