<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { executeCaseWorkflow, getCaseCollaborationRecommendation, getCaseDetail, getCases } from '../api'
import { BUSINESS } from '../config/business'
import type { CollaborationRecommendation, GovernanceCase, WorkflowAction } from '../types'
import AppIcon from '../components/AppIcon.vue'

const loading = ref(true)
const route = useRoute()
const error = ref('')
const cases = ref<GovernanceCase[]>([])
const selectedCase = ref<GovernanceCase | null>(null)
const recommendation = ref<CollaborationRecommendation | null>(null)
const detailLoading = ref(false)
const workflowBusy = ref(false)
const workflowMessage = ref('')
const filters = reactive({ keyword: '', district: '', category: '', status: '', priority: '' })
const workflow = reactive({ responsibleUnit: '', collaborators: [] as string[], evidenceComplete: false, note: '' })
const districts = ['滨江区', '上城区', '拱墅区', '西湖区']
const statuses = ['待处理', '处理中', '已完成']
const priorities = ['高', '中', '低']
const governanceUnits = [
  '市容管理模拟组', '环卫处置模拟组', '道路养护模拟组', '综合协调模拟组',
  '交通协调模拟组', '设施维护模拟组', '社区服务模拟组', '社区网格模拟组', '物业协同模拟组',
]
const workflowCounts = computed(() => ({
  pending: cases.value.filter((item) => item.status === '待处理').length,
  processing: cases.value.filter((item) => item.status === '处理中').length,
  review: cases.value.filter((item) => item.status === '处理中' && item.evidence_complete).length,
}))

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
  Object.assign(filters, { keyword: '', district: '', category: '', status: '', priority: '' })
  load()
}

function statusClass(status: string) {
  return status === '已完成' ? 'success' : status === '处理中' ? 'processing' : 'pending'
}

function formatTime(value?: string) {
  return value ? value.replace('T', ' ').slice(0, 16) : '-'
}

function hydrateWorkflow(item: GovernanceCase) {
  workflow.responsibleUnit = item.responsible_unit && item.responsible_unit !== '待分派单位' ? item.responsible_unit : ''
  workflow.collaborators = [...(item.collaborator_units ?? [])]
  workflow.evidenceComplete = Boolean(item.evidence_complete)
  workflow.note = ''
}

async function openCase(item: GovernanceCase) {
  detailLoading.value = true
  workflowMessage.value = ''
  selectedCase.value = item
  try {
    const [detail, collaboration] = await Promise.all([
      getCaseDetail(item.id), getCaseCollaborationRecommendation(item.id),
    ])
    selectedCase.value = detail
    recommendation.value = collaboration
    hydrateWorkflow(detail)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '事件详情加载失败'
  } finally {
    detailLoading.value = false
  }
}

function closeCase() {
  if (workflowBusy.value) return
  selectedCase.value = null
  recommendation.value = null
  workflowMessage.value = ''
}

function adoptRecommendation() {
  if (!recommendation.value) return
  workflow.responsibleUnit = recommendation.value.recommended_primary_unit
  workflow.collaborators = [...recommendation.value.recommended_collaborator_units]
  workflowMessage.value = '已采用智能体主协办方案，请核对后确认派单'
}

function toggleCollaborator(unit: string) {
  const index = workflow.collaborators.indexOf(unit)
  if (index >= 0) workflow.collaborators.splice(index, 1)
  else workflow.collaborators.push(unit)
}

async function runWorkflow(action: WorkflowAction) {
  const current = selectedCase.value
  if (!current) return
  if (action === 'dispatch' && !workflow.responsibleUnit) {
    workflowMessage.value = '请先选择主办单位'
    return
  }
  const labels: Record<WorkflowAction, string> = {
    dispatch: '确认执行协同派单', submit_result: '确认提交处置结果',
    return_for_rework: '确认退回补充', approve_close: '确认复核办结',
  }
  if (!window.confirm(`${labels[action]}？该操作会真实更新事件状态和处置轨迹。`)) return
  workflowBusy.value = true
  workflowMessage.value = ''
  try {
    const result = await executeCaseWorkflow(current.id, {
      action,
      responsible_unit: workflow.responsibleUnit || undefined,
      collaborator_units: workflow.collaborators,
      evidence_complete: action === 'submit_result' ? workflow.evidenceComplete : undefined,
      note: workflow.note || undefined,
    })
    selectedCase.value = result.case
    const index = cases.value.findIndex((item) => item.id === result.case.id)
    if (index >= 0) cases.value[index] = result.case
    hydrateWorkflow(result.case)
    workflowMessage.value = `${labels[action].replace('确认', '')}成功，业务状态和处置轨迹已更新`
  } catch (reason) {
    workflowMessage.value = reason instanceof Error ? reason.message : '协同处置操作失败'
  } finally {
    workflowBusy.value = false
  }
}

