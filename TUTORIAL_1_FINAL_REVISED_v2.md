# Tutorial 1 — End-to-End PSI Walkthrough (Synthetic CD3 Program)

## Executive Summary
This tutorial is a fully synthetic, code-aligned PSI walkthrough of the scientist loop:

`Experiment task → Result capture → Evidence → Claim → Decision context`

You will:
1. Create one program and six molecules (3 baseline + 3 builder variants).
2. Capture synthetic results across binding, functional, developability, PK, biodistribution proxy, and in vivo efficacy.
3. Convert results into evidence and claims.
4. Generate internal review reports (program, molecule, comparative).
5. Run DI and finish with a code-aligned endpoint: **advance TUT1-A3 to in vivo testing**.

Scope boundary:
- This tutorial ends at **in vivo advancement readiness**.
- It does **not** claim PSI has an IND-enabling approval endpoint.

## Narrative Setup
You are onboarding a synthetic discovery program called **Tutorial 1** for a targeted biologic intended to engage **CD3 on T cells**.

Baseline molecules:
- `TUT1-A`
- `TUT1-B`
- `TUT1-C`

All three begin non-advancing after baseline characterization. You then use Builder from `TUT1-A` to generate:
- `TUT1-A1`
- `TUT1-A2`
- `TUT1-A3`

After iterative capture and review, `TUT1-A3` becomes the strongest candidate for in vivo testing.

## Tutorial Goals
By the end, you will exercise these PSI surfaces in one continuous flow:
- Program workspace, Program Workflow, Development Board
- Molecule workspace and batch context
- Builder (point mutation)
- Result capture and result review
- Evidence, claims, and optional plans
- Reports (`program_report`, `molecule_report`, `molecule_comparative_report`)
- DI run and decision review

## Before You Begin
1. Open PSI in your browser.
2. Use the top navigation as your map:
   - **Programs**: program workspaces and workflow center.
   - **Molecules**: molecule registry/workspaces.
   - **Builder**: sequence design and variant generation.
   - **Reports**: run and review report outputs.
   - **Supporting Surfaces** row: **Batches**, **Results**, **Evidence**, **Claims**, **Plans**, **Decisions**.
3. Keep this orientation in mind:
   - Your home base for most of this tutorial is **Program Workflow** (the page titled `Tutorial 1 Program Workflow`).
4. Practical navigation rule:
   - If you are unsure where you are, click **Programs** in top nav, open `Tutorial 1`, then click **Open Program Workflow**.
5. Data-entry rule:
   - Most experiment captures are batch-scoped. Create batches first.
6. Units rule:
   - Enter explicit units whenever result fields support or expect units.

---

## Phase 1 — Create the Program
### Where to go
1. Click **Programs** in top nav.
2. Click **New Program**.

### What to enter
- **Name**: `Tutorial 1`
- **Description**:
  `Synthetic CD3-targeted biologic tutorial program for end-to-end PSI workflow training.`

### Save
1. Click **Save**.
2. You should now see the **Program Workspace** for Tutorial 1.
3. Confirm `Tutorial 1` appears in the page header.

### Why this matters
This is the top-level container for molecules, tasks, data, evidence, claims, plans, reports, and decisions.

---

## Phase 2 — Create the Initial Molecules
Create three baseline molecules in the same program using **IgG structured sequence inputs**.

### Navigation pattern for this phase
- You will repeat this loop three times:
  1. Open **New Molecule** from the Program workspace.
  2. Save one molecule.
  3. Return to the Program workspace before creating the next molecule.

### Where to go
1. From the Tutorial 1 Program Workspace, click **New Molecule**.
2. On the **New Molecule** form:
   - Fill fields in order: **Program**, **Primary ID**, **Title**.
   - Then set **Molecule format** (this appears below Title; typically the 4th input block on the form) to `IgG`.
3. After choosing `IgG`, the **Structured sequence inputs** section appears.

### Sequence scope note (important)
In this tutorial flow, PSI expects the structured antibody component inputs (`HC1`, `LC1`, optional `HC2`, `LC2`).
You are intentionally entering the component sequences PSI uses in this workflow, not a full Fc-annotated full-length string in the legacy raw sequence box.

