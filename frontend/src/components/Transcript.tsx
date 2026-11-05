import { useEffect, useRef } from 'react'
import type { AgentEvent } from '../api.ts'
import { AGENTS, TOOL_LABEL } from '../agents.ts'

function argLine(args: Record<string, unknown>) {
  const skip = new Set(['author', 'reason', 'body', 'rationale', 'note', 'task'])
  return Object.entries(args)
    .filter(([k, v]) => !skip.has(k) && v !== null && v !== undefined && v !== '')
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(' · ')
}

export default function Transcript({ events, live }: { events: AgentEvent[]; live: boolean }) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (live) end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [events.length, live])

  if (events.length === 0) {
    return (
      <div className="transcript empty">
        <p>No one's on this ticket yet.</p>
        <p className="muted small">Press <b>Start team</b> on the ticket. The Boss reads it first, then calls whoever it needs.</p>
      </div>
    )
  }
  return (
    <div className="transcript" aria-live="polite">
      {events.map((e, i) => {
        const a = AGENTS[e.agent]
        const firstOfRun = e.step === 1
        const handoffs = e.tools.filter((t) => t.name === 'delegate')
        return (
          <div key={e.index} className="turn" style={{ ['--c' as string]: a.color, ['--t' as string]: a.tint }}>
            {firstOfRun && e.delegated_by && (
              <div className="routing-slip">
                📞 <b>{AGENTS[e.delegated_by].label}</b> → <b>{a.label}</b>
                <span className="slip-task">“{e.task}”</span>
              </div>
            )}
            <div className="turn-row">
              <div className="turn-avatar" title={a.label} aria-hidden="true">{a.icon}</div>
              <div className="turn-body">
                <div className="turn-meta">
                  <b>{a.label}</b> · step {e.step}
                  <time>{new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
                </div>
                {e.said.map((s, k) => <p key={k} className="bubble">{s}</p>)}
                <div className="receipts">
                  {e.tools.filter((t) => t.name !== 'final_result' && t.name !== 'delegate').map((t, k) => (
                    <div key={k} className={`receipt ${t.ok ? '' : 'bad'}`}>
                      <div className="receipt-head">
                        <span>{t.ok ? '🧾' : '⛔'} {TOOL_LABEL[t.name] ?? t.name}</span>
                        <code>{t.name}</code>
                      </div>
                      {argLine(t.args) && <div className="receipt-args">{argLine(t.args)}</div>}
                      <div className="receipt-result">{t.result}</div>
                    </div>
                  ))}
                  {handoffs.map((t, k) => (
                    <div key={`h${k}`} className="handoff">
                      📞 asked <b>{AGENTS[(t.args.to as keyof typeof AGENTS) ?? 'boss']?.label ?? String(t.args.to)}</b>
                      {t.result && t.result !== '(pending)' && <span className="muted"> · {t.result}</span>}
                    </div>
                  ))}
                </div>
                {e.stop_reason && (
                  <div className={`signoff ${e.stop_reason === 'completed' ? '' : 'bad'}`}>
                    {e.stop_reason === 'completed' ? `✓ ${a.label} filed the report` : `✕ ${e.stop_reason}`}
                    {e.usage && e.depth === 0 && (
                      <span className="muted"> · team used {e.usage.requests} model calls, {(e.usage.input_tokens + e.usage.output_tokens).toLocaleString()} tokens</span>
                    )}
                  </div>
                )}
              </div>
            </div>
            {i === events.length - 1 && live && <div className="typing" aria-label="working"><span /><span /><span /></div>}
          </div>
        )
      })}
      <div ref={end} />
    </div>
  )
}
