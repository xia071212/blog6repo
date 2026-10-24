# Parent–child earnings and income measurement

This project asks how strongly adult children's earnings are associated with their parents' earnings, and how the estimate changes when income is measured in one year or averaged across several years. It matches PSID parents and children with SQL, estimates intergenerational earnings elasticities (IGE), and compares them with rank–rank regressions.

Read the [blog](https://xia071212.github.io/myrepo/blog/posts/post6/index.html), its [source](report/current_blog.qmd), or the [reproducibility document](reproducibility.qmd). The analysis uses income years 2016, 2018, 2020 and 2022, with the same 411 children in all five specifications.

## Data and sources

Obtain the releases below from [PSID packaged data](https://simba.isr.umich.edu/Zips/ZipMain.aspx) through your own registered account. Keep the supplied fixed-width `.txt` files and Stata `.do` layout files together in a folder named `Blog6data`, beside this project folder. The Python reader uses the `.do` column positions; Stata is not required.

| Release folder | Required files | Fields used |
|---|---|---|
| `pid23` | `PID23.txt`, `PID23.do` | Child identifiers and recorded mother/father identifiers |
| `ind2023er` | `IND2023ER.txt`, `IND2023ER.do` | Original family ID, person number, current family ID, sequence, household role and age |
| `fam2017er` | `FAM2017ER.txt`, `FAM2017ER.do` | Family ID and reference-person/spouse earnings for 2016 |
| `fam2019er` | `FAM2019ER.txt`, `FAM2019ER.do` | Family ID and reference-person/spouse earnings for 2018 |
| `fam2021er` | `FAM2021ER.txt`, `FAM2021ER.do` | Family ID and reference-person/spouse earnings for 2020 |
| `fam2023er` | `FAM2023ER.txt`, `FAM2023ER.do` | Family ID and reference-person/spouse earnings for 2022 |

Use the compatible 2023 Parent Identification and 1968–2023 Cross-Year Individual releases. The [variable dictionary](results/tables/variable_dictionary.csv) records the exact variables, labels and column positions. The [input audit](results/tables/audit.json) records source row counts and SHA-256 checksums.

The four annual CPI-U observations in [data/cpi.csv](data/cpi.csv) come from the [BLS annual CPI table](https://www.bls.gov/regions/northeast/data/consumerpriceindex_us_table.htm). They support a separate inflation-adjustment diagnostic; the article's main estimates use nominal earnings.

Raw PSID downloads remain outside the project. Generated person-level records stay in the ignored `data/processed/` folder; they are not part of the replication files shared through version control. Each reader obtains their own raw data.

## Matching, income and sample

The Parent Identification File establishes parentage. Original family ID plus person number identifies each individual. Current family ID plus survey year attaches the appropriate family record. Reference-person/spouse status determines which person's earnings field to use; these roles do not identify who is a child's mother or father.

Income is individual labor earnings excluding farm and unincorporated-business income. Parental earnings equal the recorded mother's plus recorded father's earnings; child earnings are the child's own earnings. The Family Files supply separate individual earnings fields, not the household total used as an individual's income. This implementation does not use the Individual File's income variables for other family members, so people without an eligible reference-person/spouse earnings record are excluded. PSID's generated earnings variables include its own imputations; this project adds none.

SQL retains records where the child and both parents are aged 19–110 and each has an earnings value from 0 through 9,999,997, excluding missing and reserved codes. It then requires positive child earnings and a positive parental sum, and retains children eligible in all four waves. An individual parent may earn zero. The resulting 411 children contribute 1,644 child–year observations; [sample_flow.csv](results/tables/sample_flow.csv) distinguishes people from repeated yearly records.

Annual and averaged models use unweighted OLS without additional controls. Earnings are averaged in levels before taking logarithms or ranks. IGE confidence intervals cluster by connected shared-parent networks, including half-siblings. Rank intervals use 1,000 cluster bootstrap draws, recalculating tied ranks in each draw. These estimates describe the selected sample, rather than a representative population or a causal effect.

## Code and their roles

The reproducibility document follows four stages: **Setup → read and match data → run regressions and save results → create and save figures**. Paths are defined together, output folders are created automatically, and the bootstrap seed is fixed. The Python entry point executes the document's code directly, so there is one version of the analysis to maintain.

| Code | Purpose |
|---|---|
| [reproducibility.qmd](reproducibility.qmd) | Readable, executable Python sections covering the complete analysis and both figures |
| [code/reproduce.py](code/reproduce.py) | Execute those sections in order from any working directory; accept an optional raw-data location |
| [code/psid_io.py](code/psid_io.py) | Read documented fixed-width fields, record labels and hash the inputs |
| [code/match_parents_children.sql](code/match_parents_children.sql) | Match people, assign earnings, filter observations, average income and calculate ranks |
| [code/inference.py](code/inference.py) | Fit OLS models and calculate shared-parent clustered and bootstrap intervals |

## Results used in the article

Result tables are saved in `results/tables/`; figures are saved in `results/figures/`. Reproducing the analysis does not edit or render the blog. The blog source refers directly to these figures.

| Output | Connection to the article |
|---|---|
| [ige_nominal.csv](results/tables/ige_nominal.csv), [ige_comparison.png](results/figures/ige_comparison.png) | Figure 1: four annual IGE estimates and the estimate using averaged earnings, with confidence intervals |
| [life_cycle_paths.csv](results/tables/life_cycle_paths.csv), [life_cycle_paths.png](results/figures/life_cycle_paths.png) | Figure 2: median earnings paths for fixed groups defined by 2017 interview age |
| [rank_rank_same_sample.csv](results/tables/rank_rank_same_sample.csv) | Rank–rank slopes and intervals for the same five income measures |
| [sample_flow.csv](results/tables/sample_flow.csv) | Selection table: distinct children and child–year observations at each step |
| [eligible_by_wave.csv](results/tables/eligible_by_wave.csv) | Positive-income records by survey wave before requiring all four waves |
| [inflation_diagnostic.csv](results/tables/inflation_diagnostic.csv) | Supporting check using earnings adjusted to 2022 dollars before averaging |
| [audit.json](results/tables/audit.json), [variable_dictionary.csv](results/tables/variable_dictionary.csv) | Source checksums, counts, definitions and variable mappings |

The lifecycle figure groups children by their own starting age and parental earnings by the father's starting age. These are fixed descriptive groups, not regression controls. Their trajectories illustrate age-dependent measurement; they do not measure the size of bias relative to lifetime earnings.

## Reproducing the analysis

1. Prepare Python with the packages listed in `requirements.txt`, and place the six PSID releases in the folders described above.
2. Open `reproducibility.qmd` to follow its four stages. Run `code/reproduce.py` to execute all the document's Python sections in order. The default input location is the sibling `Blog6data` folder; its `--data-dir` option accepts another location. This creates the local database, all result tables and both figures without requiring Quarto or changing the blog.
3. Inspect the saved tables under `results/tables/` and PNG images under `results/figures/`.

The analysis checks unique individual and family-year keys, recorded parent identities, four observations per retained child, parental earnings sums, and agreement between SQL and independent calculations of averages and ranks. The bootstrap uses a fixed seed. Generated figures and article numbers come from these saved outputs.

## References

- [PSID](https://psidonline.isr.umich.edu/) and [2023 Parent Identification documentation](https://psidonline.isr.umich.edu/documents/psid/intro/pid23intro.pdf).
- [Haider and Solon (2006), Life-Cycle Variation in the Association between Current and Lifetime Earnings](https://www.nber.org/papers/w11943).
- [BLS annual CPI-U](https://www.bls.gov/regions/northeast/data/consumerpriceindex_us_table.htm).
