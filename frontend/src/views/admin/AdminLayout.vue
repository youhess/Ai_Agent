<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import AppIcon from '../../components/AppIcon.vue'

const nav = [
  { to: '/admin/knowledge', label: '知识库', caption: '资料与索引', icon: 'document' },
  { to: '/admin/data', label: '业务数据', caption: '导入与预检', icon: 'database' },
  { to: '/admin/agent', label: 'Agent 配置', caption: '能力只读视图', icon: 'bot' },
  { to: '/admin/runs', label: '运行记录', caption: 'Trace 与状态', icon: 'rate' },
]
</script>

<template>
  <div class="studio-shell">
    <aside class="studio-sidebar">
      <div class="studio-sidebar-title">
        <span>管理中心</span>
        <small>AI Agent Studio</small>
      </div>
      <nav aria-label="Agent Studio 导航">
        <RouterLink v-for="item in nav" :key="item.to" :to="item.to">
          <span class="studio-nav-icon"><AppIcon :name="item.icon" /></span>
          <span><strong>{{ item.label }}</strong><small>{{ item.caption }}</small></span>
        </RouterLink>
      </nav>
      <div class="studio-sidebar-note">
        <AppIcon name="shield" />
        <p><strong>比赛演示模式</strong><span>配置只读，业务数据均在本机处理</span></p>
      </div>
    </aside>
    <section class="studio-main"><RouterView /></section>
  </div>
</template>
