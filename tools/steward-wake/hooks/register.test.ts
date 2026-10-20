// The wake's title gate under `claude plugin test` (#915, lab-only).
//
// The test's own hooks stand beneath the mod for every `$` noun it uses: the
// script (`process.run`), the session tools, the permission check and the
// status line. The script's answers are fixtures; the script itself is tested
// by tools/tests/test_steward_watch.py, and the gate's shape statically there.
import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const GET = 'mcp__ccd_session_mgmt__get_session'
const ROOT = 'D:/Code/steward-checkout'
const TURN = { turnId: 't1' } as any
const TURN_DONE = { answer: '', durationMs: 1, isAborted: false, turnId: 't1', reason: 'answer' } as any

type World = {
  title?: string
  check?: 'allow' | 'ask' | 'deny'
  listed?: boolean
  throws?: boolean
  text?: string
  lateMs?: number
}

const CONFIG = {
  schema_version: 1, state_dir: 'S', default_state_dir: true, page: 683, tick_seconds: 300,
  handover_tokens: 250000, owner_quiet_seconds: 3600, settle_seconds: 60, simulate_clear_refused: false,
}

function world(on: On, w: World) {
  const seen = {
    runs: [] as string[], reads: 0, readsDone: 0, calls: 0, statuses: [] as Array<string | undefined>,
    prompts: [] as string[],
  }
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.end', () => ({ sessionId: 'sid-1' }) as any)
  on('turn.start', ($, e) => ({ turnId: (e as any).turnId ?? 't1' }) as any)
  on('turn.complete', () => ({ text: '' }) as any)
  on('classic.Stop', () => ({}) as any)
  const clock = mock.clock(on, { now: 1_800_000_000_000 })
  on('session.id', () => ({ value: 'sid-1' }))
  on('session.root', () => ({ value: ROOT }))
  on('session.usage', () => ({ value: { context: { tokens: 1000 } } }) as any)
  on('agent.list', () => ({ value: [] }) as any)
  on('env.get', () => ({ value: undefined }) as any)
  on('tool.list', () => ({
    value: (w.listed === false ? ['Bash'] : [GET, 'Bash']).map(name => ({ name, description: name, isMcp: name !== 'Bash' })),
  }) as any)
  on('tool.check', () => ({ decision: w.check ?? 'allow' }))
  on('tool.call', { tool: GET }, async () => {
    seen.reads += 1
    if (w.lateMs) await clock.sleep(w.lateMs)
    seen.readsDone += 1
    if (w.throws) throw new Error('session tool failed')
    seen.calls += 1
    const text = w.text ?? `Session self:\n${JSON.stringify({ id: 'sid-1', title: w.title ?? 'Start 888', titleSource: 'auto' })}`
    return { result: [], text } as any
  })
  on('ui.status', ($, e) => {
    seen.statuses.push(e.text)
    return { value: undefined } as any
  })
  on('prompt.submit', ($, e) => {
    seen.prompts.push(String((e as any).text ?? ''))
    return { text: (e as any).text ?? '' } as any
  })
  on('process.run', async ($, e) => {
    const command = String(e.argv[2])
    seen.runs.push(command)
    const answers: Record<string, unknown> = {
      config: CONFIG,
      'handover-step': { schema_version: 1, state: 'idle', action: 'none' },
      wake: { schema_version: 1, triggers: [], cover: {} },
      'handover-due': { schema_version: 1, due: false, blocking: ['tokens'] },
      'origin-is-owner': { schema_version: 1, owner: true },
    }
    return { value: { exitCode: 0, stdout: JSON.stringify(answers[command] ?? { schema_version: 1 }), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  return Object.assign(seen, { clock })
}

async function everything($: any, seen: ReturnType<typeof world>) {
  await $.session.start({ cwd: ROOT, surface: null } as any)
  await $.turn.start(TURN)
  await $.turn.complete(TURN_DONE)
  await $.turn.start(TURN)
  await $.prompt.submit({ text: 'hello', origin: { kind: 'typed' } } as any)
  await $.classic.Stop({ stop_hook_active: false } as any)
  await $.session.end({ reason: 'clear' } as any)
  await seen.clock.settle()
  await seen.clock.advance(300_000)
  await seen.clock.advance(61_000)
  await seen.clock.settle()
}

// C3.1
test('a session titled anything but Steward runs no process and draws nothing', async ($, on) => {
  const seen = world(on, { title: 'Start 888' })
  await everything($, seen)
  expect(seen.runs).toEqual([])
  expect(seen.statuses).toEqual([])
  expect(seen.prompts).toEqual(['hello'])
  expect(seen.reads).toBeGreaterThan(0)
})

// C3.2
for (const title of ['Steward', '  steward ']) {
  test(`a session titled ${JSON.stringify(title)} starts the wake`, async ($, on) => {
    const seen = world(on, { title })
    await $.session.start({ cwd: ROOT, surface: null } as any)
    expect(seen.runs[0]).toBe('config')
    const last = String(seen.statuses.at(-1))
    expect(last).toContain('steward-wake on')
    expect(last).toContain(ROOT)
    await seen.clock.advance(300_000)
    expect(seen.runs).toContain('wake')
  })
}

// C3.3
test('a session renamed Steward wakes from its next turn and then stops reading', async ($, on) => {
  const w: World = { title: 'Start 915' }
  const seen = world(on, w)
  await $.session.start({ cwd: ROOT, surface: null } as any)
  expect(seen.runs).toEqual([])
  w.title = 'Steward'
  await $.turn.start(TURN)
  await seen.clock.settle()
  expect(seen.runs.filter(command => command === 'config').length).toBe(1)
  const reads = seen.reads
  await $.turn.complete(TURN_DONE)
  await $.turn.start(TURN)
  await seen.clock.settle()
  expect(seen.reads).toBe(reads)
  expect(seen.runs.filter(command => command === 'config').length).toBe(1)
})

// C3.4
const failures: Array<[string, World, string, boolean]> = [
  ['get_session absent', { listed: false }, '(absent)', false],
  ['the check answering ask', { check: 'ask' }, '(ask)', false],
  ['the check answering deny', { check: 'deny' }, '(deny)', false],
  ['the call throwing', { throws: true }, '(failed)', true],
  ['an answer with no title', { text: 'Session self: {"id": "sid-1"}' }, '(no title)', true],
]
for (const [name, w, reason, called] of failures) {
  test(`${name} leaves the wake off and says why`, async ($, on) => {
    const seen = world(on, { title: 'Steward', ...w })
    await $.session.start({ cwd: ROOT, surface: null } as any)
    await $.turn.start(TURN)
    await seen.clock.settle()
    await seen.clock.advance(300_000)
    expect(seen.runs).toEqual([])
    const last = String(seen.statuses.at(-1))
    expect(last).toContain('steward-wake off')
    expect(last).toContain(reason)
    if (!called) expect(seen.reads).toBe(0)
  })
}

test('a later readable title clears the unreadable line', async ($, on) => {
  const w: World = { title: 'Start 888', check: 'ask' }
  const seen = world(on, w)
  await $.session.start({ cwd: ROOT, surface: null } as any)
  expect(String(seen.statuses.at(-1))).toContain('(ask)')
  w.check = 'allow'
  await $.turn.start(TURN)
  await seen.clock.settle()
  expect(seen.statuses.at(-1)).toBeUndefined()
  expect(seen.runs).toEqual([])
})

// C3.5
test("a holder's turn does not wait on the title read", async ($, on) => {
  const w: World = { title: 'Start 888' }
  const seen = world(on, w)
  await $.session.start({ cwd: ROOT, surface: null } as any)
  w.lateMs = 60_000
  const before = seen.readsDone
  await $.turn.start(TURN)
  await seen.clock.settle()
  expect(seen.reads).toBe(before + 1)
  expect(seen.readsDone).toBe(before)
  // One read at a time: a second turn while the first read waits starts none.
  await $.turn.start(TURN)
  await seen.clock.settle()
  expect(seen.reads).toBe(before + 1)
  await seen.clock.advance(60_000)
  await seen.clock.settle()
  expect(seen.readsDone).toBe(before + 1)
})

// C3.6
test("the handover's in-place clear does not turn the wake off", async ($, on) => {
  const w: World = { title: 'Steward' }
  const seen = world(on, w)
  await $.session.start({ cwd: ROOT, surface: null } as any)
  expect(seen.runs.filter(command => command === 'config').length).toBe(1)
  const reads = seen.reads
  w.throws = true
  await $.session.end({ reason: 'clear' } as any)
  await $.session.start({ cwd: ROOT, surface: null } as any)
  await seen.clock.settle()
  expect(seen.reads).toBe(reads)
  expect(seen.runs.filter(command => command === 'config').length).toBe(1)
  const wakes = seen.runs.filter(command => command === 'wake').length
  await seen.clock.advance(300_000)
  expect(seen.runs.filter(command => command === 'wake').length).toBeGreaterThan(wakes)
})
