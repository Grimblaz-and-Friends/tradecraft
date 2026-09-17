# Index row template

**Loaded when** you are appending a review's row to a review index. Copy the row whole and fill every key; `../references/the-record.md` says what the row is for and what it may not carry.

```json
{"date": "YYYY-MM-DD", "artifact": "<what was reviewed, one line>", "lane": "<routine | panel>", "report": "<https URL of the posted report>", "highs": ["<each sustained high, one entry>"], "staffing": {"model": "<model/effort; uneven staffing spelled in the value, as fable/max (cold-read), opus/xhigh (rest)>", "runtime": "<one spelling per runtime, as claude-code (windows)>"}, "external": "<what configured automation posted, qualitatively, even where it produced nothing — never a count, never a seat>", "notes": "<one line of context that would otherwise be lost>"}
```

- `highs`: one entry per sustained high, empty where none was sustained; a repository carrying more per high makes each entry a mapping that still names the high under a key its own material states.
- `staffing`: a seat that failed unreplaced is said in the value as a panel that was short wherever omission would otherwise misdescribe the run.
- `external`: configured automation only; a commissioned pass is reported in the report's prose and never here or under `staffing`.
- `notes`: omit the key where nothing would be lost.
- A repository's own additions — what the review cost, a key per high — are its own material's, and no count of findings under any name.
