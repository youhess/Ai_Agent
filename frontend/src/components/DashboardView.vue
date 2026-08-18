<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getCases, getDashboardSummary } from '../api'
import { BUSINESS, type MetricKey } from '../config/business'
import type { DashboardSummary, GovernanceCase, MetricValue } from '../types'
import AppIcon from './AppIcon.vue'
import EChart from './EChart.vue'

const loading = ref(true)
const router = useRouter()
const loadError = ref('')
const summary = ref<DashboardSummary>({ metrics: {}, trend: [], categories: [] })
const cases = ref<GovernanceCase[]>([])

const metricKeys = Object.keys(BUSINESS.metrics) as MetricKey[]
const palette = ['#174c83', '#337c6c', '#c17a28', '#8a4b50', '#5d6f86', '#77715f']

function metricValue(key: MetricKey): MetricValue {
  const value = summary.value.metrics?.[key]
  return typeof value === 'number' ? { value } : value ?? { value: 0 }
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(value)
}

function normalizeCase(item: GovernanceCase & Record<string, unknown>): GovernanceCase {
  return {
    id: item.id ?? item.caseId ?? item.case_no ?? '-',
    title: String(item.title ?? item.content ?? item.description ?? '-'),
    category: String(item.category ?? item.type ?? '-'),
    area: String(item.area ?? item.region ?? item.district ?? '-'),
    status: String(item.status ?? 'pending'),
    reportedAt: String(item.reportedAt ?? item.createdAt ?? item.created_at ?? item.report_time ?? '-'),
  }
}

async function loadData() {
  loading.value = true
  loadError.value = ''
  const results = await Promise.allSettled([getDashboardSummary(), getCases()])
  if (results[0].status === 'fulfilled') summary.value = results[0].value
  if (results[1].status === 'fulfilled') cases.value = results[1].value.map((item) => normalizeCase(item as GovernanceCase & Record<string, unknown>)).slice(0, 5)
  if (results.every((result) => result.status === 'rejected')) loadError.value = '无法连接数据服务，请确认后端已启动（默认端口 8000），然后重试。'
  loading.value = false
}

