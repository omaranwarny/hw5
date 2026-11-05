import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, API, type AgentEvent, type Approval, type Cash, type Summary, type Ticket, type TicketDetail } from './api.ts'
import TicketRail from './components/TicketRail.tsx'
import AgentSeats from './components/AgentSeats.tsx'
import Transcript from './components/Transcript.tsx'
import TeamSummary from './components/TeamSummary.tsx'
import BoardPapers from './components/BoardPapers.tsx'
import CashRegister from './components/CashRegister.tsx'
import { TYPE_META } from './agents.ts'

export default function App() {
  const [health, setHealth] = useState<{ model: string; shop_date: string } | null>(null)
  const [offline, setOffline] = useState(false)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const since = useRef(0)
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [approver, setApproverState] = useState(() => localStorage.getItem('cc_approver') ?? '')
  const [toast, setToast] = useState<{ text: string; kind: 'ok' | 'bad' } | null>(null)

  const setApprover = (s: string) => {
    setApproverState(s)
    try { localStorage.setItem('cc_approver', s) } catch { /* private mode */ }
  }
  const flash = (text: string, kind: 'ok' | 'bad' = 'ok') => {
    setToast({ text, kind })
    setTimeout(() => setToast(null), 4500)
  }

  const running = tickets.some((t) => t.run?.status === 'running' || t.run?.status === 'queued')

  const inFlight = useRef(false)
  const refresh = useCallback(async () => {
    if (inFlight.current) return            // never run two refreshes at once (no duplicate events)
    inFlight.current = true
    try {
      const [h, t, ev, c, ap] = await Promise.all([api.health(), api.tickets(), api.events(since.current), api.cash(), api.approvals()])
      setHealth(h); setOffline(false)
      setTickets(t.tickets)
      if (ev.events.length) {
        setEvents((prev) => {
          const seen = new Set(prev.map((e) => e.index))
          return [...prev, ...ev.events.filter((e) => !seen.has(e.index))]
        })
      }
      since.current = Math.max(since.current, ev.next_since)
      setCash(c); setApprovals(ap.approvals)
      setSelected((s) => s ?? t.tickets[0]?.id ?? null)
    } catch {
      setOffline(true)
    } finally {
      inFlight.current = false
    }
  }, [])

  // Poll fast while the team works, slower when idle.
  useEffect(() => {
    refresh()
    const id = setInterval(refresh, running ? 1500 : 4000)
    return () => clearInterval(id)
  }, [refresh, running])

  // Selected ticket: detail + per-agent summary.
  const selTicket = tickets.find((t) => t.id === selected) ?? null
  const ticketEvents = useMemo(() => events.filter((e) => e.ticket_id === selected), [events, selected])
  const lastSession = ticketEvents.at(-1)?.session_id
  const sessionEvents = useMemo(() => ticketEvents.filter((e) => e.session_id === lastSession), [ticketEvents, lastSession])
  const live = selTicket?.run?.status === 'running' || selTicket?.run?.status === 'queued'

  useEffect(() => {
    if (selected == null) return
    let alive = true
    Promise.all([api.ticket(selected), api.summary(selected)])
      .then(([d, s]) => { if (alive) { setDetail(d); setSummary(s) } })
      .catch(() => {})
    return () => { alive = false }
  }, [selected, sessionEvents.length, selTicket?.status, selTicket?.pending_approvals, approvals.length])

  const onRun = async (id: number) => {
    try {
      setSelected(id)
      await api.run(id)
      flash(`Team started on ticket #${id}. The Boss is reading it now.`)
      refresh()
    } catch (e) { flash((e as Error).message, 'bad') }
  }
  const onApprove = async (id: number) => {
    try {
      const r = await api.approve(id, approver.trim())
      flash(`Paid. Checking is now ${r.checking_balance.toLocaleString('en-US', { style: 'currency', currency: 'USD' })}.`)
      refresh()
    } catch (e) { flash(`Refused: ${(e as Error).message}`, 'bad') }
  }
  const onReject = async (id: number) => {
    try { await api.reject(id, approver.trim()); flash('Voided. Nothing was paid.'); refresh() }
    catch (e) { flash((e as Error).message, 'bad') }
  }
  const onReset = async () => {
    if (!window.confirm('Reset the shop database to the original values? Approvals, payments and drafts will be cleared. (The audit trail is kept.)')) return
    try { const r = await api.reset(); flash(`Database reset. Checking back to $${r.checking_balance.toFixed(2)}.`); refresh() }
    catch (e) { flash((e as Error).message, 'bad') }
  }

  const notesCount = (detail?.ticket.notes ?? '').split('\n').filter(Boolean).length
  const hasSide = Boolean(
    (!live && summary && summary.agents.length > 0) || (detail && (detail.board_drafts.length > 0 || notesCount > 1)),
  )
  const meta = selTicket ? TYPE_META[selTicket.type] ?? { label: selTicket.type, icon: '📄' } : null

  return (
    <div className="desk">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">CC</span>
          <div>
            <strong>Campus Customs · Back Office</strong>
            <small>57 Broadway, New Haven · agent operations desk</small>
          </div>
        </div>
        <div className="topbar-right">
          {health && <span className="pill">📅 Shop date {health.shop_date}</span>}
          {health && <span className="pill">🤖 {health.model}</span>}
          <span className={`pill ${offline ? 'pill-bad' : running ? 'pill-live' : 'pill-ok'}`}>
            {offline ? `Backend offline (${API})` : running ? '● Team working' : '● Desk ready'}
          </span>
          <button className="btn btn-ghost-light small" onClick={onReset} disabled={running}>⟲ Reset day</button>
        </div>
      </header>

      <main className="layout">
        <TicketRail tickets={tickets} selected={selected} running={running} onSelect={setSelected} onRun={onRun} />

        <section className="stage">
          {selTicket && meta && (
            <div className="stage-head">
              <div>
                <span className="eyebrow">{meta.icon} {meta.label} · #{selTicket.id}</span>
                <h1>{selTicket.subject}</h1>
                <p className="muted">from {selTicket.requester}{detail?.ticket.notes ? ` · “${detail.ticket.notes.split('\n')[0]}”` : ''}</p>
              </div>
              {selTicket.state === 'resolved' && <div className="stamp big">RESOLVED</div>}
            </div>
          )}
          <AgentSeats events={sessionEvents} live={Boolean(live)} />
          <div className={`stage-cols ${hasSide ? '' : 'solo'}`}>
            <div className="col-main">
              <h3 className="section-title">Live transcript {live && <span className="live-dot">LIVE</span>}</h3>
              <Transcript events={sessionEvents} live={Boolean(live)} />
            </div>
            <div className="col-side">
              <TeamSummary summary={live ? null : summary} />
              {detail && <BoardPapers drafts={detail.board_drafts} notes={detail.ticket.notes} />}
            </div>
          </div>
        </section>

        <CashRegister
          cash={cash}
          approvals={approvals}
          approver={approver}
          setApprover={setApprover}
          onApprove={onApprove}
          onReject={onReject}
          focusTicket={selected}
        />
      </main>

      {toast && <div className={`toast ${toast.kind}`} role="status">{toast.text}</div>}
    </div>
  )
}