### Create `TUT1-A`
Enter:
- **Program**: `Tutorial 1`
- **Primary ID**: `TUT1-A`
- **Title**: `Baseline A`
- **Description (user)**: `Binds CD3`
- **HC1**:
```text
EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISWNSGSITYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCAR
```
- **LC1**:
```text
DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYFTSNLRSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPYTFGQGTKVEIK
```
- Leave `HC2` and `LC2` blank (PSI infers HC2=HC1 and LC2=LC1).

Click **Save**.

After save:
- You will land on the new molecule workspace for `TUT1-A`.
- Return to program context by clicking **Programs** in top nav, then opening `Tutorial 1`.

### Create `TUT1-B`
From the Tutorial 1 Program Workspace, click **New Molecule** again and enter:
- **Primary ID**: `TUT1-B`
- **Title**: `Baseline B`
- **Description (user)**: `Lower quality baseline; expected non-advancing.`
- **HC1**:
```text
EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYALSWVRQAPGKGLEWVSAISWNSGSITYYADSVKGRFTISRDNAKNTLYLQMNSLRAEDTAVYYCAR
```
- **LC1**:
```text
DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYFASNLRSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNSYPYTFGQGTKVEIK
```

Click **Save**, then return to `Tutorial 1` Program Workspace the same way.

### Create `TUT1-C`
From the Tutorial 1 Program Workspace, click **New Molecule** and enter:
- **Primary ID**: `TUT1-C`
- **Title**: `Baseline C`
- **Description (user)**: `Low manufacturability and weak functional profile.`
- **HC1**:
```text
EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISWNSGSITYYADSVKGRFTISRDNVKNTLYLQMNSLRAEDTAVYYCAR
```
- **LC1**:
```text
DIQMTQSPSSLSASVGDRVTITCRASQDISNYLNWYQQKPGKAPKLLIYFTSNLRSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQYNTYPYTFGQGTKVEIK
```

Click **Save**.

### End-of-phase navigation reset
1. Click **Programs** in top nav.
2. Open `Tutorial 1`.
3. Click **Open Program Workflow**.

### Why this matters
These baselines establish realistic blocked starting points and provide a parent for Builder.

---

## Phase 3 — Enter Initial Characterization Data
In this phase, create baseline batches and capture initial characterization data for A/B/C.

### 3.1 Create one batch per baseline molecule
#### Where to go
1. From Program Workflow, click **Back to Program** (header action), or use top nav **Programs** → `Tutorial 1`.
2. Open **Batches** from the Supporting Surfaces row (or go via New Batch links on molecule pages).
3. Click **New Batch**.

#### For each batch
Create one batch each for `TUT1-A`, `TUT1-B`, `TUT1-C`:
- **Molecule**: select target molecule
- **Title**: `Initial characterization batch`
- **Expression notes**: `Synthetic baseline expression run`
- **Purification notes**: `Synthetic baseline purification`
- Click **Save**.

You should now have one batch ID per baseline molecule (`...-001` style IDs; exact suffix is system-generated).

### 3.2 Keep Program Workflow as your operational home base
1. Go to the `Tutorial 1 Program Workflow` page.
2. Keep this page open in one browser tab for repeated result capture.

### 3.3 Capture baseline assay records (A/B/C)
Preferred path:
1. From Program Workflow task tables, open result capture actions when available.
2. If no task row is available yet, use **Results** in Supporting Surfaces → **New Data Record** (or direct `/data/new`) and select Program/Molecule/Batch.

For each record:
1. Set `Program`, `Molecule`, and `Batch`.
2. Set `Domain`, `Data type`, `Method`.
3. Fill Parameters/Results using the inline values below.
4. Click **Save Result Record**.
5. On the Result Review page, confirm structured results and extracted measurements.
6. Use **Continue in Program Workflow**.

Enter at minimum these baseline families:
- Binding affinity (`BINDING/SPR`)
- Functional activation (`CELL_ASSAY/KILLING`)
- Developability (`EXPRESSION/TRANSIENT_HEK`, `SEC/SEC`, `ENDOTOXIN/LAL`)

### Enter the following baseline records

#### `TUT1-A` baseline
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

