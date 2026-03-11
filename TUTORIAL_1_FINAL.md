# Tutorial 1 — End-to-End PSI Walkthrough (Synthetic CD3 Program)

## Executive Summary
This tutorial is a fully synthetic, code-aligned walkthrough of PSI’s scientist workflow:

`Experiment task → Result capture → Evidence → Claim → Decision context`

You will:
1. Create a program and six molecules (3 baseline + 3 builder-derived variants).
2. Enter realistic synthetic assay results across binding, functional, developability, PK, biodistribution proxy, and in vivo efficacy.
3. Create evidence and claims from those results.
4. Generate program/molecule/comparative reports for an internal review checkpoint.
5. Run DI and finish with a code-aligned final outcome:
   **advance TUT1-A3 to in vivo testing**.

Important scope boundary:
- This tutorial intentionally stops at **in vivo advancement readiness**.
- It does **not** claim a native PSI endpoint for IND-enabling authorization.

## Narrative Setup
You are onboarding a synthetic discovery program called **Tutorial 1** for a targeted biologic intended to engage **CD3 on T cells**.

Baseline molecules:
- `TUT1-A`
- `TUT1-B`
- `TUT1-C`

All three start non-advancing. `TUT1-A` is the best blocked parent. You use Builder to generate:
- `TUT1-A1`
- `TUT1-A2`
- `TUT1-A3`

After iterative result capture and review, `TUT1-A3` emerges as the strongest candidate to advance to in vivo testing.

## Tutorial Goals
By the end, you will have exercised these PSI surfaces in one flow:
- Program, Molecule, Batch
- Builder (point mutation flow)
- Program Workflow + Development Board
- Data entry (`/data/new`) and Data detail
- Evidence capture and citation filters
- Claim and Plan pages
- Reports (`program_report`, `molecule_report`, `molecule_comparative_report`)
- DI snapshot run and decision detail review

## Before You Begin
1. Open PSI in your browser.
2. Confirm top-level pages are reachable:
   - `/programs`
   - `/molecules`
   - `/builder`
   - `/data`
   - `/evidence`
   - `/reports`
   - `/di/run`
3. Operational rule for this tutorial:
   - Use **Program Workflow** (`/programs/{program_id}/workflow`) as your primary navigation hub.
4. Data-entry rule:
   - Most experimental data types are batch-scoped; create batches before assay entry.
5. Units rule:
   - Enter explicit units wherever form fields support units (or where unit text fields are provided).

---

## Phase 1 — Create the Program
### Where to go
1. Go to `/programs`.
2. Click **New Program**.

### What to enter
- **Name**: `Tutorial 1`
- **Description**:
  `Synthetic CD3-targeted biologic tutorial program for end-to-end PSI workflow training.`

### Save
- Click **Save**.
- You should land on `/programs/{program_id}`.

### Why this matters
This creates the top-level container for molecules, tasks, evidence, claims, plans, and reports.

---

## Phase 2 — Create the Initial Molecules
Create three baseline molecules in the same program using IgG structured sequence entry.

### Where to go
1. From program detail, click **New Molecule** (or go to `/molecules/new?program_id={program_id}`).
2. Set **Molecule format** = `IgG`.

### Create `TUT1-A`
- **Program**: `Tutorial 1`
- **Primary ID**: `TUT1-A`
- **Title**: `Baseline A`
- **Description (user)**: `Best baseline parent candidate; still blocked.`
- **HC1**: use Appendix A sequence for `TUT1-A`.
- **LC1**: use Appendix A sequence for `TUT1-A`.
- Leave HC2/LC2 blank (PSI infers HC2=HC1, LC2=LC1).
- Click **Save**.

### Create `TUT1-B`
Repeat with:
- **Primary ID**: `TUT1-B`
- **Title**: `Baseline B`
- **Description (user)**: `Lower quality baseline; expected non-advancing.`
- HC1/LC1 from Appendix A.

### Create `TUT1-C`
Repeat with:
- **Primary ID**: `TUT1-C`
- **Title**: `Baseline C`
- **Description (user)**: `Low manufacturability and weak functional profile.`
- HC1/LC1 from Appendix A.

### Why this matters
These baselines provide realistic blocked starting points and a parent candidate for Builder.

---

