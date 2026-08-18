import type { DashboardSummary, GovernanceCase, SourceItem, StreamEvent, TraceItem } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export interface HealthStatus {
  status: string
  competition_mode: boolean
  llm_configured: boolean
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new Error('无法连接后端服务，请确认 FastAPI 已在 8000 端口启动')
  }
  if (!response.ok) throw new Error(`请求失败（${response.status}）`)
  return response.json() as Promise<T>
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const payload = await request<DashboardSummary | { data: DashboardSummary }>('/api/dashboard/summary')
  return 'data' in payload && payload.data ? payload.data : payload as DashboardSummary
}

export function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/api/health')
}

export async function getCases(filters: Record<string, string | number | undefined> = {}): Promise<GovernanceCase[]> {
  const query = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value))
  })
  const suffix = query.size ? `?${query}` : ''
  const payload = await request<GovernanceCase[] | { data?: GovernanceCase[] | { items?: GovernanceCase[] }; items?: GovernanceCase[]; records?: GovernanceCase[] }>(`/api/cases${suffix}`)
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload.items)) return payload.items
  if (Array.isArray(payload.records)) return payload.records
  if (Array.isArray(payload.data)) return payload.data
  return payload.data?.items ?? []
}

function parseEventBlock(block: string): StreamEvent | null {
  const data = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n')
  if (!data || data === '[DONE]') return data === '[DONE]' ? { type: 'done', data: null } : null
  try {
    return JSON.parse(data) as StreamEvent
  } catch {
    return { type: 'answer', data }
  }
}

export async function streamAgent(
  question: string,
  history: Array<{ role: string; content: string }>,
  signal: AbortSignal,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/agent/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ question, message: question, history }),
    signal,
  })
  if (!response.ok) throw new Error(`AI 分析服务异常（${response.status}）`)
  if (!response.body) throw new Error('当前浏览器无法读取流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const event = parseEventBlock(block)
      if (event) onEvent(event)
    }
    if (done) break
  }
  if (buffer.trim()) {
    const event = parseEventBlock(buffer)
    if (event) onEvent(event)
  }
}

export function normalizeTrace(data: unknown, index: number): TraceItem {
  const value = typeof data === 'object' && data ? data as Record<string, unknown> : { title: String(data) }
  return {
    id: String(value.id ?? `trace-${index}`),
    title: String(value.title ?? value.step ?? value.name ?? '正在分析'),
    detail: value.detail || value.description || value.content || value.summary ? String(value.detail ?? value.description ?? value.content ?? value.summary) : undefined,
    status: value.status === 'error' ? 'error' : value.status === 'running' ? 'running' : 'done',
  }
}

export function normalizeSource(data: unknown): SourceItem {
  const value = typeof data === 'object' && data ? data as Record<string, unknown> : { title: String(data) }
  return {
    id: value.id ? String(value.id) : undefined,
    title: String(value.title ?? value.name ?? value.source ?? value.document_name ?? '业务数据'),
    url: value.url ? String(value.url) : undefined,
    excerpt: value.excerpt || value.description || value.chunk ? String(value.excerpt ?? value.description ?? value.chunk) : undefined,
  }
}