#### `TUT1-B` baseline
1. `BINDING/SPR`: `kd` 210 nM, `binding_confirmed` yes, `conclusion` fail
2. `CELL_ASSAY/KILLING`: `percent_killing` 24 %, `ec50` 120 nM, `conclusion` fail
3. `EXPRESSION/TRANSIENT_HEK`: `titer_mg_l` 70 mg/L, `total_yield_mg` 11 mg, `conclusion` fail
4. `SEC/SEC`: `monomer_percent` 88.0 %, `hmw_percent` 8.5 %, `lmw_percent` 3.5 %, `conclusion` fail
5. `ENDOTOXIN/LAL`: `value_eu_ml` 8.8 EU/mL, `limit_eu_ml` 5.0 EU/mL, `pass_fail` fail

#### `TUT1-C` baseline
1. `BINDING/SPR`: `kd` 165 nM, `binding_confirmed` yes, `conclusion` borderline
2. `CELL_ASSAY/KILLING`: `percent_killing` 28 %, `ec50` 95 nM, `conclusion` fail
3. `EXPRESSION/TRANSIENT_HEK`: `titer_mg_l` 62 mg/L, `total_yield_mg` 10 mg, `conclusion` fail
4. `SEC/SEC`: `monomer_percent` 91.5 %, `hmw_percent` 6.2 %, `lmw_percent` 2.3 %, `conclusion` borderline
5. `ENDOTOXIN/LAL`: `value_eu_ml` 5.9 EU/mL, `limit_eu_ml` 5.0 EU/mL, `pass_fail` fail

### Why this matters
You create the measurable blocker profile the board/workflow/claims/reports/DI surfaces consume.

---

## Phase 4 — Review Why the Initial Molecules Are Blocked
### Where to go
1. Open the **Development Board** from Program Workflow (`Open Board`) or from Program Workspace.
2. Return to **Program Workflow**.
3. Open each molecule from Program cards/lists for spot-checking.

### What to review
- Board card **Why here** and blocker text.
- Workflow buckets (ready/in progress/blocked/awaiting data entry).
- Molecule sections: “What matters now,” workflow loop, and evidence/data zones.

### Expected baseline posture
- `TUT1-A`: strongest baseline, but still missing/weak on readiness package.
- `TUT1-B`: poor purity/endotoxin plus weak functional signal.
- `TUT1-C`: weak yield and weak functional profile.

### Why this matters
You verify non-advancement before starting variant engineering.

---

## Phase 5 — Use the Builder to Create Improved Variants
Create three children from `TUT1-A` using point mutation.

### Where to go
1. Click **Builder** in top nav.
2. Open **Point Mutation**.
3. Set parent molecule to `TUT1-A`.

### Create `TUT1-A1`
- **Program**: `Tutorial 1`
- **Parent molecule**: `TUT1-A`
- **New primary ID**: `TUT1-A1`
- **New title**: `A variant 1`
- **Target component**: `HC1`
- **Mutations**: `V2I`
- **Rationale**: `Synthetic affinity/function tuning variant.`

Click **Build draft**, verify preview, then **Create molecule from draft**.

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

### Navigation reset after builder actions
1. Click **Programs** in top nav.
2. Open `Tutorial 1`.
3. Click **Open Program Workflow**.

### Why this matters
This exercises lineage-aware molecule generation from a selected parent variant.

---

## Phase 6 — Enter Improved In Vitro Results
Add improved binding, functional, and developability records for A1/A2/A3.

### 6.1 Create one batch per child molecule
1. From Supporting Surfaces, open **Batches**.
2. Create one new batch each for `TUT1-A1`, `TUT1-A2`, `TUT1-A3`.

### 6.2 Capture improved in vitro data
1. Return to `Tutorial 1 Program Workflow`.
2. Start result capture from workflow actions when available; otherwise use **Results** → new record and set Program/Molecule/Batch manually.
3. Enter the inline child in vitro values below.

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

### Enter the following improved in vitro records

#### `TUT1-A1`
- `BINDING/SPR`: `kd` 95 nM, `conclusion` borderline
- `CELL_ASSAY/KILLING`: `percent_killing` 41 %, `ec50` 52 nM, `conclusion` borderline
- `EXPRESSION/TRANSIENT_HEK`: `titer_mg_l` 118 mg/L, `total_yield_mg` 19 mg, `conclusion` pass
- `SEC/SEC`: `monomer_percent` 95.1 %, `hmw_percent` 3.6 %, `lmw_percent` 1.3 %, `conclusion` pass
- `ENDOTOXIN/LAL`: `value_eu_ml` 4.8 EU/mL, `limit_eu_ml` 5.0 EU/mL, `pass_fail` pass

