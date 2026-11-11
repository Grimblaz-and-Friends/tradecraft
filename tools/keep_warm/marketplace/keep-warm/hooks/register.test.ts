// The keep-warm module's wiring under `claude plugin test` (#983, lab-only).
//
// The test's own hooks stand beneath the module for every `$` noun it uses:
// the core (`process.run`), the prompt it submits, the session's usage and a
// tool the model calls. The core's answers here are fixtures; the core itself
// is tested by tools/tests/test_keep_warm_desktop.py.
import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const TURN = { turnId: 't1', text: '' } as any
const TURN_DONE = { answer: '', durationMs: 1, isAborted: false, turnId: 't1', reason: 'answer' } as any
const TEXT = "[tradecraft keep-warm] This turn is the practice's keep-warm, not the owner speaking. Answer with one word and use no tools."
const TICK_MS = 60_000

type World = { inert?: boolean; submit?: boolean; env?: Record<string, string> }

function world(on: On, w: World) {
  const seen = { core: [] as string[], argv: [] as string[][], prompts: [] as string[], ran: [] as string[] }
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('turn.start', ($, e) => ({ turnId: (e as any).turnId ?? 't1' }) as any)
  on('turn.complete', () => ({ text: '' }) as any)
  const clock = mock.clock(on, { now: 1_800_000_000_000 })
  on('session.id', () => ({ value: 'sid-1' }))
  on('session.root', () => ({ value: 'D:/Code/practice-checkout' }))
  on('session.usage', () => ({ value: { context: { tokens: 120_000, window: 1_000_000 } } }) as any)
  on('env.get', ($, e) => ({ value: w.env?.[(e as any).name] }) as any)
  on('prompt.submit', ($, e) => {
    seen.prompts.push(String((e as any).text ?? ''))
    return { text: (e as any).text ?? '' } as any
  })
  on('tool.call', { tool: 'Bash' }, ($, e) => {
    seen.ran.push(String((e as any).command))
    return { result: {}, text: 'ok' } as any
  })
  on('process.run', async ($, e) => {
    const argv = (e.argv as string[]).map(String)
    seen.core.push(argv[2])
    seen.argv.push(argv)
    const answers: Record<string, unknown> = {
      load: { inert: w.inert ?? false, tick_seconds: 60, interval_seconds: 3300, lapse_seconds: 3420, cap_seconds: 28800 },
      due: w.submit === false ? { submit: false, reason: 'not-yet' } : { submit: true, text: TEXT },
      submitted: { turn_open: true, count: 1 },
      'turn-end': { own: false, fault: null, stopped: null },
      fault: { logged: true },
    }
    return { value: { exitCode: 0, stdout: JSON.stringify(answers[argv[2]] ?? {}), stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  return Object.assign(seen, { clock })
}

async function ticks(seen: ReturnType<typeof world>, count: number) {
  for (let i = 0; i < count; i++) await seen.clock.advance(TICK_MS)
  await seen.clock.settle()
}

function count(seen: ReturnType<typeof world>, command: string): number {
  return seen.core.filter(one => one === command).length
}

function ownFlags(seen: ReturnType<typeof world>): string[] {
  return seen.argv.filter(argv => argv[2] === 'turn-end').map(argv => argv[argv.indexOf('--own') + 1])
}

test('a session outside a practice repository only loads', async ($, on) => {
  const seen = world(on, { inert: true })
  await $.session.start({ cwd: 'D:/Code/other', surface: null } as any)
  await ticks(seen, 120)
  await $.turn.start(TURN)
  await $.turn.complete(TURN_DONE)
  await ticks(seen, 5)
  expect(seen.core).toEqual(['load'])
  expect(seen.prompts).toEqual([])
})

// AC38
test('no keep-warm turn is submitted while a turn is running', async ($, on) => {
  const seen = world(on, {})
  await $.session.start({ cwd: 'D:/Code/practice-checkout', surface: null } as any)
  await $.turn.start(TURN)
  await ticks(seen, 90)
  expect(seen.prompts).toEqual([])
  expect(count(seen, 'due')).toBe(0)
  await $.turn.complete(TURN_DONE)
  await ticks(seen, 1)
  expect(seen.prompts).toEqual([TEXT])
  expect(count(seen, 'submitted')).toBe(1)
})

// AC38
test('no keep-warm turn is submitted while an own submission is pending', async ($, on) => {
  const seen = world(on, {})
  await $.session.start({ cwd: 'D:/Code/practice-checkout', surface: null } as any)
  await ticks(seen, 30)
  expect(seen.prompts).toEqual([TEXT])
  expect(count(seen, 'due')).toBe(1)
  expect(count(seen, 'submitted')).toBe(1)
})

// AC32, under 4.4's branch: the mod API's `tool.call` guard refuses the model's call.
test("a tool call in a keep-warm turn is refused and the turn is checked as the keep-warm's", async ($, on) => {
  const w: World = {}
  const seen = world(on, w)
  await $.session.start({ cwd: 'D:/Code/practice-checkout', surface: null } as any)
  await ticks(seen, 1)
  expect(seen.prompts).toEqual([TEXT])
  w.submit = false
  await $.turn.start(TURN)
  const refused: any = await $.tool.call({ tool: 'Bash', command: 'git status' } as any)
  expect(seen.ran).toEqual([])
  // The guard's own refusal (the test's call reaches it as the engine's), not its .catch.
  expect(String(refused.text ?? refused.deny)).toContain('not the owner; answer with one word and use no tools')
  await $.turn.complete(TURN_DONE)
  await ticks(seen, 1)
  expect(ownFlags(seen)).toEqual(['1'])
  // The next turn is a real one: its tool calls run, and it is recorded as real.
  await $.turn.start(TURN)
  await $.tool.call({ tool: 'Bash', command: 'git log -1' } as any)
  expect(seen.ran).toEqual(['git log -1'])
  await $.turn.complete(TURN_DONE)
  await seen.clock.advance(10_000)
  await seen.clock.settle()
  expect(ownFlags(seen)).toEqual(['1', '0'])
})

test('a real turn with nothing submitted runs its tools and ends as real', async ($, on) => {
  const seen = world(on, { submit: false })
  await $.session.start({ cwd: 'D:/Code/practice-checkout', surface: null } as any)
  await $.turn.start(TURN)
  await $.tool.call({ tool: 'Bash', command: 'ls' } as any)
  await $.turn.complete(TURN_DONE)
  await seen.clock.advance(10_000)
  await seen.clock.settle()
  expect(seen.ran).toEqual(['ls'])
  expect(ownFlags(seen)).toEqual(['0'])
  expect(seen.prompts).toEqual([])
})

test('a subagent turn neither starts nor ends the main turn', async ($, on) => {
  const seen = world(on, {})
  await $.session.start({ cwd: 'D:/Code/practice-checkout', surface: null } as any)
  await $.turn.start(TURN)
  await $.turn.start({ turnId: 't2', text: 'sub', agentId: 'a1' } as any)
  await $.turn.complete({ ...TURN_DONE, turnId: 't2', agentId: 'a1' })
  await ticks(seen, 3)
  expect(seen.prompts).toEqual([])
})

test('the state directory and probe timings reach every core call', async ($, on) => {
  const seen = world(on, {
    submit: false,
    env: { KEEP_WARM_LAB_STATE_DIR: 'D:/probe/keep-warm', KEEP_WARM_DESKTOP_INTERVAL_SECONDS: '120' },
  })
  await $.session.start({ cwd: 'D:/Code/practice-checkout', surface: null } as any)
  await ticks(seen, 1)
  expect(seen.argv.length).toBeGreaterThan(1)
  for (const argv of seen.argv) {
    expect(argv.join(' ')).toContain('--state-dir D:/probe/keep-warm')
    expect(argv.join(' ')).toContain('--env KEEP_WARM_DESKTOP_INTERVAL_SECONDS=120')
    expect(argv.join(' ')).toContain('--session sid-1')
  }
})
