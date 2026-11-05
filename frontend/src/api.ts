// Typed client for the Campus Customs Ops API (FastAPI, http://localhost:8000).
export const API = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export type Outcome = {
  ticket_id: number
  final_status: string
  decision: string
  actions_taken: string[]
  approvals_waiting: number[]
  draft_ids: number[]
  human_next_steps: string[]
}
export type RunInfo = {
  status: 'queued' | 'running' | 'done' | 'error'
  started_at?: string
  finished_at?: string
  outcome?: Outcome
  error?: string
}
export type Ticket = {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  state: 'open' | 'resolved'
  pending_approvals: number
  drafts: number
  created_at: string
  run?: RunInfo | null
}
export type ToolCall = { name: string; args: Record<string, unknown>; result: string; ok: boolean }
export type AgentEvent = {
  index: number
  timestamp: string
  session_id: string
  ticket_id: number | null
  agent: AgentName
  depth: number
  delegated_by: AgentName | null
  step: number
  task: string
  said: string[]
  tools: ToolCall[]
  output: string | null
  stop_reason: string | null
  usage: Record<string, number> | null
}
export type Approval = {
  id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number
  amount: number
  payee: string
  ticket_id: number | null
  reason: string
  requested_by: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  decided_by: string | null
  decided_at: string | null
  payment_id: number | null
}
export type Cash = {
  checking_balance: number
  pending_total: number
  checking_after_all_pending: number
  payments_made_total: number
  payments_made_count: number
}
export type Draft = {
  id: number
  kind: 'purchase_order' | 'customer_message' | 'price_quote'
  author: string
  status: string
  payload: Record<string, unknown>
  created_at: string
}
export type TicketDetail = { ticket: Ticket & { notes: string | null }; board_drafts: Draft[]; approvals: Approval[] }
export type AgentSummary = {
  agent: AgentName
  runs: number
  steps: number
  tools: Record<string, number>
  asked_by: AgentName[]
  summary: string | null
  facts: string[]
  actions: string[]
  approval_ids: number[]
  draft_ids: number[]
  refused: number
  final_status?: string | null
  human_next_steps?: string[]
}
export type Summary = {
  ticket_id: number
  session_id: string | null
  sessions: string[]
  usage: Record<string, number> | null
  agents: AgentSummary[]
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API + path, {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const d = (data as { detail?: unknown }).detail
    throw new Error(typeof d === 'string' ? d : `Request failed (${res.status})`)
  }
  return data as T
}

export const api = {
  health: () => req<{ ok: boolean; model: string; shop_date: string; running: boolean }>('/api/health'),
  tickets: () => req<{ today: string; tickets: Ticket[] }>('/api/tickets'),
  ticket: (id: number) => req<TicketDetail>(`/api/tickets/${id}`),
  summary: (id: number) => req<Summary>(`/api/tickets/${id}/summary`),
  run: (id: number) => req<{ ok: boolean }>(`/api/tickets/${id}/run`, { method: 'POST' }),
  events: (since: number) => req<{ events: AgentEvent[]; next_since: number }>(`/api/events?since=${since}&limit=1000`),
  approvals: () => req<{ approvals: Approval[] }>('/api/approvals?status=all'),
  approve: (id: number, approver: string) =>
    req<{ ok: boolean; checking_balance: number }>(`/api/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approver, note: 'Approved on the desk' }),
    }),
  reject: (id: number, approver: string) =>
    req<{ ok: boolean }>(`/api/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ approver, note: 'Rejected on the desk' }),
    }),
  cash: () => req<Cash>('/api/cash'),
  reset: () => req<{ ok: boolean; checking_balance: number }>('/api/reset', { method: 'POST' }),
}

export const money = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