## Phase 3 — Enter Initial Characterization Data
In this phase, create initial batches and capture baseline characterization for A/B/C.

### 3.1 Create one batch per baseline molecule
#### Where to go
1. Go to `/batches/new`.
2. Create one batch for each baseline molecule.

#### For each batch
- **Molecule**: select `TUT1-A` (then `TUT1-B`, then `TUT1-C`)
- **Title**: `Initial characterization batch`
- **Expression notes**: `Synthetic baseline expression run`
- **Purification notes**: `Synthetic baseline purification`
- Click **Save**.

You should now have one batch ID per molecule (for example `TUT1-A-001`, etc.; exact numbering is system-generated).

### 3.2 Use Program Workflow as entry hub
1. Go to `/programs/{program_id}/workflow`.
2. Keep this page as your operational home base.

### 3.3 Capture baseline assay records (A/B/C)
Use `/data/new` from workflow context. If no task row exists, use direct navigation with workflow return path:

`/data/new?program_id={program_id}&molecule_id={molecule_id}&batch_id={batch_id}&source=workflow&return_to=/programs/{program_id}/workflow`

For each record:
1. Select `Program`, `Molecule`, `Batch`.
2. Set `Domain`, `Data type`, `Method`.
3. Fill structured Parameters/Results fields.
4. Click **Save Result Record**.
5. Review the created record at `/data/{record_id}`.
6. Return to workflow.

Use Appendix B values for all entries. At minimum enter these baseline families:
- Binding affinity (`BINDING/SPR`)
- Functional activation (`CELL_ASSAY/KILLING`)
- Developability (`SEC/SEC`, `ENDOTOXIN/LAL`, and expression yield via `EXPRESSION/TRANSIENT_HEK`)

### Why this matters
This establishes measurable blockers in the same schemas DI and reports use.

---

## Phase 4 — Review Why the Initial Molecules Are Blocked
### Where to go
1. Open `/programs/{program_id}/board`.
2. Open `/programs/{program_id}/workflow`.
3. Spot-check each molecule at `/molecules/{id}`.

### What to review
- Board card **Why here** and blocker text.
- Workflow buckets (ready/in progress/blocked/awaiting data).
- Molecule “what matters now” and evidence/data sections.

### Expected baseline posture
- `TUT1-A`: best of baseline but still missing/weak in key readiness areas.
- `TUT1-B`: poor purity/endotoxin + weak functional signal.
- `TUT1-C`: weak yield/functional profile.

### Why this matters
You verify baseline non-advancement before engineering variants.

---

## Phase 5 — Use the Builder to Create Improved Variants
Create three children from `TUT1-A` via point mutation flow.

### Where to go
1. Go to `/builder/point-mutation`.
2. Set parent molecule to `TUT1-A`.

### Create `TUT1-A1`
- **Program**: Tutorial 1
- **Parent molecule**: `TUT1-A`
- **New primary ID**: `TUT1-A1`
- **New title**: `A variant 1`
- **Target component**: `HC1`
- **Mutations**: `V2I`
- **Rationale**: `Synthetic affinity/function tuning variant.`
- Click **Build draft** → verify preview → **Create molecule from draft**.

### Create `TUT1-A2`
Repeat with:
- **New primary ID**: `TUT1-A2`
- **Mutations**: `A50G`
- **Rationale**: `Synthetic developability-adjusted variant.`

### Create `TUT1-A3`
Repeat with:
- **New primary ID**: `TUT1-A3`
- **Mutations**: `E90Q`
- **Rationale**: `Synthetic lead candidate variant.`

### Optional workflow integration step
After creating each child, return to `/programs/{program_id}/workflow` and confirm molecules appear in program surfaces.

### Why this matters
This exercises deterministic lineage from parent to engineered children using Builder.

---

## Phase 6 — Enter Improved In Vitro Results
Add improved binding, functional, and developability records for A1/A2/A3.

### 6.1 Create one batch per child molecule
Go to `/batches/new` and create one batch each for `TUT1-A1`, `TUT1-A2`, `TUT1-A3`.

### 6.2 Capture improved in vitro data
From `/programs/{program_id}/workflow`, enter records on `/data/new` for each child batch using Appendix B.

