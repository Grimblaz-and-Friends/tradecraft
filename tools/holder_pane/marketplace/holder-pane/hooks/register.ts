// The holder pane's hooks module: a shim over core/holder_pane.py (#888, lab-only).
//
// Every decision is the core's. This module watches the holder's own shell
// calls, reads the session's title through the desktop app's session tools,
// runs the core, and draws what it answers in a pane, the status line and the
// sidebar name. A session that holds no change gets nothing: before it binds,
// its only work on a tool call is the in-memory test below.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, RenderElement } from 'claude-code'
import type { HolderPaneFloor as Floor, HolderPaneView } from '../types/index'

type View = HolderPaneView

const PANE = 'holder-pane'
const GET = 'mcp__ccd_session_mgmt__get_session'
const SET = 'mcp__ccd_session_mgmt__set_session_title'
const SEP = ' · '
const TICK_MS = 60_000
const CORE_TIMEOUT_MS = 30_000
const READ_TIMEOUT_MS = 600_000
const SHELLS = new Set(['Bash', 'PowerShell'])
// Mirrors the core's parse: `run <stage>` or `adopt` with --repo and --issue.
const BINDS = /(?:^|\s)(?:run\s+(?:artifact|cold-seat|build|floor|use|review-disposition|proof|ready-reviewers|release-report|catch-up)|adopt)(?=\s|$)[\s\S]*--repo[\s=][\s\S]*--issue[\s=]/
const RELEVANT = /(?:^|\s)(?:run|adopt)(?=\s|$)|(?:^|[\s;&|(])gh\s+(?:pr|api)\s/
const view = atom({ plugin: 'holder-pane', key: 'view' } as const, null)

type $ = EngineInterface
type TitleProbe = { decision: string; text: string | null }

let bound = false
let initialized = false
let stopped = false
let timer: { cancel: () => void } | undefined

async function core($: $, command: string, payload: object, timeoutMs = CORE_TIMEOUT_MS): Promise<any> {
  const script = `${$.plugin.root}/core/holder_pane.py`
  const ran = await $.process.run(['python', script, command], {
    stdin: JSON.stringify(payload),
    timeoutMs,
  })
  if (ran.exitCode !== 0) throw new Error(`holder-pane core ${command} exited ${ran.exitCode}`)
  return JSON.parse(ran.stdout)
}

// Every call to either session tool goes through here: it runs only when
// Claude Code's own permission decision for that exact input is `allow`, so
// the mod never puts a prompt in front of the owner, in any mode.
async function sessionTool($: $, tool: string, input: Record<string, unknown>) {
  const listed = (await $.tool.list()).some(one => one.name === tool)
  if (!listed) return { decision: 'absent' as const }
  const { decision } = await $.tool.check({ tool, input })
  if (decision !== 'allow') return { decision }
  const ran: any = await $.tool.call({ tool, ...input } as any)
  return { decision, ran }
}

async function readTitle($: $): Promise<TitleProbe> {
  try {
    const answer = await sessionTool($, GET, { session_id: 'self' })
    if (answer.decision !== 'allow') return { decision: answer.decision, text: null }
    const ran: any = (answer as any).ran
    return { decision: 'allow', text: typeof ran?.text === 'string' ? ran.text : null }
  } catch {
    return { decision: 'failed', text: null }
  }
}

export function formatDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest === 0 ? `${hours}h` : `${hours}h${String(rest).padStart(2, '0')}m`
}

function floorText(floor: Floor): string {
  if (!floor.outcome) return '—'
  if (floor.satisfied === null) return floor.outcome
  return `${floor.outcome} ${floor.satisfied ? '✓' : '✗'}`
}

function runningText(v: View): string | undefined {
  const r = v.running
  if (!r) return undefined
  const deadline = r.deadline === null ? '?' : formatDuration(r.deadline)
  if (r.stalled) return `STALLED ${formatDuration(r.elapsed)}/${deadline}`
  return `${v.stage} running ${formatDuration(r.elapsed)}/${deadline}`
}

export function statusLine(v: View): string {
  const parts = [`#${v.issue}`]
  const running = runningText(v)
  if (running) {
    parts.push(running)
    if (!v.running?.stalled) parts.push(`quiet ${formatDuration(v.running?.quiet ?? 0)}`)
  } else {
    parts.push(v.label)
  }
  parts.push(`next: ${v.next_step} (${v.waiting_on})`)
  parts.push(`gate ${v.gate}`)
  parts.push(`floor ${floorText(v.floor)}`)
  parts.push(`read ${v.read_at_local ?? '—'}`)
  if (v.read_failed_local) parts.push(`read failed ${v.read_failed_local}`)
  return parts.join(SEP)
}

export function paneRows(v: View): Array<[string, string]> {
  const rows: Array<[string, string]> = [
    ['stage', v.stage || '—'],
    ['waiting on', v.waiting_on || '—'],
    ['next step', v.next_step || '—'],
    ['gate', v.gate || '—'],
    ['floor', floorText(v.floor)],
  ]
  if (v.running) {
    const deadline = v.running.deadline === null ? '?' : formatDuration(v.running.deadline)
    rows.push(['elapsed', `${formatDuration(v.running.elapsed)}/${deadline}${v.running.stalled ? ' STALLED' : ''}`])
    rows.push(['quiet', `quiet for ${Math.floor(v.running.quiet / 60)} min`])
  }
  rows.push(['read', `${v.read_at_local ?? '—'} (${v.source ?? '—'})`])
  if (v.rename_note) rows.push(['name', v.rename_note])
  if (v.read_failed_local) rows.push(['read failed', v.read_failed_local])
  return rows
}

