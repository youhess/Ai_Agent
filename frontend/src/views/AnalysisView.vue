<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { computed, onMounted, ref } from 'vue'
import { getDashboardSummary } from '../api'
import type { DashboardSummary } from '../types'
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
  color: ['#315f88'],
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 18, right: 30, top: 12, bottom: 16, containLabel: true },
  xAxis: { type: 'value', splitLine: { lineStyle: { color: '#edf0f3', type: 'dashed' } } },
  yAxis: { type: 'category', inverse: true, data: summary.value.categories.map((item) => item.name), axisTick: { show: false }, axisLine: { show: false } },
  series: [{ type: 'bar', barWidth: 16, data: summary.value.categories.map((item) => item.value), label: { show: true, position: 'right', color: '#526171' } }],
}))

const topCategory = computed(() => summary.value.categories[0])
const topDistrict = computed(() => summary.value.districts?.[0])
const highRisk = computed(() => Number(summary.value.metrics.high_risk_cases ?? 0))

onMounted(load)
</script>

<template>
  <div class="dashboard-page feature-page">
    <section class="page-heading">
      <div>
        <h1>治理专题分析</h1>
        <p class="heading-description">从类别、区域和风险维度识别治理压力，并开展深度智能分析。</p>
      </div>
    </section>

    <div v-if="error" class="notice error-notice">{{ error }}</div>

    <section class="insight-grid">
      <article class="insight-card">
        <span>高频问题</span>
        <strong>{{ topCategory?.name ?? '暂无数据' }}</strong>
        <p v-if="topCategory">累计 {{ topCategory.value }} 件，建议结合时间趋势进一步下钻。</p>
      </article>
      <article class="insight-card">
        <span>治理压力区域</span>
        <strong>{{ topDistrict?.name ?? '暂无数据' }}</strong>
        <p v-if="topDistrict">累计 {{ topDistrict.value }} 件，应关注事件结构和未办结情况。</p>
      </article>
      <article class="insight-card">
        <span>未完成高风险事件</span>
        <strong>{{ highRisk }} 件</strong>
        <p>建议优先核验责任主体、处置时限和闭环记录。</p>
      </article>
    </section>

    <section class="analysis-layout">
      <article class="panel analysis-chart-panel">
        <header class="panel-header"><div><h2>类别压力排名</h2><p>按当前数据库事件量排序</p></div></header>
        <EChart v-if="summary.categories.length" :option="categoryOption" />
        <div v-else class="empty-chart">{{ loading ? '正在加载分析数据…' : '暂无类别数据' }}</div>
      </article>
      <article class="panel analysis-actions">
        <header class="panel-header"><div><h2>分析关注方向</h2><p>建议使用 AI 分析助手重点关注</p></div></header>
        <div class="analysis-task-list">
          <div><b>01</b><span><strong>区域异常分析</strong><small>对比滨江区最近 7 天与前一周期变化</small></span></div>
          <div><b>02</b><span><strong>高风险事件研判</strong><small>梳理未完成高风险事件及处置重点</small></span></div>
          <div><b>03</b><span><strong>治理规范辅助</strong><small>结合 Demo 知识库形成处置建议</small></span></div>
        </div>
      </article>
    </section>
  </div>
</template>
