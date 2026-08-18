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
  error?: boolean
}

export interface StreamEvent {
  type: 'trace' | 'source' | 'answer' | 'error' | 'done' | string
  data: unknown
}
