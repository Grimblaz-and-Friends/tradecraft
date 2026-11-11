// The desktop keep-warm's hooks module: wiring over core/keep_warm_desktop.py (#983, lab-only).
// Design: tools/keep_warm/README.md#how-it-behaves
//
// Every decision is the core's: whether the session is kept warm at all, when
// a keep-warm turn is due, and whether one that ran broke its rules. This
// module tracks whether a main turn is running and whose it is, ticks, submits
// the turn the core answers, and refuses the model's tool calls while that
// turn runs. It writes no file and draws nothing (the pane and the wake own
// the status line): its own faults go to the core's log.
import type { EngineInterface, Register } from 'claude-code'

type $ = EngineInterface

const CORE_TIMEOUT_MS = 30_000
// The core reads a finished keep-warm turn back from the transcript, so its
// check runs a moment after the turn ends, once the turn's entries are written.
const TURN_END_DELAY_MS = 5_000
const REFUSAL = "keep-warm: this turn is the practice's keep-warm, not the owner; answer with one word and use no tools."

const state = {
  started: false,
  inert: true,
  turnRunning: false,
  // A keep-warm prompt submitted whose turn has not started yet.
  pending: false,
  // The running main turn is the keep-warm's own.
  own: false,
  ticking: false,
  flags: [] as string[],
}

function message(err: unknown): string {
  return String((err as any)?.message ?? err).slice(0, 300)
}

async function core($: $, command: string, args: string[] = []): Promise<any> {
  const script = `${$.plugin.root}/core/keep_warm_desktop.py`
  const argv = ['python', script, command, '--session', String(await $.session.id()), ...args, ...state.flags]
  const ran = await $.process.run(argv, { timeoutMs: CORE_TIMEOUT_MS })
  let answer: any = null
  try {
    answer = JSON.parse(String(ran.stdout || '').trim().split('\n').pop() ?? '')
  } catch {
    answer = null
  }
  if (ran.exitCode !== 0 || answer === null || typeof answer !== 'object') {
    const why = answer?.error ?? (String(ran.stderr || '').trim().split('\n').pop() || 'no output')
    throw new Error(`keep-warm core ${command} exited ${ran.exitCode}: ${why}`)
  }
  return answer
}

async function fault($: $, err: unknown) {
  try {
    await core($, 'fault', ['--text', message(err)])
  } catch {
    // A fault that cannot be logged stops nothing further.
  }
}

// The state directory and the probe-only timings, passed on every core call;
// the core refuses the timings against the default directory.
async function settings($: $): Promise<string[]> {
  const flags: string[] = []
  const dir = await $.env.get('KEEP_WARM_LAB_STATE_DIR')
  if (dir) flags.push('--state-dir', dir)
  // Each variable is named literally, so validation lists what the mod reads.
  const probes: Record<string, string | undefined> = {
    KEEP_WARM_DESKTOP_INTERVAL_SECONDS: await $.env.get('KEEP_WARM_DESKTOP_INTERVAL_SECONDS'),
    KEEP_WARM_DESKTOP_LAPSE_SECONDS: await $.env.get('KEEP_WARM_DESKTOP_LAPSE_SECONDS'),
    KEEP_WARM_DESKTOP_CAP_SECONDS: await $.env.get('KEEP_WARM_DESKTOP_CAP_SECONDS'),
    KEEP_WARM_DESKTOP_TICK_SECONDS: await $.env.get('KEEP_WARM_DESKTOP_TICK_SECONDS'),
  }
  for (const [name, value] of Object.entries(probes)) {
    if (value) flags.push('--env', `${name}=${value}`)
  }
  return flags
}

async function tick($: $) {
  if (state.ticking || state.inert || state.turnRunning || state.pending) return
  state.ticking = true
  try {
    const usage: any = await $.session.usage()
    const context = usage?.context ?? {}
    const args = ['--turn-running', '0', '--context-tokens', String(Math.round(Number(context.tokens) || 0))]
    if (typeof context.window === 'number' && context.window > 0) args.push('--window', String(context.window))
    const answer = await core($, 'due', args)
    // A turn may have started while the core answered.
    if (!answer.submit || state.turnRunning || state.pending) return
    // Pending before the submit, so the turn it starts is known as the keep-warm's.
    state.pending = true
    await core($, 'submitted')
    try {
      await $.prompt.submit({ text: String(answer.text) })
    } catch (err) {
      // No turn came of it: the core closes the turn it recorded open, and stops.
      state.pending = false
      await core($, 'turn-end', ['--own', '1'])
      throw err
    }
  } catch (err) {
    await fault($, err)
  } finally {
    state.ticking = false
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    try {
      if (!state.started) state.flags = await settings($)
      const answer = await core($, 'load', ['--root', String(await $.session.root())])
      state.inert = Boolean(answer.inert)
      if (!state.started && !state.inert) {
        state.started = true
        $.clock.every(Number(answer.tick_seconds) * 1000, () => void tick($))
      }
    } catch (err) {
      await fault($, err)
    }
    return started
  })

  on('turn.start', async ($, e, next) => {
    if (e.agentId === undefined) {
      state.turnRunning = true
      state.own = state.pending
      state.pending = false
    }
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    if (e.agentId === undefined && state.turnRunning) {
      state.turnRunning = false
      const own = state.own
      state.own = false
      if (!state.inert) {
        $.clock.after(TURN_END_DELAY_MS, () => {
          void core($, 'turn-end', ['--own', own ? '1' : '0']).catch(err => fault($, err))
        })
      }
    }
    return done
  })

  // The model's tool calls in a keep-warm turn are refused, unrun; another
  // mod's own calls (the pane's title reads) are not the model's and pass.
  // A guard that fails in a keep-warm turn still refuses: letting an unchecked
  // call run there is the one thing this turn must never do.
  on('tool.call', async ($, e, next) => {
    if (!state.own || next.origin.plugin !== 'engine') return next(e)
    return { deny: REFUSAL }
  }).catch(($, e, next) => (next.called ? next(e) : state.own ? { deny: REFUSAL } : next(e)))
}
