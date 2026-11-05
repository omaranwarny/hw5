import type { Draft } from '../api.ts'
import { money } from '../api.ts'
import { AGENTS } from '../agents.ts'

export default function BoardPapers({ drafts, notes }: { drafts: Draft[]; notes: string | null }) {
  const noteLines = (notes ?? '').split('\n').filter(Boolean)
  if (drafts.length === 0 && noteLines.length <= 1) return null
  return (
    <section className="papers" aria-label="Drafts and notes on the board">
      <h3>Pinned to the board</h3>
      <div className="paper-grid">
        {drafts.map((d) => {
          const p = d.payload as Record<string, any>
          const who = AGENTS[d.author as keyof typeof AGENTS]?.label ?? d.author
          return (
            <article key={d.id} className={`paper ${d.kind}`}>
              <div className="pin" aria-hidden="true" />
              <header>
                <span className="paper-kind">
                  {d.kind === 'purchase_order' ? '📦 Purchase order' : d.kind === 'price_quote' ? '🏷️ Price quote' : '✉️ Customer draft'}
                </span>
                <span className={`paper-status st-${d.status}`}>{d.status.replace(/_/g, ' ')}</span>
              </header>
              {d.kind === 'purchase_order' && (
                <dl>
                  <dt>Vendor</dt><dd>{p.vendor}</dd>
                  <dt>Item</dt><dd>{p.qty}× {p.sku} {p.size}</dd>
                  <dt>Cost</dt><dd>{money(p.total_cost)}</dd>
                  <dt>ETA</dt><dd>{p.eta_if_approved_today} ({p.lead_days}-day lead)</dd>
                </dl>
              )}
              {d.kind === 'price_quote' && (
                <dl>
                  <dt>Deal</dt><dd>{p.qty}× {p.sku} at {money(p.unit_price)} ({p.discount_pct}% off)</dd>
                  <dt>Total</dt><dd>{money(p.total)} <s className="muted">{money(p.total_at_list)}</s></dd>
                  <dt>Margin</dt><dd>{p.margin_pct}%</dd>
                </dl>
              )}
              {d.kind === 'customer_message' && (
                <div className="letter">
                  <div className="letter-to">To: <b>{p.to}</b> · <i>{p.subject}</i></div>
                  <p>{p.body}</p>
                  <div className="unsent">Draft · not sent</div>
                </div>
              )}
              <footer>by {who} · #{d.id}</footer>
            </article>
          )
        })}
      </div>
      {noteLines.length > 1 && (
        <details className="notes">
          <summary>Ticket notes ({noteLines.length})</summary>
          <ul>{noteLines.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </details>
      )}
    </section>
  )
}
