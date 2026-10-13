// steward-wake: the Steward's wake and handover (tradecraft #890).
//
// Only wiring lives here. Every decision -- what counts as intake, when a read
// is due, what has already woken the Steward, whether a handover may start,
// what each prompt says -- is made by tools/steward_watch.py in the Steward's
// checkout, where CI tests it. This module runs timers, observes the session,
// calls that script, and submits or runs what it prints. It never calls a
// model, never writes a file and never uses the mod store: all local state is
// written by the script, under the state directory it resolves.

const SCRIPT = 'tools/steward_watch.py'
const PROBE_ENV = [
  'STEWARD_WAKE_TICK_SECONDS',
  'STEWARD_WAKE_HANDOVER_TOKENS',
  'STEWARD_WAKE_OWNER_QUIET_SECONDS',
  'STEWARD_WAKE_SETTLE_SECONDS',
  'STEWARD_WAKE_SIMULATE_CLEAR_REFUSED',
  'STEWARD_WAKE_PAGE',
]
const PRODUCTION = { handover_tokens: 250000, owner_quiet_seconds: 3600, settle_seconds: 60 }
const BUSY = new Set(['pending', 'running', 'waiting'])
const BACKSLASH = String.fromCharCode(92)

const state = {
  host: null,
  root: null,
  python: 'python',
  stateDir: null,
  cfg: null,
  started: false,
  ticking: false,
  turnRunning: false,
  lastTurnComplete: Date.now(),
  lastTurnStart: null,
  ownerAt: Date.now(),
  stop: { background_tasks: [], session_crons: [] },
  coverNote: null,
  timers: [],
}

// The engine as `session.start` bound it: every later call goes through these,
// each spelling its engine call at its own site.
function hostOf($) {
  return {
    run: (argv, options) => $.process.run(argv, options),
    submit: text => $.prompt.submit({ text }),
    command: name => $.command.run({ command: name }),
    status: text => $.ui.status(text),
    usage: () => $.session.usage(),
    agents: () => $.agent.list(),
    // Each variable is named literally, so validation lists what the mod reads.
    env: async () => ({
      STEWARD_WAKE_PYTHON: await $.env.get('STEWARD_WAKE_PYTHON'),
      STEWARD_LAB_STATE_DIR: await $.env.get('STEWARD_LAB_STATE_DIR'),
      STEWARD_WAKE_TICK_SECONDS: await $.env.get('STEWARD_WAKE_TICK_SECONDS'),
      STEWARD_WAKE_HANDOVER_TOKENS: await $.env.get('STEWARD_WAKE_HANDOVER_TOKENS'),
      STEWARD_WAKE_OWNER_QUIET_SECONDS: await $.env.get('STEWARD_WAKE_OWNER_QUIET_SECONDS'),
      STEWARD_WAKE_SETTLE_SECONDS: await $.env.get('STEWARD_WAKE_SETTLE_SECONDS'),
      STEWARD_WAKE_SIMULATE_CLEAR_REFUSED: await $.env.get('STEWARD_WAKE_SIMULATE_CLEAR_REFUSED'),
      STEWARD_WAKE_PAGE: await $.env.get('STEWARD_WAKE_PAGE'),
    }),
    sessionId: () => $.session.id(),
    root: () => $.session.root(),
    every: (ms, fn) => $.clock.every(ms, fn),
    after: (ms, fn) => $.clock.after(ms, fn),
  }
}

function iso(ms) {
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, 'Z')
}

function message(err) {
  return String((err && err.message) || err)
}

async function script(args, allowError = false) {
  const argv = [state.python, state.root + '/' + SCRIPT, ...args]
  if (state.stateDir) argv.push('--state-dir', state.stateDir)
  if (state.cfg && state.cfg.page !== 683) argv.push('--page', String(state.cfg.page))
  const result = await state.host.run(argv, { timeout: 120000, cwd: state.root })
  let value = null
  try {
    value = JSON.parse(String(result.stdout || '').trim().split('\n').pop())
  } catch (err) {
    value = null
  }
  if (value === null || (result.exitCode !== 0 && !(allowError && value.schema_version))) {
    const why = (value && value.error) || String(result.stderr || '').trim().split('\n').pop() || 'no output'
    throw new Error(args[0] + ': ' + why)
  }
  return value
}

