# The ideal flow — north star

> **In plain terms:** this is the flow we would run if we were starting from nothing — how a concept becomes a finished change with quality, stated as ideals. It informs direction and settles arguments about where the practice should head; it binds nothing. The practice adopts pieces of it change by change, through the normal intake, each on its own merits.

**Purpose:** record the ideal shape of concept-to-change, as the reference future changes cite when they move the practice toward it. **Audience:** the owner, and any session framing or arguing a change to the practice's own mechanics. **Success:** a reader who was not in the conversations that produced it understands the ideal well enough to argue a gap against it; and no session mistakes it for binding rule.

**Status: north star.** Nothing here overrides doctrine, the charter, or a cell. Where this document and current practice disagree, current practice governs until a change lands through its own ceremony. Amended like any other repo-only document.

## The stages

**1. Capture.** The concept is recorded as a *problem with a reason* — what's wrong or wanted, and why it matters — not as a solution. The executable form: a defect arrives as a **failing reproduction** where possible; an idea arrives with the observed evidence that motivated it. A repro is strictly better than prose — it can't be misread, and it hands Converge its first acceptance criterion for free.

**2. Frame.** Someone decides whether it's worth doing at all, and what it actually is: scope, stakes, reversibility. Proportionality gets set here — everything downstream scales with this decision. The factual half of "worth it" is measured where possible; the values half is genuine judgment against the values declaration, and stays so. Feasibility PoCs live here: the riskiest slice built first to answer "can this be done at all."

**3. Converge.** The solution space is explored — options, trade-offs — and collapses to a commitment: what "done" means, what's deliberately out, and why this shape over the others. Where argument can't settle a fork, a **spike** does: a bounded build, its question stated first, its code disposable by contract, its answer feeding the rationale. A spike's question may be *"what should done look like?"* — for emergent work (design, UX, research) where done is recognized rather than pre-specified, Converge is a **chain of such spikes**, the criteria themselves a versioned artifact firming as the work teaches. Genuine forks go to whoever owns the consequences; everything else is decided and reported. The output is an explicit — and ideally **executable** — statement of intent: acceptance criteria authored as tests/evals/measures *before* implementation exists. Everything downstream is judged against it.

**Promotion rule.** What survives a spike unexamined is only knowledge. A prototype may graduate into the deliverable, but only deliberately: re-admitted through Converge with its now-known criteria stated and real verification applied — never silently kept.

**4. Build.** Implementation against that statement, with the tightest possible feedback loops — the pre-authored measures firing as the work happens, not after. Two shapes: **converging** (one implementation refined against the criteria) and **empirical search** (multiple candidate implementations scored against a graded measure, keep the winner) — the natural shape when candidates are cheap to produce. Discoveries that invalidate the convergence go *back* to Converge, not silently absorbed. Performance and similar claims made during build are runs, not opinions.

**5. Verify.** Mechanical evidence that the acceptance criteria hold: the pre-authored measures pass — *did we build the thing right*, judged against Converge's artifact. Where stakes warrant, verify the *verifier* — would these tests actually catch a bug?

**6. Validate.** *Did we build the right thing* — judged against **Frame's problem**, upstream of the criteria. Someone in the **consumer's frame** — fresh context, the consumer's starting knowledge and actual task, never the builder walking their own happy path — experiences the change and produces a **report**: friction, confusion, surprise, delight. Its findings are dispositioned like any others — fixed, or declined with a reason. Validation can fail while every measure passes; that outcome means *the criteria were wrong* — a backward edge to Converge that Verify can never trigger. And validation outlives the change: the full customer experience exists only after Integrate, so post-integration experience — quantitative and qualitative — is a standing intake feeding Capture.

**7. Judge.** Independent adversarial review against the stated intent — independent meaning the judgment wasn't shaped by having built it. A finding is a captured concept and gets the flow's economics; the finder bears the burden of admission:

- **Admission bar.** Findings are demonstrated, not argued — a claimed bug arrives as a failing repro; a defended finding is refuted by running the scenario. Undemonstrated *and* untied to the stated intent → not admitted, rather than admitted-with-a-caveat.
- **Boundary test.** A finding is judged against the stated intent and boundary, never against an imagined ideal. Does it *contradict* the criteria, or *expand* them? Contradiction → real finding. Expansion → a proposal for new work, routed to Capture with its own worth-it question, or dropped. "Wouldn't it be better if" is not a defect.
- **The review measures itself honestly.** Its success is escaped defects prevented per unit of total cost imposed — finding + judging + fixing + the permanent complexity of the fixes — never finding count. "Clean, nothing worth raising" against a real bar is a success.