async function rename($: $, label: string, issue: number) {
  const title = `#${issue}${SEP}${label}`
  let outcome = 'failed'
  try {
    // A fresh title read immediately before the call (section 5's rule).
    const probe = await readTitle($)
    if (probe.decision !== 'allow') return
    const answer = await sessionTool($, SET, { session_id: 'self', title })
    if (answer.decision === 'absent') outcome = 'no-tool'
    else if (answer.decision !== 'allow') outcome = 'would-prompt'
    else outcome = (answer as any).ran?.isError ? 'failed' : 'renamed'
  } catch {
    outcome = 'failed'
  }
  await core($, 'renamed', { session_id: await $.session.id(), label, title, outcome })
}

async function refresh($: $) {
  if (!bound) return
  const sessionId = await $.session.id()
  const title = await readTitle($)
  const answer = await core($, 'tick', { session_id: sessionId, title })
  if (!answer.bound) {
    bound = false
    stopTimer()
    await update($, view, () => null)
    $.ui.status(undefined)
    return
  }
  await update($, view, () => answer.view as View)
  $.ui.status(statusLine(answer.view as View))
  if (answer.rename) await rename($, answer.rename.label, (answer.view as View).issue)
  if (answer.stopped) {
    stopped = true
    stopTimer()
  }
}

function stopTimer() {
  timer?.cancel()
  timer = undefined
}

async function requestRead($: $) {
  if (!bound || stopped) return
  const sessionId = await $.session.id()
  // In the background: the core's floor and lock decide whether anything runs.
  void core($, 'read', { session_id: sessionId }, READ_TIMEOUT_MS)
    .then(answer => (answer.ran ? refresh($) : undefined))
    .catch(() => undefined)
}

function arm($: $) {
  if (timer || !bound || stopped) return
  timer = $.clock.every(TICK_MS, () => {
    void refresh($).catch(() => undefined)
    void requestRead($)
  })
}

async function becameBound($: $) {
  bound = true
  stopped = false
  arm($)
  await refresh($)
  const current = await read($, view)
  if (current) void $.ui.open({ id: PANE, title: `#${current.issue}` })
  void requestRead($)
}

async function initialize($: $) {
  if (initialized) return
  initialized = true
  const sessionId = await $.session.id()
  const answer = await core($, 'recover', { session_id: sessionId, root: await $.session.root() })
  if (!answer.candidate) return
  const title = await readTitle($)
  const bindAnswer = await core($, 'bind', { session_id: sessionId, binding: answer.candidate, title })
  if (bindAnswer.bound) await becameBound($)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.command.register({ name: 'holder-pane', description: 'Reopen the holder pane' })
    await initialize($).catch(() => undefined)
    return started
  })

  on('command.run', { command: 'holder-pane' }, async $ => {
    if (!bound) return { text: 'This session holds no change.' }
    const current = await read($, view)
    await $.ui.open({ id: PANE, title: current ? `#${current.issue}` : 'holder' })
    return { text: 'Holder pane opened.' }
  })

  on('tool.call', async ($, e, next) => {
    const tool = String(e.tool)
    const command = SHELLS.has(tool) ? String((e as any).command ?? '') : ''
    const binds = command !== '' && BINDS.test(command)
    if (!binds && !(bound && command !== '' && RELEVANT.test(command))) return next(e)
    const startedAt = (await $.clock.now()) / 1000
    const ran = await next(e)
    try {
      await initialize($)
      const sessionId = await $.session.id()
      const title = binds ? await readTitle($) : undefined
      const output = typeof (ran as any).text === 'string' ? (ran as any).text : ''
      const answer = await core($, 'observe', {
        session_id: sessionId,
        command,
        output,
        started_at: startedAt,
        ended_at: (await $.clock.now()) / 1000,
        title,
      })
      if (answer.bound && !bound) await becameBound($)
      else if (!answer.bound && bound) {
        bound = false
        stopTimer()
        await update($, view, () => null)
        $.ui.status(undefined)
      } else if (bound) await refresh($)
    } catch {
      // A failed observation never changes the call's own result.
    }
    return ran
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (bound && !stopped) {
      arm($)
      void requestRead($)
    }
    return done
  })

  // The reminder (row 6): once per distinct next step of the holder's own,
  // never while a Stop re-prompt is already active, never a turn of its own.
  on('classic.Stop', async ($, e, next) => {
    const result = await next(e)
    if (!bound) return result
    const answer = await core($, 'remind', {
      session_id: await $.session.id(),
      stop_hook_active: Boolean((e as any).stop_hook_active),
    })
    return answer.block ? { ...result, block: answer.block } : result
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const current = await read($, view)
    if (!current) {
      return h(Box, { flexDirection: 'column' }, h(Text, { dimColor: true }, 'This session holds no change.')) as RenderElement
    }
    const rows = paneRows(current).map(([name, value]) =>
      h(Text, { key: name }, h(Text, { dimColor: true }, `${name}: `), value),
    )
    return h(Box, { flexDirection: 'column' }, h(Text, { bold: true }, `#${current.issue}${SEP}${current.label}`), ...rows) as RenderElement
  })
}
