# PSI_EXAMPLES dataset

This overlay adds a **seed fixture + seeding tool** that populates a realistic example portfolio into your PSI database.

## What you get
- Program: `PSI_EXAMPLES`
- 24 molecules (12 per target: `INT_SENS` and `MONO`)
- 1–3 batches per molecule (37 batches total)
- 163 DataRecords spanning PROCESS/CMC/BIO with realistic + “cartoon extreme” failures
- A handful of QC events marking outliers / failures as **quarantined** or **rejected** (so DI can learn to ignore)

## Install (ZIP overlay)
Apply this zip overlay onto your repo (same workflow as other PSI code-only updates), e.g.:

```bash
cd ~/psi_repo
rsync -avh --ignore-existing <unzipped_overlay_root>/ ./ 
```

(Or use your usual `apply_zip_update.sh`.)

## Seed the DB
From repo root (venv active):

```bash
python -m psi.tools.seed_psi_examples --db ./psi.sqlite
```

If you already use `PSI_DB_PATH`, you can omit `--db`.

Re-running is safe-ish:
- It will not delete anything.
- It will skip molecules with the same `primary_id`.
- It will skip batch titles already present under that molecule.
- It will skip DataRecords with the same `(batch_id, title)`.

## Notes
- Sequences are synthetic but antibody-shaped (HC ~449 aa, LC ~210 aa).
- The dataset is designed to exercise:
  - chain registry (SequenceEntity / CHAIN IDs)
  - measurement extraction (data_measurements)
  - QC event logging + ignore policies

