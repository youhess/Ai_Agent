<script setup lang="ts">
import { marked } from 'marked'
import { computed, nextTick, ref, watch } from 'vue'
import { normalizeSource, normalizeTrace, streamAgent } from '../api'
import { BUSINESS } from '../config/business'
import type { ChatMessage, StreamEvent } from '../types'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const messages = ref<ChatMessage[]>([])
const question = ref('')
const streaming = ref(false)
const messageList = ref<HTMLElement>()
let controller: AbortController | null = null

marked.setOptions({ breaks: true, gfm: true })

function markdown(content: string) {
  const raw = marked.parse(content) as string
  const document = new DOMParser().parseFromString(raw, 'text/html')
  document.querySelectorAll('script, iframe, object, embed, style, link').forEach((node) => node.remove())
  document.querySelectorAll('*').forEach((node) => {
    for (const attribute of [...node.attributes]) {
      if (attribute.name.startsWith('on') || attribute.name === 'style') node.removeAttribute(attribute.name)
      if (['href', 'src'].includes(attribute.name) && !/^(https?:|mailto:|\/)/i.test(attribute.value)) node.removeAttribute(attribute.name)
    }
  })
  document.querySelectorAll('a').forEach((node) => { node.target = '_blank'; node.rel = 'noopener noreferrer' })
  return document.body.innerHTML
}

const canSend = computed(() => question.value.trim().length > 0 && !streaming.value)

async function scrollBottom() {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
}

function answerText(data: unknown) {
  if (typeof data === 'string') return data
  if (data && typeof data === 'object') {
    const value = data as Record<string, unknown>
    return String(value.content ?? value.answer ?? value.text ?? value.delta ?? value.message ?? '')
  }
  return String(data ?? '')
}

async function send(text?: string) {
  const prompt = (text ?? question.value).trim()
  if (!prompt || streaming.value) return
  question.value = ''
  const history = messages.value.map(({ role, content }) => ({ role, content }))
  const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: prompt }
  const assistant: ChatMessage = { id: crypto.randomUUID(), role: 'assistant', content: '', traces: [], traceExpanded: false, sources: [] }
  messages.value.push(userMessage, assistant)
  streaming.value = true
  controller = new AbortController()
  await scrollBottom()

  const onEvent = (event: StreamEvent) => {
    if (event.type === 'trace') {
      const items = Array.isArray(event.data) ? event.data : [event.data]
      items.forEach((item) => {
        const trace = normalizeTrace(item, assistant.traces?.length ?? 0)
        const existing = assistant.traces?.findIndex((entry) => entry.id === trace.id) ?? -1
        if (existing >= 0) assistant.traces?.splice(existing, 1, trace)
        else assistant.traces?.push(trace)
      })
    } else if (event.type === 'source') {
      const items = Array.isArray(event.data) ? event.data : [event.data]
      assistant.sources?.push(...items.map(normalizeSource))
    } else if (event.type === 'answer') {
      assistant.content += answerText(event.data)
    } else if (event.type === 'error') {
      assistant.error = true
      assistant.content += `\n\n${answerText(event.data) || 'AI 分析服务返回异常，请稍后重试。'}`
    } else if (event.type === 'done') {
      assistant.traces?.forEach((trace) => { if (trace.status === 'running') trace.status = 'done' })
    }
    scrollBottom()
  }

  try {
    await streamAgent(prompt, history, controller.signal, onEvent)
    if (!assistant.content && !assistant.error) assistant.content = '分析已完成，请结合上方任务执行过程与数据来源查看结果。'
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      assistant.error = true
      assistant.content = (error as Error).message || '服务暂时不可用，请稍后重试。'
    }
  } finally {
    streaming.value = false
    controller = null
    await scrollBottom()
  }
}

function stop() {
  controller?.abort()
  streaming.value = false
}

function close() {
  emit('close')
}

