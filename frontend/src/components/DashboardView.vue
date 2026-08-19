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
const palette = ['#0868e6', '#13a67c', '#ef8b16', '#e34b4b', '#7763d5', '#5977a5', '#1383a7', '#2fa77a']

function metricValue(key: MetricKey): MetricValue {
  const value = summary.value.metrics?.[key]
  return typeof value === 'number' ? { value } : value ?? { value: 0 }
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(value)
}

function numericMetric(key: MetricKey) {
  return metricValue(key).value
}

const peakTrend = computed(() => summary.value.trend.reduce(
  (peak, item) => item.count > peak.count ? item : peak,
  { date: '暂无', count: 0 },
))

const topCategory = computed(() => summary.value.categories[0])

const aiInsights = computed(() => [
  {
    tone: 'risk', icon: 'warning', title: '高风险关注',
    text: `当前有 ${numericMetric('high_risk_cases')} 件高风险事件，建议优先核验处置进度与责任单位。`,
  },
  {
    tone: 'trend', icon: 'trend', title: '趋势洞察',
    text: peakTrend.value.count ? `${peakTrend.value.date.slice(5)} 达到近 14 天峰值（${peakTrend.value.count} 件），建议关注当日集中上报原因。` : '当前暂无足够的趋势数据。',
  },
  {
    tone: 'action', icon: 'action', title: '建议行动',
    text: `待处理事件 ${numericMetric('pending_cases')} 件${topCategory.value ? `，可优先下钻“${topCategory.value.name}”类别` : ''}。`,
  },
])

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
  color: ['#0876ee'],
  tooltip: { trigger: 'axis', backgroundColor: '#fff', borderColor: '#cfe0f5', textStyle: { color: '#18375f' } },
  legend: { top: 4, right: 14, itemWidth: 18, itemHeight: 3, textStyle: { color: '#617793' }, data: ['事件量'] },
  grid: { left: 16, right: 18, top: 48, bottom: 15, containLabel: true },
  xAxis: { type: 'category', boundaryGap: false, data: summary.value.trend.map((p) => p.date), axisLine: { lineStyle: { color: '#cddcf0' } }, axisTick: { show: false }, axisLabel: { color: '#70839c' } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: '#dce8f6', type: 'dashed' } }, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#70839c' } },
  series: [
    { name: '事件量', type: 'line', smooth: 0.32, symbol: 'circle', symbolSize: 7, data: summary.value.trend.map((p) => p.count), lineStyle: { width: 3 }, itemStyle: { borderWidth: 2, borderColor: '#fff' }, areaStyle: { color: 'rgba(8, 118, 238, .12)' } },
  ],
}))

const categoryOption = computed<EChartsOption>(() => ({
  color: palette,
  tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 件（{d}%）' },
  legend: { orient: 'vertical', right: 10, top: 'center', itemWidth: 9, itemHeight: 9, itemGap: 12, textStyle: { color: '#566d8a', fontSize: 11 } },
  series: [{
    type: 'pie', radius: ['48%', '72%'], center: ['34%', '53%'], avoidLabelOverlap: true,
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
    <section class="page-heading overview-heading">
      <span class="page-emblem"><AppIcon name="shield" /></span>
      <div class="page-title-copy">
        <h1>{{ BUSINESS.dashboard.title }}</h1>
        <p class="heading-description">{{ BUSINESS.dashboard.tagline }}</p>
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
          较昨日 <b>{{ (metricValue(key).change ?? 0) >= 0 ? '+' : '-' }}{{ Math.abs(metricValue(key).change ?? 0) }}%</b> <AppIcon name="arrow-up" />
        </span>
      </article>
    </section>

    <section class="charts-grid">
      <article class="panel trend-panel">
        <header class="panel-header"><div><h2>{{ BUSINESS.dashboard.trendTitle }}</h2></div></header>
        <EChart v-if="summary.trend.length" :option="trendOption" />
        <div v-else class="empty-chart">{{ loading ? '正在加载趋势数据…' : '暂无趋势数据' }}</div>
      </article>
      <article class="panel ai-summary-panel">
        <header class="panel-header ai-summary-header">
          <div><h2><AppIcon name="action" />态势研判</h2></div>
          <span>辅助参考</span>
        </header>
        <div class="ai-insight-list">
          <div v-for="item in aiInsights" :key="item.title" class="ai-insight" :class="`tone-${item.tone}`">
            <span class="ai-insight-icon"><AppIcon :name="item.icon" /></span>
            <div><strong>{{ item.title }}</strong><p>{{ item.text }}</p></div>
          </div>
        </div>
      </article>
      <article class="panel category-panel">
        <header class="panel-header"><div><h2>{{ BUSINESS.dashboard.categoryTitle }}</h2></div></header>
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
          :style="{ '--ticker-distance': `${-42 * cases.length}px`, '--ticker-duration': `${Math.max(cases.length * 4, 16)}s` }"
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
  </div>
</template>
