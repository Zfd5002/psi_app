# CODE REVIEW w101 (Sub-assessment library tightening)

Scope reviewed:
- `psi/services/di/sub_assessments.py`
- `psi/services/di/eval.py` sub-assessment helper call sites
- Existing smoke coverage in `psi/tools/di_contract_smoke.py`

Summary:
- Reproducibility and comparability sub-assessment derivation paths already use shared deterministic helpers (`reproducibility_signal_from_soe`, `comparability_qc_coherence_summary`).
- No additional extraction was necessary for this patch without increasing replay-risk surface.

Determinism / replay notes:
- No DI functional code changes in `w101`.
- Added smoke lock to preserve sub-assessment helper key-shape/order guarantees.

Follow-on (optional, non-urgent):
- If future DI templates add new comparability/reproducibility summaries, route them through `psi/services/di/sub_assessments.py` first to keep policy-visible behavior centralized.
