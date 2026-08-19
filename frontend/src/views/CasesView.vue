<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { getCases } from '../api'
import { BUSINESS } from '../config/business'
import type { GovernanceCase } from '../types'
import AppIcon from '../components/AppIcon.vue'

const loading = ref(true)
const error = ref('')
const cases = ref<GovernanceCase[]>([])
const filters = reactive({ district: '', category: '', status: '', priority: '' })
const districts = ['滨江区', '上城区', '拱墅区', '西湖区']
const statuses = ['待处理', '处理中', '已完成']
const priorities = ['高', '中', '低']

async function load() {
  loading.value = true
  error.value = ''
  try {
    cases.value = await getCases({ ...filters, limit: 200 })
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '事件数据加载失败'
  } finally {
    loading.value = false
  }
}

function reset() {
  Object.assign(filters, { district: '', category: '', status: '', priority: '' })
  load()
}

function statusClass(status: string) {
  return status === '已完成' ? 'success' : status === '处理中' ? 'processing' : 'pending'
}

function formatTime(value?: string) {
  return value ? value.replace('T', ' ').slice(0, 16) : '-'
}

onMounted(load)
</script>

<template>
  <div class="dashboard-page feature-page">
    <section class="page-heading feature-heading">
      <span class="page-emblem"><AppIcon name="database" /></span>
      <div class="page-title-copy">
        <h1>治理事件中心</h1>
        <p class="heading-description">统一查询治理事件，掌握受理、处置与办结状态</p>
      </div>
      <span class="result-count">当前结果 <strong>{{ cases.length }}</strong> 件</span>
    </section>

    <section class="panel filter-panel">
      <label>所属区域<select v-model="filters.district"><option value="">全部区域</option><option v-for="item in districts" :key="item">{{ item }}</option></select></label>
      <label>事件类别<select v-model="filters.category"><option value="">全部类别</option><option v-for="item in BUSINESS.categories" :key="item">{{ item }}</option></select></label>
      <label>处置状态<select v-model="filters.status"><option value="">全部状态</option><option v-for="item in statuses" :key="item">{{ item }}</option></select></label>
      <label>优先级<select v-model="filters.priority"><option value="">全部级别</option><option v-for="item in priorities" :key="item">{{ item }}</option></select></label>
      <div class="filter-actions"><button class="secondary-button" @click="reset">重置</button><button class="primary-button" @click="load">查询事件</button></div>
    </section>

    <div v-if="error" class="notice error-notice">{{ error }}</div>

    <section class="panel cases-center-panel">
      <header class="panel-header"><div><h2>事件查询结果</h2><p>数据来源：本地 SQLite Demo 数据库</p></div></header>
      <div class="table-wrap">
        <table class="cases-center-table">
          <thead><tr><th>事件编号</th><th>事件描述</th><th>类别</th><th>区域 / 街道</th><th>优先级</th><th>状态</th><th>上报时间</th><th>来源</th></tr></thead>
          <tbody>
            <tr v-for="item in cases" :key="item.id">
              <td class="case-id">{{ item.id }}</td><td class="case-title" :title="item.description">{{ item.description }}</td><td>{{ item.category }}</td>
              <td>{{ item.district }}<small class="street-name">{{ item.street }}</small></td><td><span class="priority-tag" :class="`priority-${item.priority}`">{{ item.priority }}</span></td>
              <td><span class="status-tag" :class="statusClass(item.status)">{{ item.status }}</span></td><td>{{ formatTime(item.created_at) }}</td><td>{{ item.source }}</td>
            </tr>
            <tr v-if="!cases.length"><td colspan="8" class="empty-table">{{ loading ? '正在查询事件…' : '没有符合条件的事件' }}</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
