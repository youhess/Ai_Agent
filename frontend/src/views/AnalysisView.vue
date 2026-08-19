<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { computed, onMounted, ref } from 'vue'
import { getDashboardSummary } from '../api'
import type { DashboardSummary } from '../types'
import AppIcon from '../components/AppIcon.vue'
import EChart from '../components/EChart.vue'

const loading = ref(true)
const error = ref('')
const summary = ref<DashboardSummary>({ metrics: {}, trend: [], categories: [], districts: [] })

async function load() {
  loading.value = true
  error.value = ''
  try {
    summary.value = await getDashboardSummary()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '专题数据加载失败'
  } finally {
    loading.value = false
  }
}

const categoryOption = computed<EChartsOption>(() => ({
  color: ['#0876ee'],
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 18, right: 38, top: 12, bottom: 16, containLabel: true },
  xAxis: { type: 'value', splitLine: { lineStyle: { color: '#dce8f6', type: 'dashed' } }, axisLabel: { color: '#70839c' } },
  yAxis: { type: 'category', inverse: true, data: summary.value.categories.map((item) => item.name), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: '#536b89' } },
  series: [{ type: 'bar', barWidth: 14, data: summary.value.categories.map((item) => item.value), itemStyle: { borderRadius: [0, 7, 7, 0] }, label: { show: true, position: 'right', color: '#526b88' } }],
}))

const districtOption = computed<EChartsOption>(() => ({
  color: ['#13a67c'],
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 18, right: 38, top: 12, bottom: 16, containLabel: true },
  xAxis: { type: 'value', splitLine: { lineStyle: { color: '#dce8f6', type: 'dashed' } }, axisLabel: { color: '#70839c' } },
  yAxis: { type: 'category', inverse: true, data: (summary.value.districts ?? []).map((item) => item.name), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: '#536b89' } },
  series: [{ type: 'bar', barWidth: 18, data: (summary.value.districts ?? []).map((item) => item.value), itemStyle: { borderRadius: [0, 9, 9, 0] }, label: { show: true, position: 'right', color: '#526b88' } }],
}))

const topCategory = computed(() => summary.value.categories[0])
const topDistrict = computed(() => summary.value.districts?.[0])
const highRisk = computed(() => Number(summary.value.metrics.high_risk_cases ?? 0))

onMounted(load)
</script>

<template>
  <div class="dashboard-page feature-page">
    <section class="page-heading feature-heading">
      <span class="page-emblem"><AppIcon name="trend" /></span>
      <div class="page-title-copy">
        <h1>治理专题分析</h1>
        <p class="heading-description">聚焦事件结构与区域压力，辅助识别重点治理问题</p>
      </div>
    </section>

    <div v-if="error" class="notice error-notice">{{ error }}</div>

    <section class="insight-grid">
      <article class="insight-card">
        <span>高频问题</span>
        <strong>{{ topCategory?.name ?? '暂无数据' }}</strong>
        <small v-if="topCategory">累计 {{ topCategory.value }} 件</small>
      </article>
      <article class="insight-card">
        <span>治理压力区域</span>
        <strong>{{ topDistrict?.name ?? '暂无数据' }}</strong>
        <small v-if="topDistrict">累计 {{ topDistrict.value }} 件</small>
      </article>
      <article class="insight-card">
        <span>未完成高风险事件</span>
        <strong>{{ highRisk }} 件</strong>
        <small>建议优先跟进</small>
      </article>
    </section>

    <section class="analysis-layout">
      <article class="panel analysis-chart-panel">
        <header class="panel-header"><div><h2>类别压力排名</h2></div></header>
        <EChart v-if="summary.categories.length" :option="categoryOption" />
        <div v-else class="empty-chart">{{ loading ? '正在加载分析数据…' : '暂无类别数据' }}</div>
      </article>
      <article class="panel analysis-chart-panel">
        <header class="panel-header"><div><h2>区域治理压力</h2></div></header>
        <EChart v-if="summary.districts?.length" :option="districtOption" />
        <div v-else class="empty-chart">{{ loading ? '正在加载分析数据…' : '暂无区域数据' }}</div>
      </article>
    </section>
  </div>
</template>
