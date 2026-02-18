import { createRouter, createWebHashHistory } from 'vue-router'
import { isLoggedIn } from './api.js'

import Login from './views/Login.vue'
import Dashboard from './views/Dashboard.vue'
import NodeDetail from './views/NodeDetail.vue'
import Users from './views/Users.vue'
import Tasks from './views/Tasks.vue'
import TokenUsage from './views/TokenUsage.vue'

const routes = [
  { path: '/login', component: Login, meta: { public: true } },
  { path: '/', component: Dashboard },
  { path: '/nodes/:id', component: NodeDetail },
  { path: '/users', component: Users },
  { path: '/tasks', component: Tasks },
  { path: '/token-usage', component: TokenUsage },
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
