import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from './components/DashboardView.vue'
import AnalysisView from './views/AnalysisView.vue'
import CasesView from './views/CasesView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: DashboardView },
    { path: '/analysis', name: 'analysis', component: AnalysisView },
    { path: '/cases', name: 'cases', component: CasesView },
    {
      path: '/admin', component: () => import('./views/admin/AdminLayout.vue'), redirect: '/admin/knowledge',
      children: [
        { path: 'knowledge', name: 'admin-knowledge', component: () => import('./views/admin/AdminKnowledgeView.vue') },
        { path: 'data', name: 'admin-data', component: () => import('./views/admin/AdminDataView.vue') },
        { path: 'agent', name: 'admin-agent', component: () => import('./views/admin/AdminAgentView.vue') },
        { path: 'runs', name: 'admin-runs', component: () => import('./views/admin/AdminRunsView.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
