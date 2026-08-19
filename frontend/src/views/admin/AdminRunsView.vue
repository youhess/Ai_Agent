<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppIcon from '../../components/AppIcon.vue'
import { getAgentRun, getAgentRuns } from '../../api'
import type { AgentRunDetail, AgentRunsPage } from '../../types'

const data = ref<AgentRunsPage>({ items: [], total: 0, page: 1, page_size: 20 })
const detail = ref<AgentRunDetail | null>(null)
const loading = ref(true)
const detailLoading = ref(false)
const error = ref('')
const status = ref('')
const query = ref('')

const statusLabels: Record<string, string> = { running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消' }
function formatTime(value?: string) { return value ? value.replace('T', ' ').slice(0, 19) : '-' }
function duration(value?: number) { return value === undefined || value === null ? '-' : value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} s` }

async function load(page = 1) {
  loading.value = true
  error.value = ''
  try { data.value = await getAgentRuns({ page, page_size: 20, status: status.value, query: query.value.trim() }) }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '运行记录加载失败' }
  finally { loading.value = false }
}

async function openDetail(id: string) {
  detailLoading.value = true
  error.value = ''
  try { detail.value = await getAgentRun(id) }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '运行详情加载失败' }
  finally { detailLoading.value = false }
}

function reset() { status.value = ''; query.value = ''; load(1) }
onMounted(() => load())
</script>

<template>
  <div class="studio-page">
    <header class="studio-page-header"><div><span class="studio-eyebrow">AGENT OBSERVABILITY</span><h1>运行记录</h1><p>查看每次分析任务的状态、业务步骤、工具调用与信息来源</p></div><span class="retention-note">保留最近 500 条</span></header>
    <div v-if="error" class="studio-alert error"><AppIcon name="warning" />{{ error }}</div>

    <section class="studio-panel run-filter-panel">
      <label><span>运行状态</span><select v-model="status"><option value="">全部状态</option><option value="completed">已完成</option><option value="running">运行中</option><option value="failed">失败</option><option value="cancelled">已取消</option></select></label>
      <label class="run-search"><span>问题关键词</span><input v-model="query" placeholder="搜索用户问题" @keyup.enter="load(1)"></label>
      <button class="studio-button secondary" @click="reset">重置</button><button class="studio-button primary" @click="load(1)">查询记录</button>
    </section>

    <section class="studio-panel">
      <div class="studio-panel-header"><div><h2>Agent Runs</h2><p>仅记录可解释的业务执行过程，不保存模型思维链</p></div><span class="studio-count">共 {{ data.total }} 条</span></div>
      <div class="studio-table-wrap"><table class="studio-table runs-table"><thead><tr><th>运行编号</th><th>用户问题</th><th>状态</th><th>耗时</th><th>调用工具</th><th>开始时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="item in data.items" :key="item.id"><td class="mono">#{{ item.id.slice(0, 8) }}</td><td class="run-question">{{ item.question }}</td><td><span class="studio-status" :class="item.status">{{ statusLabels[item.status] }}</span></td><td>{{ duration(item.duration_ms) }}</td><td><div class="tool-tags"><span v-for="tool in item.tools.slice(0, 2)" :key="tool">{{ tool }}</span><small v-if="item.tools.length > 2">+{{ item.tools.length - 2 }}</small><span v-if="!item.tools.length" class="empty-tool">自然对话</span></div></td><td>{{ formatTime(item.started_at) }}</td><td><button class="text-button" @click="openDetail(item.id)">查看详情</button></td></tr>
          <tr v-if="!data.items.length"><td colspan="7" class="studio-empty">{{ loading ? '正在读取运行记录…' : '暂无符合条件的运行记录' }}</td></tr>
        </tbody></table></div>
      <div v-if="data.total > data.page_size" class="studio-pagination"><button :disabled="data.page <= 1" @click="load(data.page - 1)">上一页</button><span>第 {{ data.page }} / {{ Math.ceil(data.total / data.page_size) }} 页</span><button :disabled="data.page >= Math.ceil(data.total / data.page_size)" @click="load(data.page + 1)">下一页</button></div>
    </section>

    <div v-if="detail || detailLoading" class="run-detail-mask" @click.self="detail = null">
      <aside class="run-detail-drawer">
        <header><div><span>RUN DETAIL</span><h2>{{ detail ? `#${detail.id.slice(0, 8)}` : '正在加载' }}</h2></div><button aria-label="关闭详情" @click="detail = null"><AppIcon name="close" /></button></header>
        <div v-if="detail" class="run-detail-content">
          <section class="run-summary"><span class="studio-status" :class="detail.status">{{ statusLabels[detail.status] }}</span><strong>{{ detail.question }}</strong><dl><div><dt>开始时间</dt><dd>{{ formatTime(detail.started_at) }}</dd></div><div><dt>运行耗时</dt><dd>{{ duration(detail.duration_ms) }}</dd></div><div><dt>意图识别</dt><dd>{{ detail.intent || '一般交流' }}</dd></div></dl></section>
          <section><h3>执行时间线</h3><div class="run-timeline"><article v-for="step in detail.steps" :key="step.position"><i><AppIcon name="check" /></i><div><small>{{ formatTime(step.occurred_at).slice(11) }}</small><strong>{{ step.title }}</strong><p>{{ step.detail }}</p></div></article><p v-if="!detail.steps.length" class="studio-empty">本次为自然对话，没有调用业务分析步骤</p></div></section>
          <section><h3>调用工具</h3><div class="detail-tags"><span v-for="tool in detail.tools" :key="tool">{{ tool }}</span><span v-if="!detail.tools.length">未调用工具</span></div></section>
          <section v-if="detail.sources.length"><h3>信息来源</h3><ul class="source-list"><li v-for="(source, index) in detail.sources" :key="index"><AppIcon name="document" /><span>{{ source.document_name || source.title || '知识资料' }}</span></li></ul></section>
          <section v-if="detail.answer"><h3>最终回答</h3><div class="run-answer">{{ detail.answer }}</div></section>
          <section v-if="detail.error_code"><h3>错误信息</h3><div class="studio-alert error">{{ detail.error_code }}</div></section>
        </div>
      </aside>
    </div>
  </div>
</template>
