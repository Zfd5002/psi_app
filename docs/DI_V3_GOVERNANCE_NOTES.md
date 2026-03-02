# DI V3 Governance Notes

## Internal Tie-break Exemption (Deterministic, Non-heuristic)

Scope:
- `psi/services/di/shortlisting.py`

Rule:
- The shortlisting sort order uses a fixed internal deterministic tie-break list:
  - `SHORTLISTING_INTERNAL_TIEBREAK_KEYS`
- This ordering is an implementation-level tie-break contract only.
- It is not a weighted heuristic ranking surface.
- It does not introduce numeric weights, adaptive scoring, or learned ordering.

Governance rationale:
- V3 external recommendation ordering surfaces are policy-driven (`ranking_policy_v0_2`).
- Internal tie-break remains explicit and locked by tests to prevent silent drift.

