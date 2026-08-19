import type {
  AgentConfig, AgentRunDetail, AgentRunsPage, DashboardSummary, DataPage, DataSummary,
  GovernanceCase, ImportPreview, KnowledgeDocument, KnowledgeList, SourceItem, StreamEvent, TraceItem,
} from './types'

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
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: unknown } | null
    const detail = payload?.detail
    const message = typeof detail === 'string'
      ? detail
      : typeof detail === 'object' && detail && 'message' in detail
        ? String((detail as { message: unknown }).message)
        : `请求失败（${response.status}）`
    throw new Error(message)
  }
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
  if (!response.ok) throw new Error(`智能分析服务异常（${response.status}）`)
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

export function getKnowledgeDocuments(): Promise<KnowledgeList> {
  return request<KnowledgeList>('/api/admin/knowledge/documents')
}

export function uploadKnowledgeDocument(file: File): Promise<{ document: KnowledgeDocument; index: { success: boolean; mode: string; failures: Array<{ message: string }> } }> {
  const body = new FormData()
  body.append('file', file)
  return request('/api/admin/knowledge/documents', { method: 'POST', body })
}

export function deleteKnowledgeDocument(documentId: string): Promise<unknown> {
  return request(`/api/admin/knowledge/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' })
}

export function reindexKnowledge(): Promise<unknown> {
  return request('/api/admin/knowledge/reindex', { method: 'POST' })
}

export function getDataSummary(): Promise<DataSummary> {
  return request<DataSummary>('/api/admin/data/summary')
}

export function getDataRows(page = 1, pageSize = 20): Promise<DataPage> {
  return request<DataPage>(`/api/admin/data/rows?page=${page}&page_size=${pageSize}`)
}

export function previewDataset(file: File): Promise<ImportPreview> {
  const body = new FormData()
  body.append('file', file)
  return request<ImportPreview>('/api/admin/data/imports/preview', { method: 'POST', body })
}

export function commitDataset(importId: string): Promise<unknown> {
  return request(`/api/admin/data/imports/${encodeURIComponent(importId)}/commit`, { method: 'POST' })
}

export async function downloadDataTemplate(): Promise<void> {
  const response = await fetch(`${API_BASE}/api/admin/data/template`)
  if (!response.ok) throw new Error('模板下载失败')
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = '治理事件导入模板.xlsx'
  anchor.click()
  URL.revokeObjectURL(url)
}

export function getAgentConfig(): Promise<AgentConfig> {
  return request<AgentConfig>('/api/admin/agent/config')
}

export function getAgentRuns(filters: { page?: number; page_size?: number; status?: string; query?: string } = {}): Promise<AgentRunsPage> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  return request<AgentRunsPage>(`/api/admin/runs${params.size ? `?${params}` : ''}`)
}

export function getAgentRun(runId: string): Promise<AgentRunDetail> {
  return request<AgentRunDetail>(`/api/admin/runs/${encodeURIComponent(runId)}`)
}
