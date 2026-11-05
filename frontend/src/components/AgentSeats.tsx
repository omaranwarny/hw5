import type { AgentEvent, AgentName } from '../api.ts'
import { AGENTS, AGENT_ORDER, TOOL_LABEL } from '../agents.ts'

type Seat = { state: 'idle' | 'working' | 'done' | 'error'; last?: AgentEvent }

export function seatStates(events: AgentEvent[], live: boolean): Record<AgentName, Seat> {
  const seats = Object.fromEntries(AGENT_ORDER.map((a) => [a, { state: 'idle' } as Seat])) as Record<AgentName, Seat>
  for (const e of events) {
    const s = seats[e.agent]
    if (!s) continue
    s.last = e
    if (e.stop_reason) s.state = e.stop_reason === 'completed' ? 'done' : 'error'
    else s.state = live ? 'working' : 'done'
  }
  return seats
}

export default function AgentSeats({ events, live }: { events: AgentEvent[]; live: boolean }) {
  const seats = seatStates(events, live)
  const speaking = live ? events[events.length - 1]?.agent : undefined
  return (
    <section className="seats" aria-label="Agent team">
      {AGENT_ORDER.map((name) => {
        const a = AGENTS[name]
        const s = seats[name]
        const lastTool = s.last?.tools.filter((t) => t.name !== 'final_result').at(-1)
        return (
          <div
            key={name}
            className={`seat ${s.state} ${speaking === name ? 'speaking' : ''}`}
            style={{ ['--c' as string]: a.color, ['--t' as string]: a.tint }}
          >
            <div className="seat-avatar" aria-hidden="true">{a.icon}</div>
            <div className="nameplate">
              <strong>{a.label}</strong>
              <small>{a.role}</small>
            </div>
            <div className="seat-status">
              <span className="lamp" aria-hidden="true" />
              {s.state === 'idle' && 'Off this ticket'}
              {s.state === 'working' && (speaking === name ? 'Talking now…' : 'Working…')}
              {s.state === 'done' && 'Done'}
              {s.state === 'error' && 'Stopped'}
            </div>
            {lastTool && (
              <div className="seat-tool" title={lastTool.result}>
                {lastTool.ok ? '↳' : '⚠'} {TOOL_LABEL[lastTool.name] ?? lastTool.name}
              </div>
            )}
          </div>
        )
      })}
    </section>
  )
}
