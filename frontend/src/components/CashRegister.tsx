import { useEffect, useRef, useState } from 'react'
import type { Approval, Cash } from '../api.ts'
import { money } from '../api.ts'
import { AGENTS } from '../agents.ts'

function Odometer({ value }: { value: number }) {
  const text = value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return (
    <div className="odometer" aria-label={money(value)}>
      <span className="odo-sign">$</span>
      {text.split('').map((ch, i) =>
        /\d/.test(ch) ? (
          <span key={i} className="odo-digit">
            <span className="odo-strip" style={{ transform: `translateY(-${Number(ch) * 10}%)` }}>
              {'0123456789'.split('').map((d) => <span key={d}>{d}</span>)}
            </span>
          </span>
        ) : (
          <span key={i} className="odo-sep">{ch}</span>
        ),
      )}
    </div>
  )
}

const KIND: Record<Approval['kind'], string> = { invoice: 'Vendor invoice', rent: 'Rent', purchase_order: 'Purchase order' }

type Props = {
  cash: Cash | null
  approvals: Approval[]
  approver: string
  setApprover: (s: string) => void
  onApprove: (id: number) => Promise<void>
  onReject: (id: number) => Promise<void>
  focusTicket: number | null
}

export default function CashRegister({ cash, approvals, approver, setApprover, onApprove, onReject, focusTicket }: Props) {
  const [delta, setDelta] = useState<number | null>(null)
  const prev = useRef<number | null>(null)
  const [busy, setBusy] = useState<number | null>(null)

  useEffect(() => {
    if (cash == null) return
    if (prev.current != null && prev.current !== cash.checking_balance) {
      setDelta(cash.checking_balance - prev.current)
      const t = setTimeout(() => setDelta(null), 4000)
      prev.current = cash.checking_balance
      return () => clearTimeout(t)
    }
    prev.current = cash.checking_balance
  }, [cash?.checking_balance])

  const pending = approvals.filter((a) => a.status === 'pending')
  const done = approvals.filter((a) => a.status !== 'pending').slice(-4).reverse()
  const balance = cash?.checking_balance ?? 0
  const signed = approver.trim().length >= 2

  return (
    <aside className="register" aria-label="Cash and approvals">
      <div className="till">
        <div className="till-label">Checking · Campus Customs</div>
        {cash ? <Odometer value={balance} /> : <div className="odometer">—</div>}
        {delta != null && <div className={`delta ${delta < 0 ? 'out' : 'in'}`}>{delta < 0 ? '−' : '+'}{money(Math.abs(delta))}</div>}
        {cash && (
          <div className="till-meta">
            <span>If all pending are approved: <b className={cash.checking_after_all_pending < 0 ? 'neg' : ''}>{money(cash.checking_after_all_pending)}</b></span>
            <span>Paid out so far: <b>{money(cash.payments_made_total)}</b> ({cash.payments_made_count})</span>
          </div>
        )}
      </div>

      <div className="checkbook">
        <div className="checkbook-head">
          <h3>Needs your signature</h3>
          <label className="signer">
            Signing as
            <input value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name" maxLength={60} />
          </label>
        </div>
        {pending.length === 0 && <p className="muted small">Nothing waiting. Agents prepare payments here; only you can sign them.</p>}
        {pending.map((a) => {
          const over = a.amount > balance
          const asker = AGENTS[a.requested_by as keyof typeof AGENTS]
          return (
            <article key={a.id} className={`check ${focusTicket === a.ticket_id ? 'focus' : ''} ${over ? 'over' : ''}`}>
              <div className="check-top">
                <span className="check-no">No. {String(a.id).padStart(4, '0')}</span>
                <span className="check-date">{a.created_at}</span>
              </div>
              <div className="check-pay">
                <span className="muted small">Pay to the order of</span>
                <b>{a.payee}</b>
                <span className="check-amt">{money(a.amount)}</span>
              </div>
              <div className="check-memo">
                <span>Memo: {KIND[a.kind]} · ticket #{a.ticket_id}</span>
                <span className="check-reason">{a.reason}</span>
                <span className="muted small">Prepared by {asker ? `${asker.icon} ${asker.label}` : a.requested_by}</span>
              </div>
              {over && <div className="over-note">Not enough in checking. The bank will refuse this.</div>}
              <div className="check-sign">
                <span className="sig-line">{signed ? approver : ''}</span>
                <div className="check-actions">
                  <button className="btn btn-ghost small" disabled={!signed || busy === a.id} onClick={async () => { setBusy(a.id); await onReject(a.id); setBusy(null) }}>Void</button>
                  <button className="btn btn-green small" disabled={!signed || busy === a.id} onClick={async () => { setBusy(a.id); await onApprove(a.id); setBusy(null) }}>
                    {busy === a.id ? 'Paying…' : '✍️ Sign & pay'}
                  </button>
                </div>
              </div>
            </article>
          )
        })}
        {done.length > 0 && (
          <div className="ledger">
            <h4>Ledger</h4>
            {done.map((a) => (
              <div key={a.id} className={`ledger-row ${a.status}`}>
                <span>{a.status === 'approved' ? '✓' : '✕'} {a.payee}</span>
                <span>{a.status === 'approved' ? `−${money(a.amount)}` : 'voided'}</span>
                <small className="muted">{KIND[a.kind]} · by {a.decided_by}</small>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
