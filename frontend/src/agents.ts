import type { AgentName } from './api.ts'

// Each agent has its own seat, color, icon and voice on the desk.
export const AGENTS: Record<AgentName, { label: string; role: string; icon: string; color: string; tint: string }> = {
  boss: { label: 'Boss', role: 'Routes tickets · makes the call', icon: '🎩', color: '#00356b', tint: '#e6eef8' },
  inventory: { label: 'Inventory', role: 'Shelves · vendors · restock', icon: '📦', color: '#b8641c', tint: '#fbefe3' },
  accounting: { label: 'Accounting', role: 'Cash · invoices · margins', icon: '🧮', color: '#2e7d4f', tint: '#e5f3ea' },
  facilities: { label: 'Facilities', role: 'Lease · rent · the shop', icon: '🔑', color: '#6b4fa0', tint: '#efe9f8' },
  customer_service: { label: 'Customer Service', role: 'Drafts to customers', icon: '💬', color: '#c0396b', tint: '#fbe8ef' },
}
export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const TYPE_META: Record<string, { label: string; icon: string }> = {
  customer_order: { label: 'Customer order', icon: '🧾' },
  rent_notice: { label: 'Rent notice', icon: '🏠' },
  price_override: { label: 'Price override', icon: '🏷️' },
}

// Friendly names for tools in the transcript.
export const TOOL_LABEL: Record<string, string> = {
  get_today: 'checked the date',
  get_ticket: 'read the ticket',
  list_open_tickets: 'scanned the board',
  list_tickets: 'scanned the board',
  check_stock: 'counted stock',
  list_vendors: 'looked up vendors',
  get_invoice_status: 'pulled an invoice',
  list_open_invoices: 'listed open invoices',
  get_lease_due: 'checked the lease',
  get_pricing: 'checked pricing',
  quote_price: 'ran a quote',
  get_cash_balance: 'checked cash',
  list_approvals: 'checked approvals',
  add_ticket_note: 'left a note',
  update_ticket_status: 'updated status',
  fulfill_from_stock: 'pulled stock',
  create_purchase_order: 'drafted a PO',
  draft_customer_message: 'drafted a message',
  record_price_decision: 'set the price',
  request_payment: 'asked a human to approve',
  delegate: 'handed off',
  final_result: 'filed the report',
}
