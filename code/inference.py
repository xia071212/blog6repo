"""OLS and uncertainty calculations for related parent–child observations."""
import numpy as np
import pandas as pd
import statsmodels.api as sm


def parent_clusters(parent_links):
    """Connect children who share either recorded parent, including half-siblings."""
    roots = {}

    def find(person):
        roots.setdefault(person, person)
        if roots[person] != person:
            roots[person] = find(roots[person])
        return roots[person]

    for row in parent_links.itertuples():
        mother = (row.mother_id68, row.mother_pn)
        father = (row.father_id68, row.father_pn)
        roots[find(father)] = find(mother)

    return {
        (row.child_id68, row.child_pn): str(find((row.mother_id68, row.mother_pn)))
        for row in parent_links.itertuples()
    }


def add_clusters(data, clusters):
    data = data.copy()
    data["cluster"] = [
        clusters[(row.child_id68, row.child_pn)] for row in data.itertuples()
    ]
    return data


def fit_model(data, label, clusters, use_ranks=False):
    """Estimate log–log IGE or rank–rank OLS with shared-parent clustered errors."""
    data = add_clusters(data, clusters)
    if use_ranks:
        x = data.parent_rank.to_numpy()
        y = data.child_rank.to_numpy()
    else:
        x = np.log(data.parent_income.to_numpy())
        y = np.log(data.child_income.to_numpy())

    model = sm.OLS(y, sm.add_constant(x)).fit(
        cov_type="cluster",
        cov_kwds={"groups": data.cluster},
        use_t=True,
    )
    low, high = model.conf_int()[1]
    return {
        "measure": label,
        "n": len(data),
        "clusters": data.cluster.nunique(),
        "intercept": model.params[0],
        "slope": model.params[1],
        "ci_low": low,
        "ci_high": high,
        "r_squared": model.rsquared,
    }


def rank_models(data, measures, clusters, rng, draws):
    """Recompute tied ranks in every bootstrap sample of parental networks."""
    results = []
    for label in measures:
        sample = data[data.measure == label].reset_index(drop=True)
        sample = add_clusters(sample, clusters)
        parent_rank = 100 * (sample.parent_income.rank(method="average") - 0.5) / len(sample)
        child_rank = 100 * (sample.child_income.rank(method="average") - 0.5) / len(sample)
        np.testing.assert_allclose(parent_rank, sample.parent_rank)
        np.testing.assert_allclose(child_rank, sample.child_rank)
        result = fit_model(sample, label, clusters, use_ranks=True)

        indices = list(sample.groupby("cluster", sort=True).indices.values())
        slopes = []
        for _ in range(draws):
            selected = rng.integers(len(indices), size=len(indices))
            bootstrap_indices = np.concatenate([indices[index] for index in selected])
            bootstrap = sample.iloc[bootstrap_indices]
            x = bootstrap.parent_income.rank(method="average").to_numpy()
            y = bootstrap.child_income.rank(method="average").to_numpy()
            slopes.append(np.cov(x, y, ddof=0)[0, 1] / np.var(x))

        result["ci_low"], result["ci_high"] = np.quantile(slopes, [0.025, 0.975])
        results.append(result)
    return pd.DataFrame(results)