Judge also asks the question no measure can answer about itself: *does the measure capture the intent?* — the test suite and evals reviewed as artifacts, against Goodhart. Every admitted finding gets an explicit disposition: fixed, or declined with a reason. No finding evaporates — and the null disposition is cheap and honorable, or fear of dropping findings silts the codebase.

**8. Integrate.** The change lands; the irreversible act belongs to whoever bears its consequences. The executable form of the commitment decision: staged exposure — ship to a slice, measure, then commit — with rollback triggered by measurement, not by someone noticing.

**9. Compound.** What the work taught flows to its durable home before the context that learned it is gone. A lesson compounds into **the most executable form it can take** — a check, a lint, an eval that guards forever without being recalled — with prose as the fallback. Killed and deferred changes exit through here too: what they taught is the deliverable they actually produced. **And Compound feeds Capture:** review findings routed as new concepts, telemetry surfacing defects, validation reports, lessons implying follow-on work — the flow is a cycle, its own biggest source of concepts, not a conveyor. This is what makes change N+1 cheaper and better than change N.

## Three properties that matter more than the stages

- **Each stage emits an explicit artifact that the next stage judges against.** Quality isn't a phase; it's that no stage is judged against vibes. TDD/BDD/evals are this property at full strength: the convergence artifact made mechanical, unable to drift or be reinterpreted charitably. The artifact chain is also the *interface* between stages: a fresh-context boundary buys independence where judgment needs it (Judge, Validate, search candidates), and everywhere else is the test that proves an artifact complete — a stage that cannot run cold has an incomplete artifact, not a context requirement. Only Compound is bound to the context that learned, and the owner's conversation to its running state.
- **The flow is a loop with backward edges, not a pipeline.** Any stage can invalidate an earlier one — for correctness *or* for economics — and the ideal flow makes going back cheap and shameless.
- **Executable evidence beats argument, at every stage that allows it.** Wherever a disagreement or uncertainty can be settled by running something, run it: repros at Capture, data and PoCs at Frame, spikes at Converge, measures during Build, mutation-testing the tests at Verify, consumer-frame experience at Validate, demonstrated findings at Judge, canaries at Integrate, mechanisms over prose at Compound. The residue that resists execution — whether the problem matters, whether the measure captures the intent, whether to accept the consequences — is exactly what remains genuine human judgment, and pushing everything else into execution is what buys that judgment its attention.

## The owner's interface

The flow touches its human at defined points — the values half of Frame, forks and affirmation at Converge, dispositions genuinely theirs at Judge, the commitment at Integrate. The ideal designs each touchpoint for the quality of the owner's judgment, not the ceremony of their sign-off:

- **Shaping, not ratification.** A finished design handed over for approval invites a rubber stamp — the decision congealed before the owner arrived. The ideal brings each fork while it is genuinely open: argued (live options, consequences, a recommendation), one decision at a time, in conversation. The artifact *records* what the conversation settled; it is never the medium through which the owner first encounters a decision.
- **Right-sized, right-timed.** What reaches the owner is what is genuinely theirs; everything else is decided and reported. Each ask arrives when the decision is actually open — early enough to steer, late enough to be argued from evidence rather than speculation.
- **The mirror failure is real too:** dripping non-fork questions spends the same attention ratification wastes, one interrupt at a time.

## The economics: worth-it is a standing question

