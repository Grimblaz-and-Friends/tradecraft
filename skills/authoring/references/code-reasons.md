# How code and its documents carry their reasons

**Loaded when** you are writing or changing code a change ships, a comment in it, its design document or a decision record, or deciding where a change's reasons must land before merge.

## Three homes for the why

**The code says why in the present tense, the maintained design document says what the system does now and why, and the decision record keeps what was chosen over what, when, and on what evidence.** Each holds only its own part, because one fact in two homes drifts.

## The pointer

**Each class, module or file a design document covers opens with one pointer to that document's section**: a repository path plus anchor. That section names the decisions currently in force behind the code, by links to their decision records.

**Code never points at a decision record or an issue directly.** Decisions pile up against a class while the class lives on, so a class can't point at one decision, and a maintained in-force list can be kept current where search can't tell which decision still holds. Decision records stay frozen and are reached through the section; search is for history.

**A change that adds a decision or supersedes one updates the section's in-force list.** A change that adds code no design document covers opens a section for it, creating the repository's design document if it has none, and points the new code at it. Code a change adds gets a section; code it only edits keeps waiting for its repository's catch-up, because rewriting the old is its own work.

## One-line reasons

**Write a one-line reason wherever a newcomer, person or agent, would ask why the code is like this and the code can't answer by itself.** The reason is conceptual: it never says what the code does, never states a number that can change, and never carries history — no issue, pull request or date — because code reads as what is there now.

- **Where the code could be changed to answer for itself, change the code instead.** A name or a structure that answers the question needs no line beside it.
- **A reason that needs more than one line is a sign to simplify the code, or that the fuller explanation belongs in the design document; the line still states its reason.**
- **Write nothing where a newcomer wouldn't ask**, because an unasked comment is a what.

One example. The file opens with its pointer, and the rule carries the one reason a newcomer would ask for:

```python
# Design: design/pricing.md#delivery-fee

def delivery_fee(order):
    # Weight is ignored so a customer knows the fee before the order is packed.
    return BASE_FEE + order.distance_band.fee
```

The bad form of the same line cites the issue that decided it and restates the arithmetic beside it — a history and a what, both of which the next change makes false.

## Lasting reasons leave the brief before merge

**Before merge, every reason in the affirmed brief that stays true of the system lands in the design document, if it explains what the system does now, or in the decision record, if it records what was chosen over what** — because the brief is not read again after merge.

**A change that decides nothing, such as a fix or a cleanup, writes no decision record if a reader who never saw its issue can tell from the code and the documents it points to why the change was made; if they can't, it owes one.**