#### `TUT1-A2`
- `BINDING/SPR`: `kd` 72 nM, `conclusion` pass
- `CELL_ASSAY/KILLING`: `percent_killing` 49 %, `ec50` 38 nM, `conclusion` pass
- `EXPRESSION/TRANSIENT_HEK`: `titer_mg_l` 132 mg/L, `total_yield_mg` 22 mg, `conclusion` pass
- `SEC/SEC`: `monomer_percent` 96.4 %, `hmw_percent` 2.5 %, `lmw_percent` 1.1 %, `conclusion` pass
- `ENDOTOXIN/LAL`: `value_eu_ml` 3.9 EU/mL, `limit_eu_ml` 5.0 EU/mL, `pass_fail` pass

#### `TUT1-A3` (lead)
- `BINDING/SPR`: `kd` 58 nM, `binding_confirmed` yes, `conclusion` pass
- `CELL_ASSAY/KILLING`: `percent_killing` 63 %, `ec50` 24 nM, `conclusion` pass
- `EXPRESSION/TRANSIENT_HEK`: `titer_mg_l` 148 mg/L, `total_yield_mg` 27 mg, `conclusion` pass
- `SEC/SEC`: `monomer_percent` 97.2 %, `hmw_percent` 1.9 %, `lmw_percent` 0.9 %, `conclusion` pass
- `ENDOTOXIN/LAL`: `value_eu_ml` 2.7 EU/mL, `limit_eu_ml` 5.0 EU/mL, `pass_fail` pass

### Why this matters
These records create the comparative package used by evidence, reports, and DI context.

---

## Phase 7 — Enter PK Data
PK uses explicit `PK_PD` data-entry schema paths.

### Where to go
1. Open `Tutorial 1 Program Workflow`.
2. For each child molecule/batch, open result capture (workflow entry preferred).

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

### Enter PK records for each child molecule

#### `TUT1-A1`
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

#### `TUT1-A2`
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

#### `TUT1-A3`
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

### Note
Current DI policy optional PK gates and PK form keys are not fully one-to-one. Keep PK capture for scientific/report coverage and decision context.

---

## Phase 8 — Enter Biodistribution Data
Biodistribution is entered through the **PK/PD pathway** in current PSI (proxy pattern), not as a separate first-class data type.

### Where to go
1. Open `Tutorial 1 Program Workflow`.
2. Open result capture for the relevant child batch (at minimum `TUT1-A3`).

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

### Enter biodistribution proxy records for each child molecule

#### `TUT1-A1`
- Parameters: `matrix=tissue`, `species=mouse`, `route=IV`, `dose_mg_kg=3`
- Results:
  - `pd_marker`: `CD3+ tissue uptake`
  - `pd_effect`: `Spleen 24h: 4.1 %ID/g; LN 24h: 1.8 %ID/g; liver 24h: 1.1 %ID/g`
  - `conclusion`: `borderline`

#### `TUT1-A2`
- Parameters: `matrix=tissue`, `species=mouse`, `route=IV`, `dose_mg_kg=3`
- Results:
  - `pd_marker`: `CD3+ tissue uptake`
  - `pd_effect`: `Spleen 24h: 5.4 %ID/g; LN 24h: 2.6 %ID/g; liver 24h: 1.0 %ID/g`
  - `conclusion`: `pass`

#### `TUT1-A3`
- Parameters: `matrix=tissue`, `species=mouse`, `route=IV`, `dose_mg_kg=3`
- Results:
  - `pd_marker`: `CD3+ tissue uptake`
  - `pd_effect`: `Spleen 24h: 6.8 %ID/g; LN 24h: 3.1 %ID/g; liver 24h: 0.9 %ID/g`
  - `conclusion`: `pass`

### Why this matters
This is the current code-aligned way to carry biodistribution-like context into PSI data/report/evidence workflows.

---

## Phase 9 — Enter In Vivo Efficacy Data
In vivo efficacy is explicitly modeled in PSI.

### Where to go
1. Open `Tutorial 1 Program Workflow`.
2. Capture in vivo records for selected child molecules (A1/A2/A3; at minimum A3).

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