Every gate holds two questions: *is the work right* (against the previous stage's artifact) and *is the work still worth it* (against the updated cost/value picture). Every act of executable evidence is also a measurement — the spike that picks an option also reveals the true cost; the canary that verifies safety also measures value delivered. So estimates sharpen as spend increases, and the ideal sequences work to buy the most estimate-sharpening per unit spent: riskiest assumption first — which is what a spike is, economically.

- **The re-ask fires on movement, not ritual.** Worth-it is re-opened when the estimate *moves* — a spike surprises, cost balloons, evidence disappoints — not re-litigated at every gate. Silence means the Frame answer stands. A standing *scan* for movement — a board sweep, a metric watch — is how movement gets noticed and is not itself a re-ask; the re-ask is what a scan's hit triggers.
- **Stopping is an outcome, not a failure.** "We learned enough to kill this" is the flow working cheaply. Everything in practice fights it — sunk cost, momentum, a half-built change wanting to be finished. Downgrades and deferrals are the same move at smaller scale.
- **The flow feeds a portfolio.** Once every in-flight change carries a live cost/value estimate, changes become comparable, and "continue this" always implicitly means "instead of that." Prioritization is a standing consequence of evidence, not a one-time backlog ordering — and it reaches captured-but-unstarted work too: an item that will never start is killed by the same move, at the cheapest possible point.
- **A tension to keep visible:** cost is easy to measure and value usually isn't, so this machinery can quietly become "do only what's cheap to justify." The values declaration (`values.md`, beside this file) is the counterweight: the unmeasurable half of worth-it is judged against it, and work whose value resists measurement is funded as allocation, not per-item ROI.

The flow itself is subject to all of this: escaped defects, review catch rates, reopened convergences are measurable, and process changes are changes — held to the same evidence.

## At scale: epics and sagas

The flow is scale-free and applies recursively. An epic (a group of stories) and a saga (epics across repositories/teams) run the **same nine stages at their own level**, with one recursive move: **Build at level N = running the flow at level N−1 over the children.** An epic's Build is its stories flowing; a saga's Build is its epics. Everything else — its own convergence artifact, gates, worth-it question — belongs to level N itself, not the sum of its children.

What shifts with scale (degree, not structure):

- **Converge becomes decomposition.** The level-N artifact decides the set of children and their boundaries — and its acceptance criteria are the emergent ones no child owns: end-to-end coherence, the whole experience. An epic can be done as stories and fail as an epic.
- **Emergent mode is the default.** Child criteria can usually be pre-authored; parent criteria firm up as early children teach. The chain-of-spikes / versioned-criteria machinery is the normal operating mode here — early stories are partly spikes against the epic's convergence.
- **The economics dominate.** Kill/defer, riskiest-first, and the portfolio live naturally at this level. A parent killed partway is not a failure if its shipped children were individually valuable — which makes *"each child delivers value alone where possible"* a parent-level convergence criterion, not a nicety.
- **Integrate dissolves into increments.** Children integrate continuously; parent-level Integrate becomes *declaring done*, and staged exposure is satisfied structurally by shipping value all along.
- **Validate moves up.** The consumer experiences the epic, mostly; child-level validation is partial by construction. Consumer-frame validation weight belongs at the highest level the consumer actually experiences.

**Sagas add plural ownership.** Multiple repositories may mean multiple owners, values declarations, and doctrines. The saga's convergence artifact is therefore mostly **the seams: interfaces, sequencing, and timing between epics** — and its genuine forks may need agreement between owners rather than one owner's call.

**Timing at the seams.** When teams share dates — especially with hardware-locked, waterfall-shaped teams:

- **A date is a value shape, not a new stage.** A hard date means value is a function of time, often a cliff (a missed window is worth zero, or waits a year). It enters at Frame as a constraint; the estimates gain a time axis.
- **Waterfall is this flow at reversibility ≈ zero.** A tape-out is an Integrate that is batched, irreversible, and uncanaryable — so backward edges after it are unavailable, forcing all evidence-gathering forward: exhaustive criteria, verification before commitment, frozen convergence. The hardware team runs the same ideal at extreme parameters; neither side's process is wrong.
- **Dates commit interfaces, not implementations.** The ideal seam commitment is "this contract holds at this date," leaving each team's interior evidence-paced. Riskiest-first becomes **de-risk the seam earliest**: integrate against stubs, simulators, emulated hardware long before the real counterpart exists — run the interface, don't argue about it.
- **A date commitment is an artifact, judged like any other.** Evidence-backed estimates, honest uncertainty, the standing re-ask: slippage is estimate movement and fires re-planning at the seam — hiding it is the trustworthiness violation, discovered at the expensive end.
- **Scope is the release valve.** When the date is fixed and estimates move, the downgrade move (smaller version, on time) beats the slip — the cliff makes partial-on-time worth more than complete-late. Fixed date, variable scope; never both fixed, which is how schedule fiction gets manufactured.

## Failure modes the ideal is designed against

- Solutioning at capture (Capture smuggles Converge).
- Participation as ratification — the owner handed a finished design to approve rather than open forks to decide.
- Ceremony flatness (same weight for every change) — including ritual re-asking of worth-it.
- Verification against the implementation instead of the intent.
- Validation by the builder walking their own happy path.
- Review by the builder's own frame.
- The measure becoming the whole target (Goodhart) — acing the eval, missing the point — including the review measuring itself by finding count.
- Findings judged against an imagined ideal instead of the stated boundary.
- The spike silently becoming the implementation — graduation without re-admission through Converge.
- Emergent work faking pre-specified criteria, or routing around the flow because it can't.
- Sunk cost carrying a change past the evidence against it.
- Fear of the null disposition silting the codebase with fixes nobody needed.
- Fixing both date and scope — manufacturing schedule fiction; slippage hidden instead of reported as estimate movement.
- Learning that dies with the session — or compounds as prose when it could have compounded as a mechanism.