Include these families per child:
1. **Binding affinity**: `BINDING / SPR`
2. **Functional activation**: `CELL_ASSAY / KILLING`
3. **Developability**:
   - `EXPRESSION / TRANSIENT_HEK` (titer / total yield)
   - `SEC / SEC` (monomer/HMW/LMW)
   - `ENDOTOXIN / LAL` (include legacy keys `value_eu_ml`, `limit_eu_ml`)

### Scientific target pattern
- `TUT1-A1`: moderate improvement.
- `TUT1-A2`: better than A1.
- `TUT1-A3`: strongest in vitro package.

### Why this matters
These records support both scientific interpretation and DI gating metrics.

---

## Phase 7 — Enter PK Data
PK is captured through explicit `PK_PD` schemas.

### Where to go
1. Start at `/programs/{program_id}/workflow`.
2. Open `/data/new` for each target molecule/batch (preferably A1/A2/A3).

### Form selection
- **Domain**: `BIO`
- **Data type**: `PK_PD`
- **Method**: `NONCOMPARTMENTAL` (or `COMPARTMENTAL`)

### Fields to fill (example for A3)
- Parameters:
  - `species`: mouse
  - `matrix`: plasma
  - `dose_mg_kg`: 3
  - `route`: IV
  - `sampling_schedule`: `0.5, 2, 6, 24, 72 h`
- Results:
  - `cmax`: 18.7
  - `cmax_units`: `ug/mL`
  - `tmax_h`: 0.5
  - `auc`: 132.0
  - `auc_units`: `ug*h/mL`
  - `half_life_h`: 38
  - `pk_t12_h`: 38
  - `clearance`: 0.31
  - `clearance_units`: `mL/h/kg`
  - `vd`: 0.62
  - `vd_units`: `L/kg`
  - `conclusion`: `pass`

Use Appendix B for A1/A2/A3 values.

### Note
Current DI policy optional PK gate references keys like `half_life_days` and `cmax_ug_ml`; PK form fields use `half_life_h` and `cmax` plus explicit unit fields. Keep PK in tutorial for scientific/report coverage, not as sole DI pass determinant.

---

## Phase 8 — Enter Biodistribution Data
Biodistribution is represented via the PK/PD pathway (proxy pattern), not a dedicated first-class biodistribution data type.

### Where to go
1. Start at `/programs/{program_id}/workflow`.
2. Open `/data/new` for the relevant child molecule batch (at minimum `TUT1-A3`).

### Form selection
- **Domain**: `BIO`
- **Data type**: `PK_PD`
- **Method**: `NONCOMPARTMENTAL`

### Biodistribution proxy pattern (A3 example)
- Parameters:
  - `matrix`: `tissue`
  - `species`: `mouse`
  - `route`: `IV`
  - `sampling_schedule`: `4, 24, 72 h tissue panel`
- Results:
  - `pd_marker`: `CD3+ spleen uptake`
  - `pd_effect`: `Spleen 24h: 6.8 %ID/g; LN 24h: 3.1 %ID/g; liver 24h: 0.9 %ID/g`
  - `conclusion`: `pass`

Use Appendix B for exact values.

### Why this matters
It keeps biodistribution tutorial coverage code-aligned with current PK/PD schema support.

---

## Phase 9 — Enter In Vivo Efficacy Data
In vivo efficacy is explicitly modeled in PSI.

### Where to go
1. Start at `/programs/{program_id}/workflow`.
2. Open `/data/new` for selected child molecules (A1/A2/A3; at minimum A3).

### Form selection
- **Domain**: `BIO`
- **Data type**: `IN_VIVO_EFFICACY`
- **Method**: `NOD` (or `OTHER_MOUSE`)

### A3 efficacy example
- Parameters:
  - `model`: `NOD tumor xenograft`
  - `n_per_group`: 10
  - `dose_mg_kg`: 3
  - `route`: `IV`
  - `schedule`: `Q3D x5`
  - `duration_days`: 28
  - `endpoint_primary`: `tumor growth inhibition`
- Results:
  - `primary_outcome_value`: 78
  - `primary_outcome_units`: `%TGI`
  - `effect_size`: 1.8
  - `hazard_ratio`: 0.58
  - `p_value`: 0.004
  - `survival_median_days`: 48
  - `responders_n`: 6
  - `notes_interpretation`: `Robust efficacy with acceptable variability.`
  - `conclusion`: `pass`