function status(text) {
  try {
    state.host.status(text)
  } catch (err) {
    // A status line is a courtesy; failing to draw one stops nothing.
  }
}

// Probe-only overrides are passed only when they differ from production, and
// the script refuses them against the default state directory.
function probeFlags() {
  const flags = []
  const cfg = state.cfg
  if (cfg.handover_tokens !== PRODUCTION.handover_tokens) flags.push('--handover-tokens', String(cfg.handover_tokens))
  if (cfg.owner_quiet_seconds !== PRODUCTION.owner_quiet_seconds) flags.push('--owner-quiet-seconds', String(cfg.owner_quiet_seconds))
  if (cfg.settle_seconds !== PRODUCTION.settle_seconds) flags.push('--settle-seconds', String(cfg.settle_seconds))
  return flags
}

async function act(step) {
  if (step.status) status(step.status)
  if (step.action === 'submit') {
    await state.host.submit(step.text)
  } else if (step.action === 'clear') {
    await clear()
  }
  return step
}

// Every step carries the turn facts, so the script returns a clear only at a
// quiet moment: no turn running and the settle period passed.
async function handoverStep(event, extra = []) {
  const facts = [
    '--turn-running', state.turnRunning ? '1' : '0',
    '--since-turn-complete', String((Date.now() - state.lastTurnComplete) / 1000),
  ]
  if (state.cfg.settle_seconds !== PRODUCTION.settle_seconds) facts.push('--settle-seconds', String(state.cfg.settle_seconds))
  return act(await script(['handover-step', '--event', event, '--session', String(await state.host.sessionId()), ...facts, ...extra]))
}

// Called only from timer callbacks, never from a hook a turn is waiting on.
async function clear() {
  if (state.cfg.simulate_clear_refused) {
    await handoverStep('clear-rejected', ['--reason', 'simulated refusal (probe)'])
    return
  }
  state.timers.push(state.host.after(125000, () => guarded(() => handoverStep('tick'))))
  try {
    await state.host.command('clear')
  } catch (err) {
    await handoverStep('clear-rejected', ['--reason', message(err).slice(0, 300)])
  }
}

async function gate() {
  const usage = await state.host.usage()
  const agents = (await state.host.agents()) || []
  const now = Date.now()
  return script([
    'handover-due',
    '--tokens', String((usage && usage.context && usage.context.tokens) || 0),
    '--turn-running', state.turnRunning ? '1' : '0',
    '--since-turn-complete', String((now - state.lastTurnComplete) / 1000),
    '--turn-started-since', state.lastTurnStart !== null && state.lastTurnStart > state.lastTurnComplete ? '1' : '0',
    '--background-tasks', String((state.stop.background_tasks || []).length),
    '--crons', String((state.stop.session_crons || []).length),
    '--agents-busy', String(agents.filter(a => BUSY.has(a.status)).length),
    '--since-owner', String((now - state.ownerAt) / 1000),
    ...probeFlags(),
  ])
}

async function considerHandover(event) {
  const step = await handoverStep(event)
  if (step.state !== 'idle') return
  const verdict = await gate()
  if (verdict.due) {
    const extra = state.cfg.handover_tokens !== PRODUCTION.handover_tokens ? ['--handover-tokens', String(state.cfg.handover_tokens)] : []
    await handoverStep('gate-yes', extra)
  } else if (verdict.blocking && verdict.blocking.length && verdict.blocking[0] !== 'tokens') {
    status('handover waiting on: ' + verdict.blocking.join(', '))
  }
}

// The wake reports the cover's state even when its own reads fail (an
// expired gh login silences both), so the stale note still reaches the Steward.
async function wake() {
  const found = await script(['wake'], true)
  if (found.error) status(String(found.error).slice(0, 200))
  const cover = found.cover || {}
  if (cover.stale) {
    status('the cover\'s last success is ' + (cover.last_success || 'missing') + ' (more than two hours old)')
    if (!cover.noted && cover.key) {
      state.coverNote = {
        key: cover.key,
        text: 'steward-wake: the cover\'s last successful run is ' + (cover.last_success || 'missing') +
          ', more than two hours old. Tell the owner the cover has stopped working (see docs/cells/steward/SKILL.md).',
      }
    }
  }
  // A prompt the mod submits does not pass through `prompt.submit`, so the
  // notes that hook adds to other prompts ride in the wake turn's own text.
  for (const trigger of found.triggers || []) {
    const pending = await pendingNotes()
    await state.host.submit([trigger.text, ...pending.notes].join('\n\n'))
    await script(['mark-woken', trigger.key])
    await acknowledge(pending.cover)
  }
}