### Enter in vivo efficacy records for each child molecule

#### `TUT1-A1`
- `primary_outcome_value`: 49
- `primary_outcome_units`: %TGI
- `effect_size`: 1.2
- `hazard_ratio`: 0.81
- `p_value`: 0.08
- `survival_median_days`: 36
- `responders_n`: 2
- `notes_interpretation`: `Signal present but not yet robust.`
- `conclusion`: borderline

#### `TUT1-A2`
- `primary_outcome_value`: 63
- `primary_outcome_units`: %TGI
- `effect_size`: 1.5
- `hazard_ratio`: 0.69
- `p_value`: 0.02
- `survival_median_days`: 42
- `responders_n`: 4
- `notes_interpretation`: `Consistent efficacy improvement over A1.`
- `conclusion`: pass

#### `TUT1-A3`
- `primary_outcome_value`: 78
- `primary_outcome_units`: %TGI
- `effect_size`: 1.8
- `hazard_ratio`: 0.58
- `p_value`: 0.004
- `survival_median_days`: 48
- `responders_n`: 6
- `notes_interpretation`: `Robust efficacy with acceptable variability.`
- `conclusion`: pass

---

## Phase 10 — Create Evidence and Claims

### 10.1 Create evidence from captured results
#### Where to go
1. Open a result detail page from Program Workflow, Results list, or molecule data links.
2. Click **Create Evidence (cite this)**.

#### Evidence entry pattern
On the evidence form:
- Set scope (`program`, optional `molecule`, optional `batch`).
- Choose `Domain` and `Evidence type`.
- Enter `Strength` (0–4), `Summary`, and `Details`.
- In citation selection, check eligible Data Records.
- Save.

Create at least these evidence records:
1. **Binding_Affinity** citing A3 `BINDING/SPR`
2. **InVitro_Potency** citing A3 `CELL_ASSAY/KILLING`
3. **Purity_SEC** citing A3 `SEC/SEC`
4. **InVivo_Efficacy** citing A3 `IN_VIVO_EFFICACY/NOD`

Use the following inline summary/detail text so entries are consistent:

1. **Binding_Affinity**
   - `Strength`: `3`
   - `Summary`: `A3 shows strongest CD3 binding affinity in the engineered set.`
   - `Details`: `SPR KD improved to 58 nM versus A1/A2 and baseline molecules; binding confirmed.`
2. **InVitro_Potency**
   - `Strength`: `3`
   - `Summary`: `A3 has strongest functional killing and potency in vitro.`
   - `Details`: `Killing increased to 63% with EC50 24 nM, outperforming all other tutorial variants.`
3. **Purity_SEC**
   - `Strength`: `2`
   - `Summary`: `A3 developability profile supports continued progression.`
   - `Details`: `SEC monomer 97.2% with low HMW/LMW; endotoxin result is within tutorial acceptance range.`
4. **InVivo_Efficacy**
   - `Strength`: `4`
   - `Summary`: `A3 demonstrates robust in vivo efficacy in the tutorial model.`
   - `Details`: `Primary outcome 78 %TGI, favorable hazard ratio and p-value, with highest responder count among children.`

Note: PK/PD records remain visible in result/report surfaces, but evidence citation eligibility depends on registry source-mapping rules.

### 10.2 Create claims
#### Where to go
- Open **Claims** from Supporting Surfaces, then click **New Claim**.

Create at least these claims:
1. **A3 in vivo readiness claim**
   - Molecule: `TUT1-A3`
   - Title: `TUT1-A3 is suitable to advance to in vivo testing`
   - Claim type: `in_vivo_readiness`
   - Description: `Integrated in vitro, developability, PK/PD proxy, and efficacy data support in vivo advancement.`

2. **Developability claim**
   - Molecule: `TUT1-A3`
   - Claim type: `developability`
   - Description: `SEC and endotoxin profiles are within acceptable exploratory bounds.`

After creation, open each claim detail and optionally transition lifecycle status (`hypothesis → emerging → supported`) to match your synthetic evidence posture.

### 10.3 Optional but useful: create a plan
#### Where to go
- Open **Plans** from Supporting Surfaces, then click **New Plan**.