Use Appendix B for A1/A2/A3 comparison values.

---

## Phase 10 — Create Evidence and Claims

### 10.1 Create Evidence from captured results
#### Where to go
1. Open a result detail page: `/data/{record_id}`.
2. Click **Create or Link Evidence** (opens `/evidence/new?...`).

#### Evidence creation pattern
On evidence form:
- Set scope (`program`, optional `molecule`, optional `batch`).
- Choose `Domain` and `Evidence type`.
- Enter `Strength` (0–4), `Summary`, and `Details`.
- In Step 1 citation section, check eligible Data Records.
- Save.

Create at least these evidence records:
1. **Binding_Affinity** citing A3 `BINDING/SPR`
2. **InVitro_Potency** citing A3 `CELL_ASSAY/KILLING`
3. **Purity_SEC** citing A3 `SEC/SEC`
4. **InVivo_Efficacy** citing A3 `IN_VIVO_EFFICACY/NOD`

Note: PK/PD records are visible in data/report surfaces, but evidence citation eligibility is constrained by registry mapping per evidence type.

### 10.2 Create Claims
#### Where to go
- Go to `/claims/new`.

#### Create these claims (minimum)
1. **A3 in vivo readiness claim**
   - Molecule: `TUT1-A3`
   - Title: `TUT1-A3 is suitable to advance to in vivo testing`
   - Claim type: `in_vivo_readiness`
   - Description: `Integrated in vitro, developability, PK/PD proxy, and efficacy data support in vivo advancement.`

2. **Developability claim**
   - Molecule: `TUT1-A3`
   - Claim type: `developability`
   - Description: `SEC and endotoxin profiles are within acceptable exploratory bounds.`

After creation, open each claim detail and, if desired, use lifecycle transition controls (`hypothesis → emerging → supported`) based on your synthetic evidence narrative.

### 10.3 (Optional but useful) Create a Plan
#### Where to go
- Go to `/plans/new`.

#### Suggested plan
- Scope type: `molecule`
- Molecule: `TUT1-A3`
- Title: `A3 in vivo advancement package`
- Plan type: `readiness_advancement`
- Rationale: `Consolidate strongest supporting data and finalize transition into in vivo execution.`

Then open `/plans/{plan_id}` and transition `draft → recommended → accepted` if desired.

---

## Phase 11 — Generate Reports for Program Review
Use this as an internal review / board-meeting checkpoint.

### Where to go
- Go to `/reports/new`.

### Report 1: Program report
1. `Report type`: `program_report`
2. Select **Tutorial 1** in Program selector.
3. Click **Generate**.
4. Review `/reports/{id}` for overall program state.

### Report 2: Molecule report (single lead)
1. `Report type`: `molecule_report`
2. Select Program `Tutorial 1`.
3. Select Molecule `TUT1-A3`.
4. Click **Generate**.
5. Review fact sheet and narrative context for A3.

### Report 3: Comparative molecules report
1. `Report type`: `molecule_comparative_report`
2. Select Program `Tutorial 1`.
3. Multi-select molecules: `TUT1-A1`, `TUT1-A2`, `TUT1-A3`.
4. Click **Generate**.
5. Use this as the head-to-head comparison during review.

### What to conclude in this checkpoint
- A3 has strongest integrated package.
- A1/A2 show progression but weaker combined profile.
- Baseline A/B/C remain non-advancing compared to engineered set.

---

## Phase 12 — Run the Final Decision Flow
Final endpoint: code-aligned recommendation to advance `TUT1-A3` to in vivo testing.

### 12.1 Run DI snapshot
#### Where to go
- Go to `/di/run`.

#### Inputs
- **Scope type**: `molecule`
- **Molecule**: `TUT1-A3`
- **Decision key**: `advance_to_in_vivo`
- **Policy package**: latest `advance_to_in_vivo` (default selection is acceptable)
- **QC mode**: `model_safe`
- **As-of timestamp**: leave blank (latest)

Click **Run DI**.

You will be redirected to `/decisions/{snapshot_id}`.

### 12.2 Review decision detail
On decision detail, review:
- `decision_state`
- gate outcomes and blockers
- state-of-evidence summary
- recommended experiments/missing evidence (if any)

