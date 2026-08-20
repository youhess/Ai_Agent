export interface MetricValue {
  value: number
  change?: number
  trend?: 'up' | 'down' | 'flat'
}

export interface TrendPoint {
  date: string
  count: number
}

export interface CategoryPoint {
  name: string
  value: number
}

export interface DashboardSummary {
  metrics: Record<string, MetricValue | number>
  trend: TrendPoint[]
  categories: CategoryPoint[]
  districts?: CategoryPoint[]
  updatedAt?: string
}

export interface GovernanceCase {
  id: string | number
  title: string
  category: string
  area: string
  status: string
  reportedAt: string
  description?: string
  district?: string
  created_at?: string
  street?: string
  priority?: string
  source?: string
  level?: string
  responsible_unit?: string
  collaborator_units?: string[]
  evidence_complete?: boolean
  updated_at?: string
  resolved_at?: string | null
  timeline?: Array<{
    action: string
    operator_role: string
    occurred_at: string
    note: string
  }>
}

export type WorkflowAction = 'dispatch' | 'submit_result' | 'return_for_rework' | 'approve_close'

export interface WorkflowActionPayload {
  action: WorkflowAction
  responsible_unit?: string
  collaborator_units?: string[]
  evidence_complete?: boolean
  note?: string
}

export interface CollaborationRecommendation {
  case_id: string
  current_status: string
  recommended_primary_unit: string
  recommended_collaborator_units: string[]
  basis: string[]
  requires_human_confirmation: boolean
  recommended_action: string
}

export interface TraceItem {
  id: string
  title: string
  detail?: string
  status: 'running' | 'done' | 'error'
}

export interface SourceItem {
  id?: string | number
  title: string
  url?: string
  excerpt?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  traces?: TraceItem[]
  traceExpanded?: boolean
  sources?: SourceItem[]
  suggestions?: string[]
  error?: boolean
}

export interface StreamEvent {
  type: 'run' | 'trace' | 'source' | 'answer' | 'suggestions' | 'error' | 'done' | string
  data: unknown
}

export interface KnowledgeDocument {
  id: string
  file_name: string
  source_type: 'built_in' | 'uploaded'
  size_bytes: number
  status: 'pending' | 'indexed' | 'failed'
  chunk_count: number
  index_mode: 'hybrid' | 'lexical'
  error_message?: string
  created_at: string
  indexed_at?: string
}

export interface KnowledgeList {
  items: KnowledgeDocument[]
  count: number
  indexed_count: number
  index_mode: 'hybrid' | 'lexical'
}

export interface DataSummary {
  record_count: number
  latest_case_at?: string
  latest_import?: { id: string; file_name: string; row_count: number; committed_at: string }
}

export interface DataPage {
  items: GovernanceCase[]
  total: number
  page: number
  page_size: number
}

export interface ImportIssue {
  row: number
  field: string
  message: string
}

export interface ImportPreview {
  import_id: string
  file_name: string
  status: 'validated' | 'invalid'
  row_count: number
  recognized_fields: string[]
  errors: ImportIssue[]
  error_count: number
  warnings: string[]
  preview: Array<Record<string, unknown>>
  can_commit: boolean
}

export interface AgentConfig {
  agent_name: string
  domain: string
  provider: string
  model: string
  temperature: number
  llm_configured: boolean
  embedding_configured: boolean
  retrieval_mode: 'hybrid' | 'lexical'
  rag_provider_mode: 'auto' | 'local' | 'xingchen'
  xingchen_rag_configured: boolean
  rag_fallback_enabled: boolean
  rag_last_provider?: 'xingchen' | 'local' | 'local_fallback' | null
  rag_last_error?: string | null
  rag_last_latency_ms?: number | null
  rag_fallback_count: number
  tools: Array<{ name: string; description: string }>
  editable: false
}

export interface AgentRunSummary {
  id: string
  question: string
  intent?: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string
  finished_at?: string
  duration_ms?: number
  tools: string[]
  error_code?: string
}

export interface AgentRunDetail extends AgentRunSummary {
  answer: string
  sources: Array<Record<string, unknown>>
  steps: Array<{
    step_key: string
    title: string
    detail?: string
    status: string
    occurred_at: string
    position: number
  }>
}

export interface AgentRunsPage {
  items: AgentRunSummary[]
  total: number
  page: number
  page_size: number
}
