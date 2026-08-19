<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import AppIcon from '../../components/AppIcon.vue'

const nav = [
  { to: '/admin/knowledge', label: '知识库管理', caption: '资料上传与索引', icon: 'document' },
  { to: '/admin/data', label: '业务数据管理', caption: '数据导入与维护', icon: 'database' },
  { to: '/admin/agent', label: '智能分析配置', caption: '模型与能力查看', icon: 'action' },
  { to: '/admin/runs', label: '分析记录', caption: '任务状态与过程', icon: 'rate' },
]
</script>

<template>
  <div class="studio-shell">
    <aside class="studio-sidebar">
      <div class="studio-sidebar-title"><strong>平台管理</strong><span>运行维护工作台</span></div>
      <nav aria-label="管理中心导航">
        <RouterLink v-for="item in nav" :key="item.to" :to="item.to">
          <span class="studio-nav-icon"><AppIcon :name="item.icon" /></span>
          <span><strong>{{ item.label }}</strong><small>{{ item.caption }}</small></span>
        </RouterLink>
      </nav>
      <div class="studio-sidebar-note">
        <AppIcon name="shield" />
        <p><strong>本地演示环境</strong><span>配置只读，数据文件在本机受控处理</span></p>
      </div>
    </aside>
    <section class="studio-main"><RouterView /></section>
  </div>
</template>
