# Checker pass

**Loaded when** the connected reviewer is proving or dropping finder candidates.

Evaluate every supplied candidate ID and no other defect. Never create a candidate. Keep one only when reading the supplied tree and diff demonstrates its claimed input, path and wrong result. On a public hosted run, permitted execution evidence may also prove the claim; the ordinary and every private run is read-only. If proof is incomplete, conflicting or uncertain, drop it.

For each ID, return `keep` or `drop`, an explanation and the source trace or permitted execution evidence. Evidence is required for `keep`. You may correct the changed-line anchor or make the same defect clearer, but may not turn it into a different defect. Repository review rules govern. The finder's confidence is not evidence.

