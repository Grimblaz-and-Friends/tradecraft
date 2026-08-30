**Load this when a script launches another program.** A session that only reads or writes files does not need it.

## The rule, and why it is about the call rather than about stdin

**A launch redirects nothing, or names all three of stdin, stdout and stderr.**

On Windows `subprocess._get_handles` opens with `if stdin is None and stdout is None and stderr is None: return (-1, ...)`. A launch that redirects **nothing** never asks `GetStdHandle` anything, so it cannot fail this way. Redirect one stream and the other two resolve through the process's std-handle table — which can still name a handle something has since closed. `DuplicateHandle` on that raises `OSError: [WinError 6] The handle is invalid`, out of a call that has nothing to do with the command being run.

So *"name your stdin"* is the wrong rule, and wrong in the direction that costs: applied to a launch redirecting nothing, it converts an immune call into a failing one. Measured under a test runner's default capture, twenty launches per case in a fresh process each: `run(cmd)` failed 0/20, `run(cmd, stdin=DEVNULL)` failed 20/20, `run(cmd, stdin=DEVNULL, capture_output=True)` failed 0/20.

## The compliant forms

- `run(cmd, stdin=DEVNULL, capture_output=True)` — a program given nothing to read, whose output you want. Nearly everything.
- `run(cmd, input=payload, capture_output=True)` — a program you feed; `input=` implies `stdin=PIPE`, so it covers that stream. On `run` alone, `input=None` does **not**: it never reaches `run`'s `if input is not None`, so it leaves stdin inherited while looking named.
- `run(cmd)` — a program run purely for its side effects, output going wherever the caller's went. Lawful, and adding a keyword to it is the mistake above.
- **`check_output` redirects `stdout` before you pass anything**, since it is `run(*popenargs, stdout=PIPE, ...)`. So `check_output(cmd)` is *not* the lawful bare form above — it is a partial redirect, measured failing 20 times in 20. Its compliant form is `check_output(cmd, stdin=DEVNULL, stderr=DEVNULL)`; naming all three is impossible, because supplying `stdout=` raises `ValueError`. It also rewrites `input=None` to `b''` before calling `run`, so unlike `run` it pipes stdin either way.
- **`getoutput`, `getstatusoutput` and `os.popen` have no compliant form at all.** Each redirects a stream by construction *and* exposes no stdin parameter, so nothing you can pass satisfies the rule. Do not use them.

`stdin=None` is the default spelled out, so it redirects nothing and covers nothing.

**Read a launcher against its own source, not against `run`'s.** The two bullets above are both cases where a wrapper's behaviour is not `run`'s, and both were missed by people reasoning from `run` — including, three times over, by reviewers proposing fixes for the first two.

## Why it fails intermittently, and why green CI says nothing

Windows recycles handle values. When some unrelated object in the process happens to hold the recycled value, the duplicate **succeeds** — and the child silently receives an unrelated handle. When the value is free, the launch raises. Nothing about the code, the ordering, or the machine has to change for the answer to flip, so a suite reports a different failure set on every run with one error behind all of them.

**A green Windows leg on a build server is not evidence about this.** A CI step's interpreter is born with its streams already redirected, and being born that way is itself the immunity — the table it inherits names handles that are still open. What breaks the table is a redirect performed *inside* a living process, leaving the table naming what it closed. Neither condition is something a reader can check about their own harness, which is why the rule above is stated as a property of the call: *did I redirect none, or name all three?* is exact, and answerable without knowing anything about the process you are running under.

## The guard, and what it cannot see

A call-site check reads this off one call and needs no guess about what reaches where. **What it reads is the callee and its keyword arguments; a second positional argument, a splat of either kind, and a non-literal `capture_output` are unread, and unread is silence. A stream keyword whose value is not the literal `None` is read as a redirect — including a name that happens to be `None` at run time.** Silence is deliberate where the redirection is genuinely unknown, and a guard that reddened there would block lawful work, which fails as hard as passing unlawful work. The last clause is the one to carry away: a call-site check cannot know what a name evaluates to, so `stdout=NL` where `NL = None` reads as covered and is not.