Suggested plan:
- Scope type: `molecule`
- Molecule: `TUT1-A3`
- Title: `A3 in vivo advancement package`
- Plan type: `readiness_advancement`
- Rationale: `Consolidate strongest supporting data and finalize transition into in vivo execution.`

Open the plan detail and optionally transition `draft → recommended → accepted`.

---

## Phase 11 — Generate Reports for Program Review
Use this as an internal company/board-style checkpoint.

### Where to go
- Click **Reports** in top nav, then **New Report**.

### Report 1: program report
1. `Report type`: `program_report`
2. Select Program `Tutorial 1`.
3. Click **Generate**.
4. Review the generated report detail page.

### Report 2: molecule report (single lead)
1. `Report type`: `molecule_report`
2. Program: `Tutorial 1`
3. Molecule: `TUT1-A3`
4. Click **Generate**.
5. Review molecule fact-sheet and narrative sections.

### Report 3: comparative molecules report
1. `Report type`: `molecule_comparative_report`
2. Program: `Tutorial 1`
3. Molecules: `TUT1-A1`, `TUT1-A2`, `TUT1-A3`
4. Click **Generate**.
5. Review side-by-side performance for internal review discussion.

### Meeting-style interpretation checkpoint
Use the three reports plus Program Workflow and Board to answer:
- Which molecule has strongest integrated profile?
- Which blockers are still open?
- Is there enough support to advance A3 to in vivo testing?

---

## Phase 12 — Run the Final Decision Flow
Final endpoint: code-aligned recommendation to advance `TUT1-A3` to in vivo testing.

### 12.1 Run DI snapshot
#### Where to go
- Open **Decisions** (Supporting Surfaces) or go directly to the DI run page.

#### Inputs
- **Scope type**: `molecule`
- **Molecule**: `TUT1-A3`
- **Decision key**: `advance_to_in_vivo`
- **Policy package**: latest `advance_to_in_vivo` (default is fine)
- **QC mode**: `model_safe`
- **As-of timestamp**: leave blank for latest

Click **Run DI**.

### 12.2 Review decision detail
On the decision page, review:
- `decision_state`
- gate outcomes and blockers
- evidence posture summary
- recommended experiments/missing evidence (if any)

### 12.3 Record final tutorial conclusion
Using the result records entered in Phases 3 and 6–9, expected tutorial conclusion is:
- **Recommend advancing `TUT1-A3` to in vivo testing**.

Optionally add DI review notes with rationale such as:
`A3 meets current synthetic readiness package for in vivo advancement; proceed to in vivo testing workflow.`

---

## Expected Final State
By completion, you should have:
1. Program `Tutorial 1` with 6 molecules.
2. Baseline molecules (`TUT1-A/B/C`) represented as blocked/non-advancing.
3. Builder-derived children (`TUT1-A1/A2/A3`) with progressive improvements.
4. Structured records across required families:
   - binding affinity
   - functional activation
   - developability
   - PK
   - biodistribution proxy
   - in vivo efficacy
5. Evidence entries citing eligible Data Records.
6. Claims (and optional plan) capturing scientific posture.
7. Program, molecule, and comparative report runs.
8. DI snapshot and final recommendation to advance `TUT1-A3` to in vivo testing.

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

## Revision Notes
This revision keeps the synthetic scientific dataset unchanged while improving scientist-facing usability:
- Replaced route-heavy phrasing in main steps with visible UI wording (Program Workspace, Program Workflow, Development Board, Supporting Surfaces).
- Added explicit navigation resets and return-path instructions between Program, Molecule, Batch, Workflow, and Result Review pages.
- Added inline HC1/LC1 sequence blocks at molecule creation so users do not need to repeatedly scroll to appendices.
- Clarified molecule-form field order, including where **Molecule format** appears on the New Molecule form.
- Reworded early TUT1-A baseline description to a neutral, non-forward-looking statement.

Current PSI UI limitations that the tutorial compensates for:
- Molecule pages do not always present a single obvious “Back to Program” primary button, so the tutorial explicitly uses top-nav **Programs** as the reliable return path.
- Some flows can be entered from multiple surfaces (workflow rows, registries, direct forms), so the tutorial repeatedly anchors back to Program Workflow as the operational home base.
- Biodistribution remains a PK/PD proxy entry pattern rather than a dedicated first-class biodistribution form.
