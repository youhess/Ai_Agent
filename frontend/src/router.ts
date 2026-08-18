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
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
