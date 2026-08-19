<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { BUSINESS } from './config/business'
import AgentPanel from './components/AgentPanel.vue'
import AppIcon from './components/AppIcon.vue'
import { getHealth } from './api'

const route = useRoute()
const router = useRouter()
const activeNav = computed(() => String(route.name ?? 'overview'))
const isAdmin = computed(() => route.path.startsWith('/admin'))
const mobileNavOpen = ref(false)
const assistantOpen = ref(false)
const serviceOnline = ref(false)
let healthTimer: number | undefined

async function checkHealth() {
  try {
    serviceOnline.value = (await getHealth()).status === 'ok'
  } catch {
    serviceOnline.value = false
  }
}

function selectNav(key: string) {
  mobileNavOpen.value = false
  router.push({ name: key })
}

onMounted(() => {
  checkHealth()
  healthTimer = window.setInterval(checkHealth, 30000)
})
onUnmounted(() => window.clearInterval(healthTimer))
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-inner">
        <RouterLink class="brand" :to="isAdmin ? '/admin' : '/'" aria-label="返回首页">
          <span class="brand-mark"><AppIcon name="landmark" /></span>
          <span class="brand-copy">
            <strong>{{ isAdmin ? 'AI Agent Studio' : BUSINESS.appName }}</strong>
            <small>{{ isAdmin ? '知识 · 数据 · 智能体运行维护' : BUSINESS.organization }}</small>
          </span>
        </RouterLink>
        <nav v-if="!isAdmin" class="main-nav" aria-label="主导航">
          <button
            v-for="(label, key) in BUSINESS.nav"
            :key="key"
            :class="{ active: activeNav === key }"
            @click="selectNav(key)"
          >{{ label }}</button>
        </nav>
        <div class="topbar-actions">
          <RouterLink class="workspace-switch" :to="isAdmin ? '/' : '/admin'">
            <AppIcon :name="isAdmin ? 'landmark' : 'bot'" />
            {{ isAdmin ? '返回业务工作台' : 'Agent Studio' }}
          </RouterLink>
          <span class="system-status" :class="{ offline: !serviceOnline }"><i />{{ serviceOnline ? '系统正常' : '服务离线' }}</span>
          <button v-if="!isAdmin" class="icon-button mobile-menu" aria-label="打开导航" @click="mobileNavOpen = !mobileNavOpen">
            <AppIcon name="menu" />
          </button>
        </div>
      </div>
      <nav v-if="mobileNavOpen && !isAdmin" class="mobile-nav" aria-label="移动端导航">
        <button v-for="(label, key) in BUSINESS.nav" :key="key" @click="selectNav(key)">{{ label }}</button>
      </nav>
    </header>

    <main>
      <RouterView />
    </main>

    <button v-if="!isAdmin" class="agent-fab" aria-label="打开 AI 分析助手" @click="assistantOpen = true">
      <AppIcon name="spark" />
      <span>AI 分析助手</span>
    </button>
    <AgentPanel v-if="!isAdmin" :open="assistantOpen" @close="assistantOpen = false" />
  </div>
</template>
