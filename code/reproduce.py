"""Reproduce the Blog 6 analysis and figures from the original PSID releases.

Run this file with Python from any directory. Use --data-dir to select a
raw-data folder; the default is Blog6data beside the project folder.
Outputs are saved to results/tables and results/figures; the blog is not edited.
"""


def main():
    # 1. Setup
    # Define paths, check raw inputs, and fix the bootstrap seed.

    from pathlib import Path
    import json
    import sqlite3
    import argparse

    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Find the project directory and define all paths in one place.
    project_dir = Path(__file__).resolve().parents[1]
    data_dir = project_dir / "data"
    code_dir = project_dir / "code"
    results_dir = project_dir / "results"
    tables_dir = results_dir / "tables"
    figures_dir = results_dir / "figures"
    processed_dir = data_dir / "processed"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=project_dir.parent / "Blog6data",
        help="Folder containing the six original PSID releases.",
    )
    raw_dir = parser.parse_args().data_dir.resolve()

    for directory in [data_dir, results_dir, tables_dir, figures_dir, processed_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    from psid_io import read_fixed
    from inference import parent_clusters, fit_model, rank_models

    # Fix the bootstrap seed so estimates and intervals can be reproduced.
    rng = np.random.default_rng(6400)
    bootstrap_draws = 1000
    waves = [2017, 2019, 2021, 2023]
    measures = ["2016", "2018", "2020", "2022", "Four-year average"]
    individual_prefix = {2017: 345, 2019: 347, 2021: 349, 2023: 351}
    family_fields = {
        2017: ["ER66002", "ER71293", "ER71321"],
        2019: ["ER72002", "ER77315", "ER77343"],
        2021: ["ER78002", "ER81642", "ER81670"],
        2023: ["ER82002", "ER85496", "ER85524"],
    }

    # Check inputs before replacing the generated local database.
    releases = [("pid23", "PID23"), ("ind2023er", "IND2023ER")]
    releases += [(f"fam{wave}er", f"FAM{wave}ER") for wave in waves]
    for folder, stem in releases:
        for extension in ["txt", "do"]:
            required_file = raw_dir / folder / f"{stem}.{extension}"
            if not required_file.is_file():
                raise FileNotFoundError(f"Missing PSID input: {required_file}")
    print("Project:", project_dir)

    # 2. Read and match the data
    # Read parent identifiers, individual roles and family earnings; match them with SQL.

    metadata = []
    sources = []
    parent_ids, source = read_fixed(
        raw_dir / "pid23", "PID23",
        ["PID2", "PID3", "PID4", "PID5", "PID23", "PID24"], metadata,
    )
    sources.append(source)
    individual_fields = ["ER30001", "ER30002"] + [
        f"ER{prefix}{suffix:02d}"
        for prefix in individual_prefix.values()
        for suffix in [1, 2, 3, 4]
    ]
    individuals, source = read_fixed(
        raw_dir / "ind2023er", "IND2023ER", individual_fields, metadata,
    )
    sources.append(source)

    people = []
    families = []
    for wave, prefix in individual_prefix.items():
        fields = ["ER30001", "ER30002"] + [f"ER{prefix}{suffix:02d}" for suffix in [1, 2, 3, 4]]
        person_wave = individuals[fields].copy()
        person_wave.columns = ["id68", "pn", "family_id", "sequence", "relationship", "age"]
        person_wave["wave"] = wave
        people.append(person_wave)

        family_wave, source = read_fixed(
            raw_dir / f"fam{wave}er", f"FAM{wave}ER", family_fields[wave], metadata,
        )
        sources.append(source)
        family_wave.columns = ["family_id", "rp_earnings", "sp_earnings"]
        family_wave["wave"] = wave
        family_wave["income_year"] = wave - 1
        families.append(family_wave)

    person_year = pd.concat(people, ignore_index=True)
    family_year = pd.concat(families, ignore_index=True)
    assert not person_year.duplicated(["id68", "pn", "wave"]).any()
    assert not family_year.duplicated(["family_id", "wave"]).any()
    valid_parents = parent_ids[
        (parent_ids.PID4 > 0) & parent_ids.PID5.between(1, 995)
        & (parent_ids.PID23 > 0) & parent_ids.PID24.between(1, 995)
    ]
    assert not ((valid_parents.PID4 == valid_parents.PID23) & (valid_parents.PID5 == valid_parents.PID24)).any()
    assert not ((valid_parents.PID2 == valid_parents.PID4) & (valid_parents.PID3 == valid_parents.PID5)).any()
    assert not ((valid_parents.PID2 == valid_parents.PID23) & (valid_parents.PID3 == valid_parents.PID24)).any()

    database_file = processed_dir / "both_parents_nominal.sqlite"
    if database_file.exists():
        database_file.unlink()
    connection = sqlite3.connect(database_file)
    for name, frame in [("pid", parent_ids), ("person_year", person_year), ("family_year", family_year)]:
        frame.to_sql(name, connection, index=False)
    connection.executescript((code_dir / "match_parents_children.sql").read_text())

    balanced = pd.read_sql_query("SELECT * FROM balanced ORDER BY child_id68, child_pn, wave", connection)
    averaged = pd.read_sql_query("SELECT * FROM averaged ORDER BY child_id68, child_pn", connection)
    assert len(balanced) == 4 * len(averaged)
    assert (averaged.n_years == 4).all()
    np.testing.assert_allclose(balanced.parent_income, balanced.mother_income + balanced.father_income)
    np.testing.assert_allclose(averaged.parent_income, averaged.mother_income + averaged.father_income)
    independent_means = balanced.groupby(["child_id68", "child_pn"])[["parent_income", "child_income"]].mean()
    np.testing.assert_allclose(independent_means.to_numpy(), averaged[["parent_income", "child_income"]].to_numpy())
    print("Balanced sample:", len(averaged), "children;", len(balanced), "child–year records")

    # 3. Run regressions and save results
    # Estimate annual and averaged-income models, then save coefficients and sample checks.

    parent_links = pd.read_sql_query(
        "SELECT DISTINCT child_id68, child_pn, mother_id68, mother_pn, father_id68, father_pn FROM balanced",
        connection,
    )
    clusters = parent_clusters(parent_links)
    income_measures = pd.read_sql_query("SELECT * FROM income_measures", connection)
    ranked = pd.read_sql_query("SELECT * FROM ranked", connection)

    ige_results = pd.DataFrame([
        fit_model(income_measures[income_measures.measure == measure], measure, clusters)
        for measure in measures
    ])
    ige_results.to_csv(tables_dir / "ige_nominal.csv", index=False)

    rank_results = rank_models(ranked, measures, clusters, rng, bootstrap_draws)
    rank_results.to_csv(tables_dir / "rank_rank_same_sample.csv", index=False)
    print(ige_results.to_string(index=False))
    print(rank_results.to_string(index=False))

    # Save the separate inflation-adjustment diagnostic.
    cpi = pd.read_csv(data_dir / "cpi.csv").set_index("income_year").cpi
    real_income = balanced.copy()
    real_income["factor"] = real_income.income_year.map(lambda year: 292.655 / cpi[year])
    for variable in ["parent_income", "child_income"]:
        real_income[variable] = real_income[variable] * real_income.factor
    for wave, group in real_income.groupby("wave"):
        nominal_slope = ige_results[ige_results.measure == str(wave - 1)].slope.iloc[0]
        assert abs(fit_model(group, str(wave - 1), clusters)["slope"] - nominal_slope) < 1e-10
    real_average = real_income.groupby(["child_id68", "child_pn"], as_index=False)[["parent_income", "child_income"]].mean()
    inflation_result = fit_model(real_average, "Real four-year average (diagnostic only)", clusters)
    pd.DataFrame([inflation_result]).to_csv(tables_dir / "inflation_diagnostic.csv", index=False)

    # Record how many people and child–year records survive each selection step.
    selection_steps = [
        ("pid", "Raw parent-ID file"),
        ("links", "Both parents identified"),
        ("matched", "Child and both parents matched in the same survey year"),
        ("adult_observed", "Child and both parents aged 19–110, with nonmissing earnings (including zero)"),
        ("positive", "Positive child and combined parent earnings"),
        ("balanced", "Eligible in all four waves"),
        ("averaged", "Average over the four income years"),
    ]
    flow = []
    row_counts = {}
    for table, label in selection_steps:
        keys = "PID2, PID3" if table == "pid" else "child_id68, child_pn"
        rows = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        children = connection.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT {keys} FROM {table})").fetchone()[0]
        row_counts[table] = rows
        flow.append({
            "stage": label,
            "children": children,
            "child_years": rows if table not in ["pid", "links", "averaged"] else None,
        })
    sample_flow = pd.DataFrame(flow)
    sample_flow.to_csv(tables_dir / "sample_flow.csv", index=False)
    assert flow[-2]["child_years"] == 4 * flow[-1]["children"] == len(balanced)

    eligible = pd.read_sql_query("SELECT wave, COUNT(*) pair_years FROM positive GROUP BY wave", connection)
    eligible.to_csv(tables_dir / "eligible_by_wave.csv", index=False)
    audit = {table: row_counts[table] for table in ["links", "matched", "adult_observed", "positive", "balanced", "averaged"]}
    audit["unique_positive_children"] = int(sample_flow.iloc[4].children)
    audit["zero_in_either_parent_pair_years"] = int(((balanced.mother_income == 0) | (balanced.father_income == 0)).sum())
    audit["parents_different_household_pair_years"] = int((balanced.mother_family_id != balanced.father_family_id).sum())
    audit["source_files"] = sources
    audit["2017_median_ages"] = balanced[balanced.wave == 2017][["child_age", "mother_age", "father_age"]].median().to_dict()
    audit["definition"] = "Nominal individual labor income excluding farm and unincorporated business income. Parent = recorded mother + recorded father. Child = own same-definition income."
    (tables_dir / "audit.json").write_text(json.dumps(audit, indent=2))
    pd.DataFrame(metadata).to_csv(tables_dir / "variable_dictionary.csv", index=False)
    connection.close()

    # 4. Create and save figures
    # Use the saved results to reproduce the two blog figures with their original styling.

    ols = pd.read_csv(tables_dir / "ige_nominal.csv")
    with sqlite3.connect(f"file:{database_file}?mode=ro", uri=True) as connection:
        panel = pd.read_sql_query("SELECT * FROM balanced", connection)
    assert len(panel) == 4 * int(ols.iloc[0]["n"])

    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    # Figure 1: compare annual and averaged-income IGE estimates.
    fig, ax = plt.subplots(figsize=(8.2, 4))
    x = np.arange(5)
    ax.errorbar(
        x, ols.slope,
        yerr=[ols.slope - ols.ci_low, ols.ci_high - ols.slope],
        fmt="o", color="#176b83", capsize=5,
    )
    ax.axhline(0, color="#888888", lw=1)
    ax.set(
        xticks=x,
        xticklabels=["2016", "2018", "2020", "2022", "Four-year\naverage"],
        ylabel="Intergenerational earnings elasticity",
        title="The estimated relationship depends on the income measure",
    )
    for index, value in enumerate(ols.slope):
        ax.annotate(f"{value:.3f}", (index, value), xytext=(9, 4), textcoords="offset points")
    fig.tight_layout()
    fig.savefig(figures_dir / "ige_comparison.png", dpi=180)
    plt.close(fig)

    # Figure 2: keep each person's starting-age group fixed across income years.
    baseline = panel[panel.income_year == 2016][["child_id68", "child_pn", "child_age", "father_age"]]
    baseline = baseline.rename(columns={"child_age": "baseline_child_age", "father_age": "baseline_father_age"})
    trajectories = panel.merge(baseline, on=["child_id68", "child_pn"], validate="many_to_one")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    paths = []
    groups = [
        (axes[0], "baseline_child_age", "child_income", [0, 29, 39, 120],
         ["19–29", "30–39", "40+"], "Children: grouped by child’s starting age"),
        (axes[1], "baseline_father_age", "parent_income", [0, 54, 64, 120],
         ["Under 55", "55–64", "65+"], "Parents: grouped by father’s starting age"),
    ]
    for ax, age, income, bins, labels, title in groups:
        group_data = trajectories.copy()
        group_data["age_group"] = pd.cut(group_data[age], bins, labels=labels)
        summary = group_data.groupby(["age_group", "income_year"], observed=True)[income].agg(median="median", n="size").reset_index()
        summary["generation"] = income
        paths.append(summary)
        colors = ["#176b83", "#d87522", "#80539a"]
        for (group, values), color in zip(summary.groupby("age_group", observed=True), colors):
            ax.plot(
                values.income_year, values["median"] / 1000,
                marker="o", color=color, label=f'{group} (n={values.iloc[0]["n"]})',
            )
        ax.set(title=title, xlabel="Income year", xticks=[2016, 2018, 2020, 2022])
        ax.legend(frameon=False, fontsize=9)
    axes[0].set_ylabel("Median nominal earnings ($ thousands)")
    fig.tight_layout()
    fig.savefig(figures_dir / "life_cycle_paths.png", dpi=180)
    plt.close(fig)

    path_table = pd.concat(paths)
    path_table.to_csv(tables_dir / "life_cycle_paths.csv", index=False)
    print("Saved both figures and all result tables.")


if __name__ == "__main__":
    main()