// The notes every turn carries now: the awaiting-clear update note while a
// handover waits on the owner, and a stale cover's note once per episode.
// Nothing is acknowledged here: the caller acknowledges the cover note only
// once the turn carrying it was delivered, so a failed delivery leaves the
// note eligible on the next tick.
async function pendingNotes() {
  const notes = []
  const step = await script(['handover-step', '--event', 'prompt'])
  if (step.action === 'note') notes.push(step.text)
  const cover = state.coverNote
  if (cover) notes.push(cover.text)
  return { notes, cover }
}

// Marks a delivered stale-cover note, so each stale episode is noted once.
async function acknowledge(cover) {
  if (!cover) return
  await script(['mark-woken', cover.key])
  if (state.coverNote === cover) state.coverNote = null
}

async function guarded(fn) {
  try {
    await fn()
  } catch (err) {
    status(message(err).slice(0, 200))
  }
}

async function tick() {
  if (state.ticking) return
  state.ticking = true
  try {
    await guarded(wake)
    await guarded(() => considerHandover('tick'))
  } finally {
    state.ticking = false
  }
}

async function start(host, cwd) {
  if (state.started) return
  state.started = true
  state.host = host
  state.root = String((await host.root()) || cwd).split(BACKSLASH).join('/')
  const vars = await host.env()
  state.python = vars.STEWARD_WAKE_PYTHON || 'python'
  state.stateDir = vars.STEWARD_LAB_STATE_DIR || null
  const env = []
  for (const name of PROBE_ENV) {
    const value = vars[name]
    if (value !== undefined && value !== null && value !== '') env.push('--env', name + '=' + value)
  }
  try {
    state.cfg = await script(['config', ...env])
  } catch (err) {
    status('not started: ' + message(err).slice(0, 200))
    return
  }
  state.ownerAt = Date.now()
  await guarded(() => handoverStep('load'))
  state.timers.push(host.every(state.cfg.tick_seconds * 1000, () => tick()))
  state.timers.push(host.after(5000, () => tick()))
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    await start(hostOf($), e && e.cwd)
    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    if (e.agentId === undefined) {
      state.turnRunning = true
      state.lastTurnStart = Date.now()
    }
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined && state.cfg) {
      state.turnRunning = false
      state.lastTurnComplete = Date.now()
      const settle = state.cfg.settle_seconds * 1000
      state.timers.push(state.host.after(settle + 1000, () => guarded(async () => {
        if (state.turnRunning || Date.now() - state.lastTurnComplete < settle) return
        await considerHandover('turn-settled')
      })))
    }
    return next(e)
  })

  on('classic.Stop', async ($, e, next) => {
    if (e && !e.agent_id) {
      state.stop = { background_tasks: e.background_tasks || [], session_crons: e.session_crons || [] }
    }
    return next(e)
  })

  on('prompt.submit', async ($, e, next) => {
    if (!state.cfg) return next(e)
    const context = [...(e.context || [])]
    let cover = null
    await guarded(async () => {
      const kind = (e.origin && e.origin.kind) || 'unclassified'
      const verdict = await script(['origin-is-owner', kind, '--record'])
      if (verdict.owner) state.ownerAt = Date.now()
      const pending = await pendingNotes()
      context.push(...pending.notes)
      cover = pending.cover
    })
    const delivered = await next({ ...e, context })
    await guarded(() => acknowledge(cover))
    return delivered
  })

  on('session.end', async ($, e, next) => {
    if (e && e.reason === 'clear' && state.cfg) {
      const extra = state.lastTurnStart !== null ? ['--last-turn-start', iso(state.lastTurnStart)] : []
      state.timers.push(state.host.after(1000, () => guarded(() => handoverStep('session-end-clear', extra))))
    }
    return next(e)
  })
}
