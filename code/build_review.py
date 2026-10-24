"""Create a checkable review of the revised analysis, using generated results."""
from pathlib import Path
import json,sqlite3,shutil,subprocess
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/tables'
a=json.loads((OUT/'audit.json').read_text())
ols=pd.read_csv(OUT/'ige_nominal.csv');rr=pd.read_csv(OUT/'rank_rank_same_sample.csv')
inf=pd.read_csv(OUT/'inflation_diagnostic.csv')

def table(df):
    lines=['| Measure | N | Slope | 95% CI |','|---|---:|---:|---:|']
    for r in df.itertuples():lines.append(f'| {r.measure} | {r.n:,} | {r.slope:.3f} | [{r.ci_low:.3f}, {r.ci_high:.3f}] |')
    return '\n'.join(lines)

with sqlite3.connect(f'file:{ROOT}/data/processed/both_parents_nominal.sqlite?mode=ro',uri=True) as c:
    adults=c.execute('SELECT COUNT(*) FROM matched WHERE child_age BETWEEN 19 AND 110 AND mother_age BETWEEN 19 AND 110 AND father_age BETWEEN 19 AND 110').fetchone()[0]

sql=(ROOT/'code/match_parents_children.sql').read_text()
doc=rf'''---
title: "Blog 6: Revised regression and processing review"
subtitle: "Recorded mother + recorded father; nominal individual earnings; rank–rank bonus"
date: 2026-10-22
---

This technical review documents the current individual-earnings specification, its source variables, sample restrictions and validation checks.

## 1. Exact definition used

The parent regressor is the **sum of the recorded mother's own earnings and recorded father's own earnings**. The child outcome is the **child's own earnings**, using the same definition. Both generations are measured in the same income year.

The available PSID generated measures used here are *labor income excluding farm and unincorporated-business income*. They include wages/salaries and listed job-related components, including bonuses, overtime, tips and commissions. They are **not total personal income**: pensions, Social Security, capital income, and the excluded business/farm income are not included. This is an explicitly scoped earnings-based implementation, not a claim that total individual income has been constructed. The role-specific variables can be assigned to current reference persons and spouses; other family members' individual income is not constructed in this run.

The codebooks for all four waves were checked for this same definition. PSID has already assigned missing values in these generated labor-income measures; no additional income imputation was performed here.

## 2. Raw data selected

| File | Fields read | Raw records |
|---|---|---:|
| PID23 | PID2/PID3 child; PID4/PID5 mother; PID23/PID24 father | 103,725 |
| IND2023ER | ER30001/ER30002; each wave's family ID, sequence, relationship, age | 85,536 |
| FAM2017ER | ER66002 family ID; ER71293 RP earnings; ER71321 spouse earnings | 9,607 |
| FAM2019ER | ER72002 family ID; ER77315 RP earnings; ER77343 spouse earnings | 9,569 |
| FAM2021ER | ER78002 family ID; ER81642 RP earnings; ER81670 spouse earnings | 9,207 |
| FAM2023ER | ER82002 family ID; ER85496 RP earnings; ER85524 spouse earnings | 9,152 |

**The PID file establishes parentage; the cross-year Individual File locates those exact individuals in each wave.** A person's ID consists of original family ID plus person number. The importer reads fixed-width raw text using the official `.do` positions and writes selected fields to SQLite. It does not execute Stata or alter the source files. Python reshapes the individual file into person-wave records.

## 3. SQL joins and selection

1. Exclude unknown mother/father identifiers. Person number 999 means identity unclear, not a valid parent ID. An initial validation caught three links where both parents had this unknown code; the explicit filter now handles them.
2. Join each person's current family ID to the Family File **on family ID and wave together**.
3. Assign `rp_earnings` to relationship 10/sequence 1; assign `sp_earnings` to relationship 20 or 22/sequence 2. A mother can be either role; a father can be either role. Sex is not used as a shortcut for household role.
4. Join the child, mother and father using their two-field identifiers in the same wave.
5. Add mother and father earnings **once each**. They may share a household or live separately. Never add household totals and never substitute the current spouse for the recorded biological parent.
6. Require all three to be observed adults (interview ages 19–110) with valid earnings. A missing parent is excluded, never converted to zero. A recorded zero earner is retained at this stage.
7. For both log–log OLS and rank–rank regressions, require positive **child earnings and combined parental earnings**, not positive earnings for every parent separately. Keep the same children in all four waves.

| Stage | Unit | Count |
|---|---|---:|
| Both recorded parent IDs known | Child-parent links | {a['links']:,} |
| All three found as current members in same wave | Child-parent-wave records | {a['matched']:,} |
| All three meet adult age eligibility | Child-parent-wave records | {adults:,} |
| All three have assignable, valid own earnings | Child-parent-wave records | {a['adult_observed']:,} |
| Child and combined parental earnings positive | Child-parent-wave records | {a['positive']:,} |
| Distinct children with at least one positive eligible wave | Children | {a['unique_positive_children']:,} |
| Positive and eligible in all four waves | Children | {a['averaged']:,} |
| Main long-form panel | Child-parent-wave records | {a['balanced']:,} |

Among the main panel's {a['balanced']:,} pair-year records, {a['zero_in_either_parent_pair_years']:,} have at least one zero-earning parent, and {a['parents_different_household_pair_years']:,} have parents in different households. This verifies that summation does not require both parents to work or live together.

Baseline median interview ages: child {a['2017_median_ages']['child_age']:.0f}, mother {a['2017_median_ages']['mother_age']:.0f}, father {a['2017_median_ages']['father_age']:.0f}. Age is used only for adult eligibility; no age control is included.

## 4. Nominal income and averages

For each year:

$$X_{{it}}=M_{{it}}+F_{{it}},\qquad Y_{{it}}=C_{{it}}.$$

SQL forms arithmetic averages over **2016, 2018, 2020, 2022**:

$$\overline X_i=\frac14\sum_t(M_{{it}}+F_{{it}}),\qquad
\overline Y_i=\frac14\sum_t C_{{it}}.$$

Logs are taken after averaging. There is no CPI adjustment, interpolation, winsorization, or additional imputation in the main results.

**Your inflation argument holds within a single year.** Dividing both X and Y by the same annual price index shifts the log intercept without changing the slope. I verified numerically that all four single-year slopes are unchanged to numerical precision. It also leaves within-year ranks unchanged.

For multi-year averages, each year's conversion factor differs. Nominal averaging weights later price levels differently, so it is not generally equivalent to real averaging. As a diagnostic only, the identical sample's averaged IGE is **{ols.iloc[-1].slope:.6f} nominal versus {inf.iloc[0].slope:.6f} real**. The primary tables below use nominal income as requested.

## 5. Regression specification and results

$$\log C_i=\alpha+\beta\log(M_i+F_i)+\varepsilon_i.$$

The averaged version substitutes the corresponding arithmetic averages before taking logs. All models have an intercept and **no age or other controls**, and are unweighted. Main confidence intervals cluster by connected parental networks: children sharing either recorded parent are in the same cluster, including half-siblings. There are {int(ols.iloc[0].clusters)} clusters.

{table(ols)}

These estimates are not directly comparable with the old 2,177-pair family-income estimates: both the income concept and selected sample changed. Observing both parents and requiring positive earnings across all four waves selects a small, working subset. The average is not a known lifetime-income benchmark.

## 6. Bonus: rank–rank regression

$$R_i^{{child}}=a+bR_i^{{parents}}+u_i.$$

This is meaningful as a **relative mobility** measure, distinct from a dollar elasticity. Higher parent rank predicts higher child rank when the slope is positive. For the average-income main sample, a 10-percentile-point parent difference is associated with approximately **{10*rr.iloc[-1].slope:.2f} percentile points** in child rank. It is not a causal effect.

SQL computes percentile midranks separately for each generation and measurement. Tied incomes get the average tied rank:

$$R_i=100\frac{{\text{{midrank}}_i-0.5}}{{N}}.$$

For the multi-year model, first average nominal earnings, **then rank those averages**. Do not average yearly ranks. Parents are ranked across the child observations, so siblings receive tied parent ranks. These are ranks within our selected pooled-age sample, not national ranks or birth-cohort-specific ranks. Rank–rank approaches are used in [intergenerational mobility research](https://opportunityinsights.org/paper/land-of-opportunity/), but this small selected sample does not reproduce that research's population design.

### Same {a['averaged']:,} children as the IGE models

{table(rr)}

Rank confidence intervals use 1,000 parental-network bootstrap draws and **recompute both sets of ranks in each draw**, rather than treating ranks as known. Seed: 6400. The sample remains unweighted.

## 7. Checks performed and remaining limits

- Checked all four codebooks for consistent earnings definitions and the raw import column positions.
- Recorded SHA-256 hashes and counts; raw files remain unchanged.
- Checked unique individual-wave and family-wave keys, distinct parents and no self-parent links.
- Enforced one child-wave row after matching and exactly four observations per main child.
- Verified every parental sum equals the separately matched mother plus father.
- Independently recalculated SQL averages in Python; verified average sums equal sums of parent averages.
- Independently recalculated SQL tied ranks in Python on the same positive-income sample.
- Verified single-year slopes are invariant to a common CPI deflator.

These checks verify data processing, not causal identification or the absence of selection bias. This analysis does **not** empirically isolate life-cycle bias. Four recent income years cannot reveal lifetime earnings; both parents' observation and positive-earnings restrictions particularly affect older families. Total personal income, farm/business earnings, pensions and capital income are not represented in this earnings definition. If the intended concept is total income, that requires a separately documented construction before finalizing the blog.

## 8. Reproduce and inspect

From `blog6repo`:

```bash
python3 code/reproduce.py --data-dir ../Blog6data
python3 code/build_review.py
```

Tables: `results/tables/`. Figures: `results/figures/`. Person-level database: `data/processed/both_parents_nominal.sqlite` (local, excluded from the public bundle). Raw field mappings: `results/tables/variable_dictionary.csv`. Sample counts and hashes: `results/tables/audit.json`.

The current workflow is written in `reproducibility.qmd` and executed by `code/reproduce.py`. It uses `code/psid_io.py` for fixed-width input and `code/inference.py` for estimation. It has no dependency on the local archive and does not change the blog.

## Complete SQL used in this rerun

```sql
{sql}
```
'''
source=ROOT/'report/revised_review.qmd';source.write_text(doc)
pandoc = shutil.which('pandoc')
if not pandoc:
    quarto = shutil.which('quarto')
    if quarto:
        candidates = list((Path(quarto).resolve().parent / 'tools').glob('**/pandoc'))
        pandoc = str(candidates[0]) if candidates else None
if not pandoc:
    raise SystemExit('Review source saved. Add Pandoc or Quarto to PATH to also produce review HTML.')
subprocess.run([
    pandoc, source.name, '--from=markdown', '--standalone', '--embed-resources',
    '--mathml', '--toc', '--css=styles.css', '-o', 'revised_review.html',
], cwd=source.parent, check=True)
print('Wrote', source)