const trendOption = computed<EChartsOption>(() => ({
  color: ['#174c83', '#337c6c'],
  tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#d9e0e7', textStyle: { color: '#27384a' } },
  legend: { top: 4, right: 8, itemWidth: 18, itemHeight: 3, textStyle: { color: '#68788a' }, data: ['事件量'] },
  grid: { left: 15, right: 15, top: 48, bottom: 12, containLabel: true },
  xAxis: { type: 'category', boundaryGap: false, data: summary.value.trend.map((p) => p.date), axisLine: { lineStyle: { color: '#cfd7df' } }, axisTick: { show: false }, axisLabel: { color: '#7b8998' } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#edf0f3', type: 'dashed' } }, axisLabel: { color: '#7b8998' } },
  series: [
    { name: '事件量', type: 'line', smooth: 0.25, symbol: 'circle', symbolSize: 6, data: summary.value.trend.map((p) => p.count), lineStyle: { width: 2.5 }, itemStyle: { borderWidth: 2, borderColor: '#fff' } },
  ],
}))

const categoryOption = computed<EChartsOption>(() => ({
  color: palette,
  tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 件（{d}%）' },
  legend: { orient: 'vertical', right: 8, top: 'center', itemWidth: 9, itemHeight: 9, itemGap: 14, textStyle: { color: '#5f6f80', fontSize: 12 } },
  series: [{
    type: 'pie', radius: ['48%', '72%'], center: ['36%', '53%'], avoidLabelOverlap: true,
    itemStyle: { borderColor: '#fff', borderWidth: 3 }, label: { show: false },
    data: summary.value.categories,
  }],
  graphic: [{ type: 'text', left: '28%', top: '47%', style: { text: `${summary.value.categories.reduce((sum, item) => sum + item.value, 0)}\n事件`, textAlign: 'center', fill: '#26384a', fontSize: 13, fontWeight: 600, lineHeight: 21 } }],
}))

function statusLabel(status: string) {
  return BUSINESS.statusLabels[status.toLowerCase()] ?? status
}

function statusClass(status: string) {
  const key = status.toLowerCase()
  return ['resolved', 'closed', '已完成'].includes(key) ? 'success' : ['processing', '处理中'].includes(key) ? 'processing' : 'pending'
}

function formatBroadcastTime(value: string) {
  return value.includes('T') ? value.slice(5, 16).replace('T', ' ') : value
}

onMounted(loadData)
</script>

<template>
  <div class="dashboard-page">
    <section class="page-heading">
      <div>
        <h1>{{ BUSINESS.dashboard.title }}</h1>
        <p class="heading-description">{{ BUSINESS.dashboard.description }}</p>
      </div>
    </section>

    <div v-if="loadError" class="notice error-notice">{{ loadError }}</div>

    <section class="metrics-grid" aria-label="核心指标">
      <article v-for="(key, index) in metricKeys" :key="key" class="metric-card" :class="{ loading }">
        <div class="metric-icon" :class="`tone-${index + 1}`"><AppIcon :name="BUSINESS.metrics[key].icon" /></div>
        <div class="metric-main">
          <p>{{ BUSINESS.metrics[key].label }}</p>
          <div class="metric-value"><strong>{{ loading ? '—' : formatNumber(metricValue(key).value) }}</strong><span>{{ BUSINESS.metrics[key].unit }}</span></div>
        </div>
        <span v-if="metricValue(key).change !== undefined" class="metric-change" :class="metricValue(key).trend">
          <AppIcon name="arrow-up" /> {{ Math.abs(metricValue(key).change ?? 0) }}%
        </span>
      </article>
    </section>

    <section class="charts-grid">
      <article class="panel trend-panel">
        <header class="panel-header"><div><h2>{{ BUSINESS.dashboard.trendTitle }}</h2><p>{{ BUSINESS.dashboard.trendSubtitle }}</p></div></header>
        <EChart v-if="summary.trend.length" :option="trendOption" />
        <div v-else class="empty-chart">{{ loading ? '正在加载趋势数据…' : '暂无趋势数据' }}</div>
      </article>
      <article class="panel category-panel">
        <header class="panel-header"><div><h2>{{ BUSINESS.dashboard.categoryTitle }}</h2><p>{{ BUSINESS.dashboard.categorySubtitle }}</p></div></header>
        <EChart v-if="summary.categories.length" :option="categoryOption" />
        <div v-else class="empty-chart">{{ loading ? '正在加载分类数据…' : '暂无分类数据' }}</div>
      </article>
    </section>

    <section class="panel cases-panel">
      <header class="panel-header"><div><h2>{{ BUSINESS.dashboard.casesTitle }}</h2><p>{{ BUSINESS.dashboard.casesSubtitle }}</p></div><button class="text-button" @click="router.push('/cases')">进入事件中心 <span>›</span></button></header>
      <div v-if="cases.length" class="event-broadcast" aria-label="最新事件动态，鼠标悬停可暂停滚动">
        <div
          class="broadcast-track"
          :class="{ scrolling: cases.length > 4 }"
          :style="{ '--ticker-distance': `${-52 * cases.length}px`, '--ticker-duration': `${Math.max(cases.length * 4, 16)}s` }"
        >
          <div v-for="item in cases" :key="item.id" class="broadcast-item">
            <time>{{ formatBroadcastTime(item.reportedAt) }}</time>
            <span class="broadcast-category">{{ item.category }}</span>
            <span class="broadcast-area">{{ item.area }}</span>
            <strong :title="item.title">{{ item.title }}</strong>
            <span class="status-tag" :class="statusClass(item.status)">{{ statusLabel(item.status) }}</span>
          </div>
          <div v-for="item in cases" :key="`copy-${item.id}`" class="broadcast-item broadcast-copy" aria-hidden="true">
            <time>{{ formatBroadcastTime(item.reportedAt) }}</time>
            <span class="broadcast-category">{{ item.category }}</span>
            <span class="broadcast-area">{{ item.area }}</span>
            <strong :title="item.title">{{ item.title }}</strong>
            <span class="status-tag" :class="statusClass(item.status)">{{ statusLabel(item.status) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="broadcast-empty">{{ loading ? '正在加载事件动态…' : BUSINESS.caseTable.empty }}</div>
    </section>
    <footer class="dashboard-footer"><span>{{ BUSINESS.organization }} · {{ BUSINESS.region }}</span><span>{{ BUSINESS.footer }}</span></footer>
  </div>
</template>