onMounted(() => {
  filters.keyword = String(route.query.keyword ?? '')
  load()
})
watch(() => route.query.keyword, (keyword) => {
  const value = String(keyword ?? '')
  if (value !== filters.keyword) {
    filters.keyword = value
    load()
  }
})
</script>

<template>
  <div class="dashboard-page feature-page">
    <section class="page-heading feature-heading">
      <span class="page-emblem"><AppIcon name="database" /></span>
      <div class="page-title-copy">
        <h1>治理事件协同处置中心</h1>
        <p class="heading-description">围绕事件分级、主协办派单、处置反馈与证据复核形成业务闭环</p>
      </div>
      <span class="result-count">当前结果 <strong>{{ cases.length }}</strong> 件</span>
    </section>

    <section class="workflow-overview" aria-label="协同处置流程概览">
      <article><span>01</span><div><small>待智能派单</small><strong>{{ workflowCounts.pending }}</strong></div><p>明确主办与协办责任</p></article>
      <article><span>02</span><div><small>协同处置中</small><strong>{{ workflowCounts.processing }}</strong></div><p>反馈进度并沉淀轨迹</p></article>
      <article><span>03</span><div><small>待证据复核</small><strong>{{ workflowCounts.review }}</strong></div><p>通过后才允许办结归档</p></article>
    </section>

    <section class="panel filter-panel">
      <label>关键词<input v-model="filters.keyword" placeholder="事件编号或关键词" @keyup.enter="load"></label>
      <label>所属区域<select v-model="filters.district"><option value="">全部区域</option><option v-for="item in districts" :key="item">{{ item }}</option></select></label>
      <label>事件类别<select v-model="filters.category"><option value="">全部类别</option><option v-for="item in BUSINESS.categories" :key="item">{{ item }}</option></select></label>
      <label>处置状态<select v-model="filters.status"><option value="">全部状态</option><option v-for="item in statuses" :key="item">{{ item }}</option></select></label>
      <label>优先级<select v-model="filters.priority"><option value="">全部级别</option><option v-for="item in priorities" :key="item">{{ item }}</option></select></label>
      <div class="filter-actions"><button class="secondary-button" @click="reset">重置</button><button class="primary-button" @click="load">查询事件</button></div>
    </section>

    <div v-if="error" class="notice error-notice">{{ error }}</div>

    <section class="panel cases-center-panel">
      <header class="panel-header"><div><h2>事件查询结果</h2><p>点击事件进入智能协同处置；所有操作均写入本地 SQLite Demo 数据库</p></div></header>
      <div class="table-wrap">
        <table class="cases-center-table">
          <thead><tr><th>事件编号</th><th>事件描述</th><th>类别</th><th>区域 / 街道</th><th>优先级</th><th>状态</th><th>主办 / 协办</th><th>上报时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in cases" :key="item.id" class="case-row" @dblclick="openCase(item)">
              <td class="case-id">{{ item.id }}</td><td class="case-title" :title="item.description">{{ item.description }}</td><td>{{ item.category }}</td>
              <td>{{ item.district }}<small class="street-name">{{ item.street }}</small></td><td><span class="priority-tag" :class="`priority-${item.priority}`">{{ item.priority }}</span></td>
              <td><span class="status-tag" :class="statusClass(item.status)">{{ item.status }}</span></td>
              <td class="unit-cell">{{ item.responsible_unit || '待分派' }}<small>{{ item.collaborator_units?.length ? `${item.collaborator_units.length} 个协办单位` : '暂无协办' }}</small></td>
              <td>{{ formatTime(item.created_at) }}</td><td><button class="table-action" @click="openCase(item)">协同处置</button></td>
            </tr>
            <tr v-if="!cases.length"><td colspan="9" class="empty-table">{{ loading ? '正在查询事件…' : '没有符合条件的事件' }}</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="selectedCase" class="workflow-backdrop" @click.self="closeCase">
      <aside class="workflow-drawer" aria-label="治理事件协同处置">
        <header>
          <div><small>协同处置工作台</small><h2>{{ selectedCase.id }}</h2></div>
          <button class="icon-button" aria-label="关闭" @click="closeCase"><AppIcon name="close" /></button>
        </header>
        <div v-if="detailLoading" class="workflow-loading">正在加载事件业务上下文…</div>
        <div v-else class="workflow-content">
          <section class="case-brief">
            <div class="case-brief-heading"><span class="priority-tag" :class="`priority-${selectedCase.priority}`">{{ selectedCase.level }} · {{ selectedCase.priority }}风险</span><span class="status-tag" :class="statusClass(selectedCase.status)">{{ selectedCase.status }}</span></div>
            <h3>{{ selectedCase.description }}</h3>
            <dl><div><dt>治理区域</dt><dd>{{ selectedCase.district }} · {{ selectedCase.street }}</dd></div><div><dt>事件类别</dt><dd>{{ selectedCase.category }}</dd></div><div><dt>上报来源</dt><dd>{{ selectedCase.source }}</dd></div><div><dt>证据状态</dt><dd>{{ selectedCase.evidence_complete ? '完整，待复核' : '待补充' }}</dd></div></dl>
          </section>

          <section v-if="recommendation" class="collaboration-recommendation">
            <div class="recommendation-heading"><div><small>智能体业务研判</small><h3>主协办方案</h3></div><span>需人工确认</span></div>
            <div class="recommended-units"><p><small>建议主办</small><strong>{{ recommendation.recommended_primary_unit }}</strong></p><p><small>建议协办</small><strong>{{ recommendation.recommended_collaborator_units.join('、') || '无' }}</strong></p></div>
            <ul><li v-for="item in recommendation.basis" :key="item">{{ item }}</li></ul>
            <button v-if="selectedCase.status === '待处理'" class="secondary-button" @click="adoptRecommendation">采用智能体方案</button>
          </section>

          <section class="workflow-stage">
            <h3>业务流程</h3>
            <div class="stage-track"><span class="done">受理研判</span><span :class="{ done: selectedCase.status !== '待处理' }">协同派单</span><span :class="{ done: selectedCase.evidence_complete || selectedCase.status === '已完成' }">结果反馈</span><span :class="{ done: selectedCase.status === '已完成' }">复核办结</span></div>
          </section>

          <section v-if="selectedCase.status !== '已完成'" class="workflow-operation">
            <h3>{{ selectedCase.status === '待处理' ? '智能协同派单' : '处置反馈与复核' }}</h3>
            <template v-if="selectedCase.status === '待处理'">
              <label>主办单位<select v-model="workflow.responsibleUnit"><option value="">请选择主办单位</option><option v-for="unit in governanceUnits" :key="unit">{{ unit }}</option></select></label>
              <fieldset><legend>协办单位</legend><button v-for="unit in governanceUnits.filter((item) => item !== workflow.responsibleUnit)" :key="unit" type="button" :class="{ selected: workflow.collaborators.includes(unit) }" @click="toggleCollaborator(unit)">{{ unit }}</button></fieldset>
            </template>
            <template v-else>
              <label class="evidence-check"><input v-model="workflow.evidenceComplete" type="checkbox"><span><strong>处置证据完整</strong><small>包含处置说明和至少一项可追溯结果证据</small></span></label>
            </template>
            <label>操作说明<textarea v-model="workflow.note" maxlength="300" :placeholder="selectedCase.status === '待处理' ? '说明主协办分工和办理要求（可选）' : '填写现场结果、退回原因或复核意见（可选）'"></textarea></label>
            <p v-if="workflowMessage" class="workflow-message">{{ workflowMessage }}</p>
            <div v-if="selectedCase.status === '待处理'" class="workflow-actions"><button class="primary-button" :disabled="workflowBusy" @click="runWorkflow('dispatch')">调用智能体并确认派单</button></div>
            <div v-else class="workflow-actions split"><button class="secondary-button" :disabled="workflowBusy" @click="runWorkflow('return_for_rework')">复核退回补充</button><button class="secondary-button" :disabled="workflowBusy" @click="runWorkflow('submit_result')">提交处置结果</button><button class="primary-button" :disabled="workflowBusy || !selectedCase.evidence_complete" title="需先提交完整证据" @click="runWorkflow('approve_close')">复核办结归档</button></div>
          </section>
          <section v-else class="workflow-complete"><AppIcon name="check" /><div><h3>事件已完成闭环</h3><p>结果证据已经复核，办结时间 {{ formatTime(selectedCase.resolved_at || undefined) }}</p></div></section>

          <section class="workflow-timeline">
            <h3>可追溯处置轨迹</h3>
            <ol><li v-for="(item, index) in selectedCase.timeline" :key="`${item.occurred_at}-${index}`"><i></i><div><strong>{{ item.action }}</strong><small>{{ formatTime(item.occurred_at) }} · {{ item.operator_role }}</small><p>{{ item.note }}</p></div></li></ol>
          </section>
        </div>
      </aside>
    </div>
  </div>
</template>
