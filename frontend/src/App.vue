<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { BUSINESS } from './config/business'
import AgentPanel from './components/AgentPanel.vue'
import AppIcon from './components/AppIcon.vue'

const route = useRoute()
const router = useRouter()
const activeNav = computed(() => String(route.name ?? 'overview'))
const isAdmin = computed(() => route.path.startsWith('/admin'))
const mobileNavOpen = ref(false)
const assistantOpen = ref(false)
const searchText = ref('')
const accessible = ref(false)

const headerNav = computed(() => isAdmin.value ? [
  { name: 'overview', label: '业务首页' },
  { name: 'admin-knowledge', label: '知识库' },
  { name: 'admin-data', label: '数据管理' },
  { name: 'admin-agent', label: '智能分析配置' },
  { name: 'admin-runs', label: '分析记录' },
] : [
  { name: 'overview', label: '首页' },
  { name: 'analysis', label: '专题分析' },
  { name: 'cases', label: '事件中心' },
])

function selectNav(key: string) {
  mobileNavOpen.value = false
  router.push({ name: key })
}

function submitSearch() {
  const keyword = searchText.value.trim()
  if (!keyword) return
  mobileNavOpen.value = false
  router.push({ name: 'cases', query: { keyword } })
}

</script>

<template>
  <div class="app-shell" :class="{ accessible, 'admin-mode': isAdmin }">
    <header v-if="!isAdmin" class="topbar gov-header">
      <div class="gov-header-main">
        <div class="topbar-inner">
        <RouterLink class="brand" to="/" aria-label="返回首页">
          <span class="brand-mark"><AppIcon name="shield" /></span>
          <span class="brand-copy">
            <strong>{{ BUSINESS.appName }}</strong>
            <small>{{ BUSINESS.organization }}</small>
          </span>
        </RouterLink>
        <form class="gov-search" role="search" @submit.prevent="submitSearch">
          <input v-model="searchText" aria-label="全站搜索" placeholder="请输入事件编号、区域或事项关键词">
          <button type="submit">搜索</button>
        </form>
        <div class="topbar-actions">
          <button class="utility-link" type="button" @click="accessible = !accessible">无障碍浏览</button>
          <span class="utility-divider" />
          <span class="utility-text">简体中文</span>
          <span class="utility-divider" />
          <button v-if="!isAdmin" class="utility-link" type="button" @click="assistantOpen = true">使用帮助</button>
          <button class="icon-button mobile-menu" aria-label="打开导航" @click="mobileNavOpen = !mobileNavOpen">
            <AppIcon name="menu" />
          </button>
        </div>
      </div>
      </div>
      <div class="gov-nav-bar">
        <div class="gov-nav-inner">
          <nav class="main-nav" aria-label="主导航">
            <button v-for="item in headerNav" :key="item.name" :class="{ active: activeNav === item.name }" @click="selectNav(item.name)">{{ item.label }}</button>
          </nav>
          <div class="nav-side">
            <RouterLink class="management-entry" :to="isAdmin ? '/' : '/admin'">{{ isAdmin ? '返回业务工作台' : '进入管理中心' }}</RouterLink>
          </div>
        </div>
        <nav v-if="mobileNavOpen" class="mobile-nav" aria-label="移动端导航">
          <button v-for="item in headerNav" :key="item.name" @click="selectNav(item.name)">{{ item.label }}</button>
          <button v-if="!isAdmin" class="mobile-management-entry" @click="selectNav('admin-knowledge')">进入管理中心</button>
          <button v-else class="mobile-management-entry" @click="selectNav('overview')">返回业务工作台</button>
        </nav>
      </div>
    </header>

    <header v-else class="admin-topbar">
      <div class="admin-topbar-inner">
        <RouterLink class="admin-brand" to="/admin" aria-label="返回管理中心首页">
          <span class="admin-brand-mark"><AppIcon name="shield" /></span>
          <span><strong>{{ BUSINESS.appName }}</strong><small>管理中心</small></span>
        </RouterLink>
        <span class="admin-environment">演示环境</span>
        <div class="admin-topbar-actions">
          <RouterLink to="/">返回业务工作台</RouterLink>
        </div>
      </div>
    </header>

    <main :class="{ 'admin-main': isAdmin }">
      <RouterView />
    </main>

    <button v-if="!isAdmin" class="agent-fab" aria-label="打开 AI智能助手" @click="assistantOpen = true">
      <AppIcon name="bot" />
      <span>AI智能助手</span>
    </button>
    <AgentPanel v-if="!isAdmin" :open="assistantOpen" @close="assistantOpen = false" />

    <footer v-if="!isAdmin" class="gov-footer">
      <div class="gov-footer-services">
        <div><span class="footer-service-icon">☎</span><p><small>政务服务热线</small><strong>12345</strong></p></div>
        <div><span class="footer-service-icon">◉</span><p><small>系统服务</small><strong>工作日 9:00–17:30</strong></p></div>
        <div><span class="footer-service-icon">◇</span><p><small>意见建议</small><strong>欢迎提出宝贵意见</strong></p></div>
        <div><span class="footer-service-icon">盾</span><p><small>数据安全保障</small><strong>本地数据受控使用</strong></p></div>
      </div>
      <div class="gov-footer-bottom"><span>主办单位：{{ BUSINESS.organization }}</span><span>数据仅用于辅助研判，具体处置以业务系统为准</span><span>系统运行区域：{{ BUSINESS.region }}</span></div>
    </footer>
  </div>
</template>
