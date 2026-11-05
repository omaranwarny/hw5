import type { Summary } from '../api.ts'
import { AGENTS, AGENT_ORDER, TOOL_LABEL } from '../agents.ts'

export default function TeamSummary({ summary }: { summary: Summary | null }) {
  if (!summary || summary.agents.length === 0) return null
  const byName = Object.fromEntries(summary.agents.map((a) => [a.agent, a]))
  const boss = byName.boss
  return (
    <section className="summary" aria-label="What each agent did">
      <div className="summary-head">
        <h3>Who did what</h3>
        {summary.usage && (
          <span className="muted small">
            {summary.usage.requests} model calls · {summary.usage.tool_calls} tool calls ·{' '}
            {((summary.usage.input_tokens ?? 0) + (summary.usage.output_tokens ?? 0)).toLocaleString()} tokens
          </span>
        )}
      </div>
      {boss?.summary && (
        <blockquote className="decision">
          <span className="decision-label">🎩 Boss's call{boss.final_status ? ` · ${boss.final_status.replace('_', ' ')}` : ''}</span>
          {boss.summary}
          {boss.human_next_steps && boss.human_next_steps.length > 0 && (
            <ul>{boss.human_next_steps.map((s, i) => <li key={i}>👉 {s}</li>)}</ul>
          )}
        </blockquote>
      )}
      <div className="summary-grid">
        {AGENT_ORDER.filter((n) => byName[n]).map((n) => {
          const s = byName[n]
          const a = AGENTS[n]
          const tools = Object.entries(s.tools).filter(([k]) => k !== 'delegate')
          return (
            <article key={n} className="sum-card" style={{ ['--c' as string]: a.color, ['--t' as string]: a.tint }}>
              <header>
                <span>{a.icon}</span> <b>{a.label}</b>
                {s.asked_by.length > 0 && <small> · asked by {s.asked_by.map((x) => AGENTS[x].label).join(', ')}</small>}
              </header>
              <p>{n === 'boss' ? `Ran ${s.steps} steps and handed off ${s.tools.delegate ?? 0} time(s).` : s.summary ?? '—'}</p>
              {tools.length > 0 && (
                <div className="tool-tags">
                  {tools.map(([k, v]) => <span key={k} title={k}>{TOOL_LABEL[k] ?? k}{v > 1 ? ` ×${v}` : ''}</span>)}
                </div>
              )}
              {s.refused > 0 && <p className="small warn-text">⚠ {s.refused} call(s) refused by a guardrail</p>}
            </article>
          )
        })}
      </div>
    </section>
  )
}