### 12.3 Record the final tutorial conclusion
If A3 data were entered per Appendix B, expected tutorial conclusion is:
- **Recommend advancing `TUT1-A3` to in vivo testing**.

You can capture this explicitly in DI review controls on decision detail:
- Add DI review verdict (for example `useful`)
- Add rationale text such as:
  `A3 meets current synthetic readiness package for in vivo advancement; proceed to in vivo testing workflow.`

---

## Expected Final State
By tutorial completion, you should have:
1. Program `Tutorial 1` with 6 molecules.
2. Baseline molecules (`TUT1-A/B/C`) represented as blocked/non-advancing.
3. Builder-derived children (`TUT1-A1/A2/A3`) with progressive improvements.
4. Structured records across all required families:
   - binding affinity
   - functional activation
   - developability
   - PK
   - biodistribution proxy
   - in vivo efficacy
5. Evidence entries citing eligible Data Records.
6. Claims (and optional plan) on A3 scientific posture.
7. Program, molecule, and comparative report runs.
8. DI snapshot and final recommendation to advance `TUT1-A3` to in vivo testing.

---

## Appendix A — Synthetic Sequences Used

All sequences are synthetic and tutorial-only.

### TUT1-A (parent)
- **HC1**
```text
EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISWNSGSITYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCAR
```
- **LC1**
```text
DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYFTSNLRSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPYTFGQGTKVEIK
```

### TUT1-B
- **HC1**
```text
EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYALSWVRQAPGKGLEWVSAISWNSGSITYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCAR
```
- **LC1**
```text
DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYFASNLRSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPYTFGQGTKVEIK
```

### TUT1-C
- **HC1**
```text
EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISWNSGSITYYADSVKGRFTISRDNVKNTLYLQMNSLRAEDTAVYYCAR
```
- **LC1**
```text
DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYFTSNLRSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNTYPYTFGQGTKVEIK
```

### Builder-derived children from TUT1-A

#### TUT1-A1
- Mutation: `HC1 V2I`
- HC1:
```text
EIQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISWNSGSITYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCAR
```
- LC1: same as TUT1-A

#### TUT1-A2
- Mutation: `HC1 A50G`
- HC1:
```text
EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSGISWNSGSITYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCAR
```
- LC1: same as TUT1-A

#### TUT1-A3
- Mutation: `HC1 E90Q`
- HC1:
```text
EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISWNSGSITYYADSVKGRFTISRDNAKNTLYLQMNSLRAQDTAVYYCAR
```
- LC1: same as TUT1-A

---

## Appendix B — Synthetic Datasets and Units

Use these values when entering records in `/data/new`.

### B.1 Baseline set (blocked profile)

#### TUT1-A baseline
1. **Binding** (`BINDING/SPR`)
   - `kd`: 140 nM
   - `ka`: 8.2e4 1/M·s
   - `kdiss`: 1.1e-2 1/s
   - `binding_confirmed`: yes
   - `conclusion`: borderline

2. **Functional** (`CELL_ASSAY/KILLING`)
   - `percent_killing`: 32 %
   - `ec50`: 78 nM
   - `conclusion`: borderline

3. **Expression** (`EXPRESSION/TRANSIENT_HEK`)
   - `titer_mg_l`: 95 mg/L
   - `total_yield_mg`: 16 mg
   - `viability_percent`: 82 %
   - `conclusion`: borderline

4. **SEC** (`SEC/SEC`)
   - `monomer_percent`: 94.2 %
   - `hmw_percent`: 4.1 %
   - `lmw_percent`: 1.7 %
   - `conclusion`: borderline

5. **Endotoxin** (`ENDOTOXIN/LAL`)
   - `value_eu_ml`: 6.2 EU/mL
   - `limit_eu_ml`: 5.0 EU/mL
   - `pass_fail`: fail

#### TUT1-B baseline
1. `BINDING/SPR`: `kd` 210 nM, `binding_confirmed` yes, `conclusion` fail
2. `CELL_ASSAY/KILLING`: `percent_killing` 24 %, `ec50` 120 nM, `conclusion` fail
3. `EXPRESSION/TRANSIENT_HEK`: `titer_mg_l` 70 mg/L, `total_yield_mg` 11 mg, `conclusion` fail
4. `SEC/SEC`: `monomer_percent` 88.0 %, `hmw_percent` 8.5 %, `lmw_percent` 3.5 %, `conclusion` fail
5. `ENDOTOXIN/LAL`: `value_eu_ml` 8.8 EU/mL, `limit_eu_ml` 5.0 EU/mL, `pass_fail` fail

