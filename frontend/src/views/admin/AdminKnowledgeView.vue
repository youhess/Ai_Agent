<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppIcon from '../../components/AppIcon.vue'
import { deleteKnowledgeDocument, getKnowledgeDocuments, reindexKnowledge, uploadKnowledgeDocument } from '../../api'
import type { KnowledgeList } from '../../types'

const data = ref<KnowledgeList>({ items: [], count: 0, indexed_count: 0, index_mode: 'lexical' })
const loading = ref(true)
const working = ref(false)
const error = ref('')
const notice = ref('')
const fileInput = ref<HTMLInputElement>()

function formatSize(value: number) {
  return value < 1024 * 1024 ? `${Math.max(1, Math.round(value / 1024))} KB` : `${(value / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(value?: string) {
  return value ? value.replace('T', ' ').slice(0, 16) : '-'
}

function statusLabel(status: string) {
  return status === 'indexed' ? '已索引' : status === 'failed' ? '索引失败' : '待索引'
}

async function load() {
  loading.value = true
  error.value = ''
  try { data.value = await getKnowledgeDocuments() }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '知识库加载失败' }
  finally { loading.value = false }
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  working.value = true
  error.value = ''
  notice.value = ''
  try {
    const result = await uploadKnowledgeDocument(file)
    if (result.index.success) notice.value = `“${file.name}”已上传并完成索引处理`
    else error.value = `“${file.name}”已保存，但解析失败：${result.index.failures[0]?.message || '请检查文档内容'}`
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '文档上传失败'
  } finally {
    working.value = false
    input.value = ''
  }
}

async function reindex() {
  working.value = true
  error.value = ''
  notice.value = ''
  try {
    await reindexKnowledge()
    notice.value = '知识索引已重新建立'
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '索引重建失败'
  } finally { working.value = false }
}

async function remove(id: string, name: string) {
  if (!window.confirm(`确认删除上传资料“${name}”吗？删除后将同步重建知识索引。`)) return
  working.value = true
  error.value = ''
  try {
    await deleteKnowledgeDocument(id)
    notice.value = `“${name}”已删除`
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '文档删除失败'
  } finally { working.value = false }
}

onMounted(load)
</script>

<template>
  <div class="studio-page">
    <header class="studio-page-header">
      <div><span class="studio-eyebrow">KNOWLEDGE BASE</span><h1>知识库</h1><p>维护 Agent 可检索的治理规范、业务指南和处置资料</p></div>
      <div class="studio-header-actions">
        <button class="studio-button secondary" :disabled="working" @click="reindex"><AppIcon name="refresh" />重新建立索引</button>
        <button class="studio-button primary" :disabled="working" @click="fileInput?.click()"><AppIcon name="document" />{{ working ? '正在处理…' : '上传文件' }}</button>
        <input ref="fileInput" class="visually-hidden" type="file" accept=".pdf,.docx,.txt,.md" @change="upload">
      </div>
    </header>

    <div v-if="error" class="studio-alert error"><AppIcon name="warning" />{{ error }}</div>
    <div v-if="notice" class="studio-alert success"><AppIcon name="check" />{{ notice }}</div>

    <section class="studio-stat-grid three">
      <article><span class="studio-stat-icon blue"><AppIcon name="document" /></span><div><small>资料总数</small><strong>{{ data.count }}</strong><span>份治理资料</span></div></article>
      <article><span class="studio-stat-icon green"><AppIcon name="check" /></span><div><small>已完成索引</small><strong>{{ data.indexed_count }}</strong><span>份可用于检索</span></div></article>
      <article><span class="studio-stat-icon orange"><AppIcon name="trend" /></span><div><small>当前检索模式</small><strong class="text-value">{{ data.index_mode === 'hybrid' ? '混合检索' : '关键词兜底' }}</strong><span>{{ data.index_mode === 'hybrid' ? '语义 70% + 关键词 30%' : '无需外部模型即可运行' }}</span></div></article>
    </section>

    <section class="studio-panel">
      <div class="studio-panel-header"><div><h2>资料列表</h2><p>内置资料受保护；上传资料可删除并自动更新索引</p></div><span class="studio-count">共 {{ data.count }} 份</span></div>
      <div class="studio-table-wrap">
        <table class="studio-table">
          <thead><tr><th>文件名称</th><th>来源</th><th>文件大小</th><th>分块数量</th><th>检索方式</th><th>索引时间</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in data.items" :key="item.id">
              <td><div class="file-cell"><span><AppIcon name="document" /></span><div><strong>{{ item.file_name }}</strong><small v-if="item.error_message">{{ item.error_message }}</small></div></div></td>
              <td><span class="studio-chip" :class="item.source_type">{{ item.source_type === 'built_in' ? '内置资料' : '上传资料' }}</span></td>
              <td>{{ formatSize(item.size_bytes) }}</td><td>{{ item.chunk_count || '-' }}</td>
              <td>{{ item.index_mode === 'hybrid' ? '混合检索' : '关键词检索' }}</td><td>{{ formatTime(item.indexed_at) }}</td>
              <td><span class="studio-status" :class="item.status">{{ statusLabel(item.status) }}</span></td>
              <td><button v-if="item.source_type === 'uploaded'" class="text-button danger" :disabled="working" @click="remove(item.id, item.file_name)">删除</button><span v-else class="muted-text">受保护</span></td>
            </tr>
            <tr v-if="!data.items.length"><td colspan="8" class="studio-empty">{{ loading ? '正在读取知识库…' : '暂无知识资料' }}</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
