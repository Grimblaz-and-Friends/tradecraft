# Proof v1 interoperability fixtures

**Loaded when** implementing or testing the independent gate that consumes the entrance's proof document.

`v1-valid.json` is a schema-valid document whose public records are assumed to match the live fixture. `v1-negative-cases.json` names the rejecting cases and expresses only the field overlay that differs from the valid document plus the trusted live fact the gate must re-derive. An overlay replaces the named object or array; it is not a JSON Merge Patch implementation requirement.

The schema rejects the producer-verification field structurally. The other cases are deliberately schema-shaped where possible: schema validity cannot establish head applicability, public check identity, configured reviewer completeness, review credit, disposition authority, or the public/declaration distinction. The gate applies those cases against its own fetched records and trusted policy.
