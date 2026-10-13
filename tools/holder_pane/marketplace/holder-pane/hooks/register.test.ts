// The shim's behaviours under `claude plugin test` (#888, lab-only).
//
// The test's own hooks stand beneath the plugin for every `$` noun it uses:
// the core (`process.run`), the session tools, the permission check, the pane
// and the status line. The core's answers here are fixtures; the core itself
// is tested by tools/holder_pane/tests.
import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const GET = 'mcp__ccd_session_mgmt__get_session'
const SET = 'mcp__ccd_session_mgmt__set_session_title'
const RUN = 'python launch_stage.py b1 -- run build --repo Grimblaz-and-Friends/tradecraft --issue 888 --root D:/r'

const VIEW = {
  issue: 888, stage: 'build', label: 'build running', waiting_on: 'builder',
  next_step: 'wait for the build run', gate: 'not reached',
  floor: { outcome: 'ci-met', satisfied: true },
  running: { stage: 'build', elapsed: 2460, deadline: 7200, quiet: 360, stalled: false },
  source: 'stage-return', read_at_local: '14:02', record_pending: false, final: null,
}

type World = {
  title?: string
  checks?: Record<string, 'allow' | 'ask' | 'deny'>
  bound?: boolean
  block?: string | null
}

function world(on: On, w: World) {
  const seen = { core: [] as string[], calls: [] as string[], opened: 0, statuses: [] as Array<string | undefined> }
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('turn.complete', ($, e) => ({ text: '' }) as any)
  on('classic.Stop', () => ({}) as any)
  mock.clock(on, { now: 1_800_000_000_000 })
  on('command.register', ($, e) => ({ value: { command: e.name } }) as any)
  on('session.id', () => ({ value: 'sid-1' }))
  on('session.root', () => ({ value: 'D:/root' }))
  on('tool.list', () => ({ value: [GET, SET, 'Bash'].map(name => ({ name, description: name, isMcp: name !== 'Bash' })) }) as any)
  on('tool.check', ($, e) => ({ decision: w.checks?.[e.tool] ?? 'allow' }))
  on('tool.call', { tool: GET }, () => {
    seen.calls.push(GET)
    return { result: [], text: JSON.stringify({ title: w.title ?? 'Start 888' }) } as any
  })
  on('tool.call', { tool: SET }, () => {
    seen.calls.push(SET)
    return { result: [], text: 'Renamed' } as any
  })
  on('tool.call', { tool: 'Bash' }, () => ({ result: {}, text: '12345' }) as any)
  on('ui.open', () => {
    seen.opened += 1
    return { value: { isPlaced: true } } as any
  })
  on('ui.status', ($, e) => {
    seen.statuses.push(e.text)
    return { value: undefined } as any
  })
  on('process.run', ($, e) => {
    const command = String(e.argv[2])
    seen.core.push(command)
    const answers: Record<string, unknown> = {
      recover: { candidate: null },
      observe: w.bound === false || (w.title ?? '').toLowerCase() === 'steward' ? { bound: false } : { bound: true },
      tick: { bound: true, view: VIEW, rename: { label: 'build running' }, stopped: false },
      renamed: { bound: true },
      read: { ran: false, why: 'floor' },
      remind: { block: w.block ?? null },
    }
    return { value: { exitCode: 0, stdout: JSON.stringify(answers[command] ?? {}), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  return seen
}

test('a session holding no change draws, renames and reads nothing', async ($, on) => {
  const seen = world(on, { bound: false })
  await $.session.start({ cwd: 'D:/root', surface: null } as any)
  await $.turn.complete({ reason: 'answer', text: '' } as any)
  await $.classic.Stop({ stop_hook_active: false } as any)
  await $.tool.call({ tool: 'Bash', command: 'git status' } as any)
  expect(seen.opened).toBe(0)
  expect(seen.statuses).toEqual([])
  expect(seen.calls).toEqual([])
  expect(seen.core).toEqual(['recover'])
})

test('a session titled Steward never binds and is never renamed', async ($, on) => {
  const seen = world(on, { title: 'Steward' })
  await $.session.start({ cwd: 'D:/root', surface: null } as any)
  await $.tool.call({ tool: 'Bash', command: RUN } as any)
  expect(seen.opened).toBe(0)
  expect(seen.calls.includes(SET)).toBe(false)
})

test('a holder binds at run, draws, and renames only behind an allow', async ($, on) => {
  const seen = world(on, {})
  await $.session.start({ cwd: 'D:/root', surface: null } as any)
  await $.tool.call({ tool: 'Bash', command: RUN } as any)
  expect(seen.core).toContain('observe')
  expect(seen.opened).toBe(1)
  expect(seen.statuses.at(-1)).toContain('#888')
  expect(seen.calls).toContain(SET)
})

test('get_session answering ask is never called, and nothing is renamed', async ($, on) => {
  const seen = world(on, { checks: { [GET]: 'ask' } })
  await $.session.start({ cwd: 'D:/root', surface: null } as any)
  await $.tool.call({ tool: 'Bash', command: RUN } as any)
  expect(seen.opened).toBe(1)
  expect(seen.calls).toEqual([])
})

test('set_session_title answering ask is never called', async ($, on) => {
  const seen = world(on, { checks: { [SET]: 'deny' } })
  await $.session.start({ cwd: 'D:/root', surface: null } as any)
  await $.tool.call({ tool: 'Bash', command: RUN } as any)
  expect(seen.calls.includes(SET)).toBe(false)
  expect(seen.core).toContain('renamed')
})

test('the reminder is the Stop re-prompt the core answers', async ($, on) => {
  world(on, { block: 'next: post the release report (yours)' })
  await $.session.start({ cwd: 'D:/root', surface: null } as any)
  await $.tool.call({ tool: 'Bash', command: RUN } as any)
  const answer = await $.classic.Stop({ stop_hook_active: false } as any)
  expect(answer.block).toBe('next: post the release report (yours)')
})

test('the pane shows every field on terminal and desktop', async ($, on) => {
  world(on, {})
  await $.session.start({ cwd: 'D:/root', surface: null } as any)
  await $.tool.call({ tool: 'Bash', command: RUN } as any)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'holder-pane', surface, component: 'Pane', requestId: 'holder-pane', props: {} } as any)
    for (const text of ['stage', 'waiting on', 'next step', 'gate', 'floor', 'elapsed', 'quiet for 6 min', 'read', '14:02']) {
      expect(await ui.find({ text })).toBeDefined()
    }
    await ui.unmount()
  }
})
