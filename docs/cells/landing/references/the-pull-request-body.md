# What a change owes at and after the commit

**Loaded when** writing a pull request body here, checking a draft before anything is opened, returning to an open pull request, or listing what the change still owes before it can merge.

**The body carries a line beginning `**Waiting on you:**`**, naming the marked asks this change is waiting on or saying it is waiting on nothing. The `engagement` cell makes the mark what puts an ask; this is where the change says whether it put one. `python tools/check_ask_declaration.py --pr N` refuses a body without the line, and CI runs it on every pull request. It checks presence, never truth, because deciding whether an unmarked ask is buried in prose is a content judgment. `--body-file PATH` checks a draft before anything is opened.

The body states `Closes #N`, or one line saying it closes none and why. **A change that fixes a cause disposes of every issue tied to it as a symptom**, with a closing reference for each one the fix discharged and one line for each survivor saying why it stands. Read the symptoms from the cause's own GitHub sub-issue list; where a relationship could not be represented there, walk the issue's flagged prose by hand. Each closing reference is a bare keyword and one number on its own line, because that is the form GitHub parses.

The body carries `**Dispatch:** holder <vendor> <model>, <usage exactly as the runtime displayed it | usage unavailable — reason>; implementer <vendor actually run>.` Read each value from the runtime or dispatch record rather than reconstructing it from a transcript.
