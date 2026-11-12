# D-999 — Price every model a run used, and say how to add a missing price

**Purpose:** record why #936 adds five Claude prices, prices Haiku 5.5 per request, turns a model with no price from an unknown run into a labelled runtime figure or a named floor, and has the report say where to look up a missing price and where to paste it; and record the calls made inside the brief's rows. **Audience:** a future session changing the rate card, how `change_cost.py` prices a run, or the repository price file. **Success:** that reader can recover what was chosen over what without the issue.

The owner's [affirmed brief](https://github.com/Grimblaz-and-Friends/tradecraft/issues/936#issuecomment-6815693523) governs. Its pre-implementation artifact was [settled on the would route](https://github.com/Grimblaz-and-Friends/tradecraft/issues/936#issuecomment-6816210076), and the holder's reading before the build amended it on the cold seat's points. The lane is ordinary / connected, and no panel was bought. This record supersedes none.

## The fault

Product artifact turns (Daemon #95, Organizations-of-Verra #568) used Sonnet 5 helpers, and their cost reports came back unknown: one model with no card row made the whole run unknown, so under two cents of a helper left a $3.75 author turn and a $10.32 build read unknown. Fable 5.2, Sonnet 5.5, Haiku 4.5 and Haiku 5.5 had no rows either, and Fable 5.2 is a holder model, so every holder close on it was unpriced. The report said only that no dated rate matched.

## What was chosen over what

- **Report guidance, over a command that reads the pricing page and writes an entry, and over a live page lookup while a report runs** (the owner's ruling: "B: report guidance"). Adding a model is a lookup on the vendor's page and a paste.
- **A labelled runtime figure or a named floor, over unknown.** A model with no price takes the runtime's own figure when the runtime marked it as a list price, and is otherwise left out of a figure marked as a floor that names it. Every other fault still makes a run unknown. A holder transcript was already handled this way.
- **The runtime's figure is trusted only when marked `list`.** A runtime too old to know a model charges it at another model's rates and marks that figure otherwise.
- **The filled entry goes in the repository's own price file, `rates.json` in its `.tradecraft` folder, over the installed plugin's card.** An entry pasted into the plugin's card would be lost at the next plugin update and would show as a change to the plugin. A shipped row wins where both price a use, and the report says the repository entry can then be removed.
- **Haiku 5.5 is priced per request at its own tier.** Its posted page charges five times as much for any request whose prompt is above 100,000 tokens, counting cache reads and writes, and 11 of the 14 Haiku 5.5 replies recorded on this machine were above it (mean 183,318 prompt tokens). A flat lower price would understate them.

## Calls made inside the rows

- **C1: the runtime/card comparison accepts either uniform cache-write reading.** For a `modelUsage` share with aggregate cache writes, on a row with both write prices, the card is read at the one-hour price (as before) and at the five-minute price, and the runtime's list figure is accepted within a cent of either. A spike over every `modelUsage` share marked `list` on this machine on 2026-11-12, at the retrieval's prices (the card's for Opus):

  | Model | 5-minute only | 1-hour only | either | between | outside |
  |---|---|---|---|---|---|
  | `claude-sonnet-5` | 5 | 0 | 0 | 0 | 0 |
  | `claude-haiku-4-5-20251001` | 4 | 0 | 3 | 0 | 0 |
  | `claude-opus-5-5` | 3 | 1,274 | 2 | 151 | 0 |
  | `claude-opus-5` | 0 | 55 | 1 | 0 | 0 |

  A main conversation writes one-hour cache and a helper five-minute cache, and `modelUsage` gives only the sum. Without C1 every Sonnet 5 helper share would read about $2.48, flagged, against a right runtime figure of $1.9993206. Its effect on existing records: the three Opus 5.5 shares matching only the five-minute reading move from a flagged card figure to the runtime's, and the 151 between the readings stay flagged.
- **C2: every new row starts 2026-09-20T00:00:00Z,** the card's established backfill start, before the earliest dispatch in the store (2026-09-20T14:07:28Z) and so before each model's earliest recorded run: Haiku 4.5 2026-10-13, Sonnet 5 2026-11-01, Haiku 5.5 2026-11-03, Sonnet 5.5 2026-11-07, Fable 5.2 2026-11-11.
- **C3: tiers apply only where each request's counts are kept,** which is each transcript reply. Dispatch `modelUsage` totals and cloud session deltas are totals; there a tiered model takes the runtime's list figure or a floor saying it is priced per request, and it never enters the missing-price guidance, because the card does price it. Pricing dispatches from stdout logs or cloud ledger rows would be a new pricing source.
- **C4: a damaged repository price file doesn't stop the report.** The file or each unusable row is named under `price_files`, so a half-filled paste can't take away every other figure. A damaged shipped card stays fatal.
- **C5: the report finds the repository file by `--root`,** falling back to the current directory's git top level, matching the work entrance's `--root`.
- **From the holder's reading:** the guidance shows the `prompt_tiers` shape inline instead of pointing at the shipped Haiku 5.5 row, and a transcript reply on an unpriced model enters the guidance with its reply count.
- **A malformed native count on a reply with no price stays a fault of its own,** so a missing price can't hide it and the row stays unknown when nothing else priced.
- **Keep-warm pings are not touched.** The pull request adding `_ping_price` (#993) had not merged when this was built; whichever merges second carries this rule into it.

## The prices

Retrieved from <https://platform.claude.com/docs/en/about-claude/pricing> at 2026-11-12T05:21:04Z, USD per million tokens, and re-read by the builder at 2026-11-12T06:19:40Z with every price unchanged:

| Model | Input | 5m cache write | 1h cache write | Cache hit | Output |
|---|---|---|---|---|---|
| Claude Fable 5.2 | 8 | 10 | 16 | 0.20 | 40 |
| Claude Sonnet 5.5 | 2 | 2.50 | 4 | 0.10 | 10 |
| Claude Sonnet 5 | 2 | 2.50 | 4 | 0.20 | 10 |
| Claude Haiku 4.5 | 1 | 1.25 | 2 | 0.10 | 5 |
| Claude Haiku 5.5, prompt up to 100,000 tokens | 0.10 | 0.125 | 0.20 | 0.01 | 0.50 |
| Claude Haiku 5.5, prompt over 100,000 tokens | 0.50 | 0.625 | 1 | 0.05 | 2.50 |

Sonnet 5's $2/$10 was introductory through 2026-08-31 and is now its standard price. At these prices, with cache writes at the five-minute rate, an Organizations-of-Verra #576 artifact run's Sonnet 5 share reproduces its runtime `costUSD` of 1.9993206, marked `list`; that run, trimmed to its usage, model and timing fields, is the fixture the tests price.

The tests are in `lib/tests/test_change_cost.py`, `lib/tests/test_holder_cost.py` and `lib/tests/test_cloud_build.py`.