watch(() => props.open, (open) => { if (open) scrollBottom() })
</script>

<template>
  <Transition name="fade"><div v-if="open" class="drawer-backdrop" @click="close" /></Transition>
  <Transition name="slide">
    <aside v-if="open" class="agent-drawer" aria-label="社会治理分析助手">
      <header class="agent-header">
        <div class="agent-identity"><span class="agent-logo"><AppIcon name="spark" /></span><div><h2>{{ BUSINESS.assistant.title }}</h2></div></div>
        <button class="icon-button" aria-label="关闭" @click="close"><AppIcon name="close" /></button>
      </header>

      <div ref="messageList" class="message-list">
        <div v-if="!messages.length" class="agent-welcome">
          <span class="welcome-mark"><AppIcon name="spark" /></span>
          <h3>{{ BUSINESS.assistant.welcomeTitle }}</h3>
          <p>{{ BUSINESS.assistant.welcomeText }}</p>
          <div class="suggestions">
            <span>{{ BUSINESS.assistant.suggestionsTitle }}</span>
            <button v-for="item in BUSINESS.assistant.suggestions" :key="item" @click="send(item)">{{ item }}<b>›</b></button>
          </div>
        </div>

        <template v-for="message in messages" :key="message.id">
          <div v-if="message.role === 'user'" class="message-row user-row"><div class="user-message">{{ message.content }}</div><span class="user-avatar">我</span></div>
          <div v-else class="message-row assistant-row">
            <span class="assistant-avatar"><AppIcon name="spark" /></span>
            <div class="assistant-body">
              <div v-if="message.traces?.length" class="trace-card">
                <button class="trace-heading" :aria-expanded="message.traceExpanded" @click="message.traceExpanded = !message.traceExpanded">
                  <AppIcon name="rate" /><span>{{ BUSINESS.assistant.traceTitle }}</span>
                  <small>{{ streaming && message === messages[messages.length - 1] ? '执行中' : `${message.traces.length} 步` }}</small>
                  <b>{{ message.traceExpanded ? '收起' : '展开' }}</b>
                </button>
                <div v-if="message.traceExpanded" class="trace-list">
                  <div v-for="trace in message.traces" :key="trace.id" class="trace-item" :class="trace.status">
                    <span class="trace-dot" /><div><strong>{{ trace.title }}</strong><p v-if="trace.detail">{{ trace.detail }}</p></div>
                  </div>
                </div>
              </div>
              <div v-if="message.content" class="markdown-body" :class="{ error: message.error }" v-html="markdown(message.content)" />
              <div v-else-if="streaming && message === messages[messages.length - 1]" class="thinking"><i /><i /><i /><span>{{ BUSINESS.assistant.thinking }}</span></div>
              <div v-if="message.sources?.length" class="sources-block">
                <h4><AppIcon name="database" />{{ BUSINESS.assistant.sourcesTitle }}</h4>
                <a v-for="(source, index) in message.sources" :key="source.id ?? index" :href="source.url || undefined" :target="source.url ? '_blank' : undefined" rel="noopener noreferrer">
                  <span>{{ index + 1 }}</span><div><strong>{{ source.title }}</strong><p v-if="source.excerpt">{{ source.excerpt }}</p></div>
                </a>
              </div>
            </div>
          </div>
        </template>
      </div>

      <footer class="agent-composer">
        <div class="composer-box">
          <textarea v-model="question" :placeholder="BUSINESS.assistant.inputPlaceholder" rows="2" @keydown.enter.exact.prevent="send()" />
          <button v-if="streaming" class="stop-button" @click="stop"><span />{{ BUSINESS.assistant.stop }}</button>
          <button v-else class="send-button" :disabled="!canSend" aria-label="发送" @click="send()"><AppIcon name="send" /></button>
        </div>
        <p>{{ BUSINESS.footer }}</p>
      </footer>
    </aside>
  </Transition>
</template>