#### TUT1-C baseline
1. `BINDING/SPR`: `kd` 165 nM, `binding_confirmed` yes, `conclusion` borderline
2. `CELL_ASSAY/KILLING`: `percent_killing` 28 %, `ec50` 95 nM, `conclusion` fail
3. `EXPRESSION/TRANSIENT_HEK`: `titer_mg_l` 62 mg/L, `total_yield_mg` 10 mg, `conclusion` fail
4. `SEC/SEC`: `monomer_percent` 91.5 %, `hmw_percent` 6.2 %, `lmw_percent` 2.3 %, `conclusion` borderline
5. `ENDOTOXIN/LAL`: `value_eu_ml` 5.9 EU/mL, `limit_eu_ml` 5.0 EU/mL, `pass_fail` fail

### B.2 Improved in vitro set (children)

#### TUT1-A1
- `BINDING/SPR`: `kd` 95 nM, `conclusion` borderline
- `CELL_ASSAY/KILLING`: `percent_killing` 41 %, `ec50` 52 nM, `conclusion` borderline
- `EXPRESSION/TRANSIENT_HEK`: `titer_mg_l` 118 mg/L, `total_yield_mg` 19 mg, `conclusion` pass
- `SEC/SEC`: `monomer_percent` 95.1 %, `hmw_percent` 3.6 %, `lmw_percent` 1.3 %, `conclusion` pass
- `ENDOTOXIN/LAL`: `value_eu_ml` 4.8 EU/mL, `limit_eu_ml` 5.0 EU/mL, `pass_fail` pass

#### TUT1-A2
- `BINDING/SPR`: `kd` 72 nM, `conclusion` pass
- `CELL_ASSAY/KILLING`: `percent_killing` 49 %, `ec50` 38 nM, `conclusion` pass
- `EXPRESSION/TRANSIENT_HEK`: `titer_mg_l` 132 mg/L, `total_yield_mg` 22 mg, `conclusion` pass
- `SEC/SEC`: `monomer_percent` 96.4 %, `hmw_percent` 2.5 %, `lmw_percent` 1.1 %, `conclusion` pass
- `ENDOTOXIN/LAL`: `value_eu_ml` 3.9 EU/mL, `limit_eu_ml` 5.0 EU/mL, `pass_fail` pass

#### TUT1-A3 (lead)
- `BINDING/SPR`: `kd` 58 nM, `binding_confirmed` yes, `conclusion` pass
- `CELL_ASSAY/KILLING`: `percent_killing` 63 %, `ec50` 24 nM, `conclusion` pass
- `EXPRESSION/TRANSIENT_HEK`: `titer_mg_l` 148 mg/L, `total_yield_mg` 27 mg, `conclusion` pass
- `SEC/SEC`: `monomer_percent` 97.2 %, `hmw_percent` 1.9 %, `lmw_percent` 0.9 %, `conclusion` pass
- `ENDOTOXIN/LAL`: `value_eu_ml` 2.7 EU/mL, `limit_eu_ml` 5.0 EU/mL, `pass_fail` pass

### B.3 PK data (`PK_PD/NONCOMPARTMENTAL`)

#### TUT1-A1
- `cmax`: 12.1
- `cmax_units`: ug/mL
- `tmax_h`: 0.5
- `auc`: 88.5
- `auc_units`: ug*h/mL
- `half_life_h`: 26
- `pk_t12_h`: 26
- `clearance`: 0.45
- `clearance_units`: mL/h/kg
- `vd`: 0.74
- `vd_units`: L/kg
- `conclusion`: borderline

#### TUT1-A2
- `cmax`: 15.4
- `cmax_units`: ug/mL
- `tmax_h`: 0.5
- `auc`: 109.2
- `auc_units`: ug*h/mL
- `half_life_h`: 32
- `pk_t12_h`: 32
- `clearance`: 0.38
- `clearance_units`: mL/h/kg
- `vd`: 0.68
- `vd_units`: L/kg
- `conclusion`: pass

