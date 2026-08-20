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
const expanded = ref(false)
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
  const requestController = new AbortController()
  controller = requestController
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
      const shouldReset = Boolean(event.data && typeof event.data === 'object' && (event.data as Record<string, unknown>).reset)
      if (shouldReset) assistant.content = answerText(event.data)
      else assistant.content += answerText(event.data)
    } else if (event.type === 'suggestions') {
      const items = Array.isArray(event.data) ? event.data : []
      assistant.suggestions = items.filter((item): item is string => typeof item === 'string').slice(0, 3)
    } else if (event.type === 'error') {
      assistant.error = true
      assistant.content += `\n\n${answerText(event.data) || '智能分析服务返回异常，请稍后重试。'}`
    } else if (event.type === 'done') {
      assistant.traces?.forEach((trace) => { if (trace.status === 'running') trace.status = 'done' })
    }
    scrollBottom()
  }

  try {
    await streamAgent(prompt, history, requestController.signal, onEvent)
    if (!assistant.content && !assistant.error) assistant.content = '分析已完成，请结合上方任务执行过程与数据来源查看结果。'
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      assistant.error = true
      assistant.content = (error as Error).message || '服务暂时不可用，请稍后重试。'
    }
  } finally {
    if (controller === requestController) {
      streaming.value = false
      controller = null
    }
    await scrollBottom()
  }
}

function stop() {
  controller?.abort()
  streaming.value = false
}

function close() {
  expanded.value = false
  emit('close')
}

function clearConversation() {
  if (!messages.value.length || !window.confirm('确认清空当前对话吗？清空后无法恢复。')) return
  controller?.abort()
  controller = null
  streaming.value = false
  question.value = ''
  messages.value = []
}

watch(() => props.open, (open) => { if (open) scrollBottom() })
</script>

<template>
  <Transition name="chat-window">
    <aside v-if="open" class="agent-drawer" :class="{ expanded }" aria-label="AI智能助手会话窗口">
      <header class="agent-header">
        <div class="agent-identity"><span class="agent-logo"><AppIcon name="bot" /></span><div><h2>{{ BUSINESS.assistant.title }}<b>测试版</b></h2><p>智能研判 · 协同派单 · 证据复核</p></div></div>
        <div class="agent-window-actions">
          <button v-if="messages.length" class="icon-button" aria-label="清空对话" title="清空对话" @click="clearConversation"><AppIcon name="trash" /></button>
          <button class="icon-button" :aria-label="expanded ? '恢复窗口' : '展开窗口'" @click="expanded = !expanded"><AppIcon :name="expanded ? 'restore' : 'maximize'" /></button>
          <button class="icon-button" aria-label="最小化" @click="close"><AppIcon name="minimize" /></button>
        </div>
      </header>

      <div ref="messageList" class="message-list">
        <div v-if="!messages.length" class="agent-welcome">
          <div class="welcome-conversation">
            <span class="welcome-mark"><AppIcon name="bot" /></span>
            <div class="welcome-bubble">
              <h3>{{ BUSINESS.assistant.welcomeTitle }}</h3>
              <p>{{ BUSINESS.assistant.welcomeText }}</p>
            </div>
          </div>
          <div class="suggestions">
            <span>{{ BUSINESS.assistant.suggestionsTitle }}</span>
            <button v-for="item in BUSINESS.assistant.suggestions" :key="item" @click="send(item)">{{ item }}<b>›</b></button>
          </div>
          <div class="assistant-capabilities">
            <span><AppIcon name="bot" /><b>智能问答</b><small>即时响应</small></span>
            <span><AppIcon name="trend" /><b>数据分析</b><small>辅助研判</small></span>
            <span><AppIcon name="document" /><b>政策解读</b><small>资料可溯</small></span>
            <span><AppIcon name="action" /><b>治理建议</b><small>处置参考</small></span>
          </div>
        </div>

        <template v-for="message in messages" :key="message.id">
          <div v-if="message.role === 'user'" class="message-row user-row"><div class="user-message">{{ message.content }}</div><span class="user-avatar">我</span></div>
          <div v-else class="message-row assistant-row">
            <span class="assistant-avatar"><AppIcon name="bot" /></span>
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
              <div v-if="message.suggestions?.length" class="message-suggestions">
                <p>您可以继续这样查询或操作：</p>
                <button v-for="item in message.suggestions" :key="item" :disabled="streaming" @click="send(item)">{{ item }}<b>›</b></button>
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
