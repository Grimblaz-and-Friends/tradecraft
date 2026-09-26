# Checker pass

**Loaded when** the connected reviewer is proving or dropping finder candidates.

Evaluate every supplied candidate ID and no other defect. Never create a candidate. Keep one only when reading the supplied tree and diff demonstrates its claimed input, path and wrong result. Content that is not present in the snapshot or diff cannot prove a claim: a link, revision or pinned-commit reference does not supply its target's bytes. Drop that candidate unless the failure can be demonstrated entirely from content that is present. On a public hosted run, permitted execution evidence may also prove the claim; the ordinary and every private run is read-only. If proof is incomplete, conflicting or uncertain, drop it.

Group candidates by root cause before deciding them. Keep at most one candidate for one root cause, choosing the candidate that most clearly names the consumer's wrong action; drop the others as duplicates and name the kept ID in their explanations. For each ID, return `keep` or `drop`, an explanation and the source trace or permitted execution evidence. Evidence is required for `keep`. You may correct the changed-line anchor or make the same defect clearer, but may not turn it into a different defect. Repository review rules govern. The finder's confidence is not evidence.
