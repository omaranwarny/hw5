import type { Ticket } from '../api.ts'
import { TYPE_META } from '../agents.ts'

type Props = {
  tickets: Ticket[]
  selected: number | null
  running: boolean
  onSelect: (id: number) => void
  onRun: (id: number) => void
}

const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  waiting_approval: 'Waiting on approval',
  waiting_customer: 'Waiting on customer',
  resolved: 'Resolved',
  rejected: 'Rejected',
}

export default function TicketRail({ tickets, selected, running, onSelect, onRun }: Props) {
  return (
    <aside className="rail" aria-label="Tickets">
      <div className="rail-head">
        <span className="spike" aria-hidden="true" />
        <h2>On the spike</h2>
        <span className="muted small">{tickets.filter((t) => t.state === 'open').length} open</span>
      </div>
      <ol className="stubs">
        {tickets.map((t) => {
          const meta = TYPE_META[t.type] ?? { label: t.type, icon: '📄' }
          const isRunning = t.run?.status === 'running' || t.run?.status === 'queued'
          const hasRun = Boolean(t.run) || t.status !== 'open'
          const closeOut = t.state === 'open' && hasRun && t.pending_approvals === 0 && !isRunning
          return (
            <li key={t.id}>
              <article
                className={`stub ${selected === t.id ? 'selected' : ''} ${t.state} ${isRunning ? 'running' : ''}`}
                onClick={() => onSelect(t.id)}
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && onSelect(t.id)}
                aria-current={selected === t.id}
              >
                <div className="stub-top">
                  <span className="stub-no">#{t.id}</span>
                  <span className="stub-type">{meta.icon} {meta.label}</span>
                </div>
                <h3>{t.subject}</h3>
                <p className="stub-from">from {t.requester}</p>
                {(t.sku || t.lease_id || t.invoice_id) && (
                  <p className="stub-ref">
                    {t.sku && <span>{t.qty}× {t.sku} {t.size}</span>}
                    {t.lease_id && <span>lease {t.lease_id}</span>}
                    {t.invoice_id && <span>inv {t.invoice_id}</span>}
                  </p>
                )}
                <div className="stub-foot">
                  <span className={`status s-${t.status}`}>{STATUS_LABEL[t.status] ?? t.status}</span>
                  {t.pending_approvals > 0 && <span className="chip warn">✍️ {t.pending_approvals} to sign</span>}
                  {t.drafts > 0 && <span className="chip">📝 {t.drafts}</span>}
                </div>
                {t.state === 'resolved' && <div className="stamp" aria-label="Resolved">RESOLVED</div>}
                {isRunning && <div className="working-bar" aria-label="Team is working" />}
                {t.state === 'open' && (
                  <button
                    className={`btn ${closeOut ? 'btn-gold' : 'btn-navy'} stub-run`}
                    disabled={running}
                    onClick={(e) => {
                      e.stopPropagation()
                      onRun(t.id)
                    }}
                    title={running ? 'The team is busy with another ticket' : ''}
                  >
                    {isRunning ? 'Team working…' : closeOut ? '✔ Close out' : hasRun ? '↻ Run again' : '▶ Start team'}
                  </button>
                )}
              </article>
            </li>
          )
        })}
      </ol>
    </aside>
  )
}