#### TUT1-A3
- `cmax`: 18.7
- `cmax_units`: ug/mL
- `tmax_h`: 0.5
- `auc`: 132.0
- `auc_units`: ug*h/mL
- `half_life_h`: 38
- `pk_t12_h`: 38
- `clearance`: 0.31
- `clearance_units`: mL/h/kg
- `vd`: 0.62
- `vd_units`: L/kg
- `conclusion`: pass

### B.4 Biodistribution proxy (`PK_PD` with `matrix=tissue`)

#### TUT1-A1
- Params: `matrix=tissue`, `species=mouse`, `route=IV`, `dose_mg_kg=3`
- Results:
  - `pd_marker`: CD3+ tissue uptake
  - `pd_effect`: `Spleen 24h: 4.1 %ID/g; LN 24h: 1.8 %ID/g; liver 24h: 1.1 %ID/g`
  - `conclusion`: borderline

#### TUT1-A2
- Results:
  - `pd_marker`: CD3+ tissue uptake
  - `pd_effect`: `Spleen 24h: 5.4 %ID/g; LN 24h: 2.6 %ID/g; liver 24h: 1.0 %ID/g`
  - `conclusion`: pass

#### TUT1-A3
- Results:
  - `pd_marker`: CD3+ tissue uptake
  - `pd_effect`: `Spleen 24h: 6.8 %ID/g; LN 24h: 3.1 %ID/g; liver 24h: 0.9 %ID/g`
  - `conclusion`: pass

### B.5 In vivo efficacy (`IN_VIVO_EFFICACY/NOD`)

#### TUT1-A1
- `primary_outcome_value`: 49
- `primary_outcome_units`: %TGI
- `effect_size`: 1.2
- `hazard_ratio`: 0.81
- `p_value`: 0.08
- `survival_median_days`: 36
- `responders_n`: 2
- `notes_interpretation`: `Signal present but not yet robust.`
- `conclusion`: borderline

#### TUT1-A2
- `primary_outcome_value`: 63
- `primary_outcome_units`: %TGI
- `effect_size`: 1.5
- `hazard_ratio`: 0.69
- `p_value`: 0.02
- `survival_median_days`: 42
- `responders_n`: 4
- `notes_interpretation`: `Consistent efficacy improvement over A1.`
- `conclusion`: pass

#### TUT1-A3
- `primary_outcome_value`: 78
- `primary_outcome_units`: %TGI
- `effect_size`: 1.8
- `hazard_ratio`: 0.58
- `p_value`: 0.004
- `survival_median_days`: 48
- `responders_n`: 6
- `notes_interpretation`: `Robust efficacy with acceptable variability.`
- `conclusion`: pass

### B.6 Example synthetic interpretation text snippets
Use short, realistic entries in notes/details fields:
- `Binding profile improved with preserved specificity in synthetic control panel.`
- `Functional killing and potency now exceed baseline threshold expectations.`
- `Developability signals are within exploratory acceptance range for continued progression.`
- `PK/PD profile supports sustained exposure relative to baseline variants.`
- `Tissue distribution pattern is consistent with intended CD3-targeted activity in this synthetic model.`
- `In vivo efficacy supports progression into in vivo-focused development activities.`

---

## Appendix C — Key PSI Pages Used in This Tutorial

### Core workflow and context
- `/programs`
- `/programs/new`
- `/programs/{program_id}`
- `/programs/{program_id}/workflow`
- `/programs/{program_id}/board`

### Molecules and builder
- `/molecules/new`
- `/molecules/{molecule_id}`
- `/builder`
- `/builder/point-mutation`

### Material and results
- `/batches/new`
- `/batches/{batch_id}`
- `/data/new`
- `/data/{record_id}`
- `/data/{record_id}/edit`

### Evidence, claims, plans
- `/evidence/new`
- `/evidence/{evidence_id}`
- `/claims/new`
- `/claims/{claim_id}`
- `/plans/new`
- `/plans/{plan_id}`

### Reporting and decisions
- `/reports/new`
- `/reports/{report_run_id}`
- `/di/run`
- `/decisions/{snapshot_id}`

### API-backed dynamic helpers used by forms
- `/api/registry`
- `/api/data_records`
- `/api/evidence_allowed_sources`
