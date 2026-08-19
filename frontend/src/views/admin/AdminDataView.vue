<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppIcon from '../../components/AppIcon.vue'
import { commitDataset, downloadDataTemplate, getDataRows, getDataSummary, previewDataset } from '../../api'
import type { DataPage, DataSummary, ImportPreview } from '../../types'

const summary = ref<DataSummary>({ record_count: 0 })
const rows = ref<DataPage>({ items: [], total: 0, page: 1, page_size: 20 })
const preview = ref<ImportPreview | null>(null)
const loading = ref(true)
const working = ref(false)
const error = ref('')
const notice = ref('')
const fileInput = ref<HTMLInputElement>()

function formatTime(value?: string) { return value ? value.replace('T', ' ').slice(0, 16) : '-' }

async function load(page = 1) {
  loading.value = true
  error.value = ''
  try { [summary.value, rows.value] = await Promise.all([getDataSummary(), getDataRows(page, 20)]) }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '业务数据加载失败' }
  finally { loading.value = false }
}

async function selectFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  working.value = true
  error.value = ''
  notice.value = ''
  preview.value = null
  try { preview.value = await previewDataset(file) }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '文件预检失败' }
  finally { working.value = false; input.value = '' }
}

async function commit() {
  if (!preview.value?.can_commit) return
  if (!window.confirm(`确认用“${preview.value.file_name}”中的 ${preview.value.row_count} 条记录替换当前全部业务数据吗？`)) return
  working.value = true
  error.value = ''
  try {
    await commitDataset(preview.value.import_id)
    notice.value = `数据集已替换，共导入 ${preview.value.row_count} 条记录`
    preview.value = null
    await load(1)
  } catch (reason) { error.value = reason instanceof Error ? reason.message : '数据导入失败' }
  finally { working.value = false }
}

async function downloadTemplate() {
  try { await downloadDataTemplate() }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '模板下载失败' }
}

onMounted(() => load())
</script>

<template>
  <div class="studio-page">
    <header class="studio-page-header">
      <div><span class="studio-eyebrow">BUSINESS DATA</span><h1>业务数据</h1><p>通过标准模板预检并更新 Agent 使用的治理事件数据</p></div>
      <div class="studio-header-actions">
        <button class="studio-button secondary" @click="downloadTemplate"><AppIcon name="document" />下载标准模板</button>
        <button class="studio-button primary" :disabled="working" @click="fileInput?.click()"><AppIcon name="database" />{{ working ? '正在预检…' : '导入 Excel / CSV' }}</button>
        <input ref="fileInput" class="visually-hidden" type="file" accept=".xlsx,.csv" @change="selectFile">
      </div>
    </header>

    <div v-if="error" class="studio-alert error"><AppIcon name="warning" />{{ error }}</div>
    <div v-if="notice" class="studio-alert success"><AppIcon name="check" />{{ notice }}</div>

    <section class="studio-stat-grid three">
      <article><span class="studio-stat-icon blue"><AppIcon name="database" /></span><div><small>当前记录</small><strong>{{ summary.record_count }}</strong><span>条治理事件</span></div></article>
      <article><span class="studio-stat-icon green"><AppIcon name="clock" /></span><div><small>最近数据时间</small><strong class="text-value">{{ formatTime(summary.latest_case_at).slice(0, 10) }}</strong><span>按事件上报时间统计</span></div></article>
      <article><span class="studio-stat-icon orange"><AppIcon name="refresh" /></span><div><small>最近导入</small><strong class="text-value">{{ summary.latest_import?.file_name || '示例数据' }}</strong><span>{{ summary.latest_import ? `${summary.latest_import.row_count} 条 · ${formatTime(summary.latest_import.committed_at)}` : '尚未通过 Studio 导入' }}</span></div></article>
    </section>

    <section v-if="preview" class="studio-panel import-preview-panel">
      <div class="studio-panel-header"><div><h2>导入预检</h2><p>{{ preview.file_name }} · 共识别 {{ preview.row_count }} 条记录</p></div><button class="text-button" @click="preview = null">关闭预检</button></div>
      <div class="import-check-summary" :class="preview.can_commit ? 'passed' : 'blocked'">
        <AppIcon :name="preview.can_commit ? 'check' : 'warning'" />
        <div><strong>{{ preview.can_commit ? '校验通过，可以替换当前数据集' : `发现 ${preview.error_count} 项错误，暂不能导入` }}</strong><span>已识别字段：{{ preview.recognized_fields.join('、') }}</span></div>
        <button class="studio-button primary" :disabled="!preview.can_commit || working" @click="commit">确认替换数据</button>
      </div>
      <ul v-if="preview.warnings.length" class="import-messages warnings"><li v-for="item in preview.warnings" :key="item">{{ item }}</li></ul>
      <ul v-if="preview.errors.length" class="import-messages errors"><li v-for="(item, index) in preview.errors.slice(0, 20)" :key="index">第 {{ item.row }} 行 · {{ item.field }}：{{ item.message }}</li></ul>
      <div class="studio-table-wrap compact">
        <table class="studio-table"><thead><tr><th>事件 ID</th><th>描述</th><th>区域</th><th>类型</th><th>优先级</th><th>状态</th><th>上报时间</th></tr></thead>
          <tbody><tr v-for="item in preview.preview" :key="String(item.id)"><td class="mono">{{ item.id }}</td><td>{{ item.description }}</td><td>{{ item.district }}</td><td>{{ item.category }}</td><td>{{ item.priority }}</td><td>{{ item.status }}</td><td>{{ formatTime(String(item.created_at)) }}</td></tr></tbody>
        </table>
      </div>
    </section>

    <section class="studio-panel">
      <div class="studio-panel-header"><div><h2>当前数据</h2><p>Agent Tool、综合态势和事件中心共享这一数据集</p></div><span class="studio-count">共 {{ rows.total }} 条</span></div>
      <div class="studio-table-wrap"><table class="studio-table"><thead><tr><th>事件编号</th><th>事件描述</th><th>区域 / 街道</th><th>类型</th><th>优先级</th><th>状态</th><th>上报时间</th></tr></thead>
        <tbody>
          <tr v-for="item in rows.items" :key="item.id"><td class="mono">{{ item.id }}</td><td class="wide-cell">{{ item.description }}</td><td>{{ item.district }}<small class="table-subline">{{ item.street }}</small></td><td>{{ item.category }}</td><td>{{ item.priority }}</td><td><span class="studio-status" :class="item.status === '已完成' ? 'indexed' : 'pending'">{{ item.status }}</span></td><td>{{ formatTime(item.created_at) }}</td></tr>
          <tr v-if="!rows.items.length"><td colspan="7" class="studio-empty">{{ loading ? '正在读取业务数据…' : '当前没有业务数据' }}</td></tr>
        </tbody></table></div>
      <div v-if="rows.total > rows.page_size" class="studio-pagination"><button :disabled="rows.page <= 1" @click="load(rows.page - 1)">上一页</button><span>第 {{ rows.page }} / {{ Math.ceil(rows.total / rows.page_size) }} 页</span><button :disabled="rows.page >= Math.ceil(rows.total / rows.page_size)" @click="load(rows.page + 1)">下一页</button></div>
    </section>
  </div>
</template>
