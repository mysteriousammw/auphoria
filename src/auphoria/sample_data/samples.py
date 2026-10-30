"""Predictable generators for the bundled sample CSVs.

Used to (re)create ``src/auphoria/sample_data/data/*.csv`` deterministically.
The values are synthetic but realistic, and are fixed so automated tests can
check hand-calculated answers against them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_MISSING = float("nan")  # leave a hole (NaN) in the CSV


def plant_growth(n_per_group: int = 15, seed: int = 42) -> pd.DataFrame:
    """A two-treatment, hand-friendly dataset for the t-test demo.

    control / fertilizer heights are drawn from normal distributions with a
    clear separation so the t-test is unmistakably significant; a few weight
    values are missing (left blank) to demonstrate the missing-value guardrail.
    """
    rng = np.random.default_rng(seed)
    control = rng.normal(12.0, 2.0, n_per_group)
    fertilizer = rng.normal(16.0, 2.2, n_per_group)
    heights = np.concatenate([control, fertilizer])

    weight = 0.4 * heights + rng.normal(0, 1.0, len(heights))

    n = len(heights)
    treatment = np.concatenate(
        [np.full(n_per_group, "control"), np.full(n_per_group, "fertilizer")]
    )
    light_hours = rng.integers(8, 15, n)

    df = pd.DataFrame(
        {
            "treatment": treatment,
            "height_cm": np.round(heights, 1).astype(float),
            "weight_g": np.round(weight, 1).astype(float),
            "light_hours": light_hours,
        }
    )
    # Leave 3 weight_g values blank (NaN) on purpose.
    hole_indices = rng.choice(n, size=3, replace=False)
    df.loc[hole_indices, "weight_g"] = _MISSING
    return df


def survey(n_rows: int = 40, seed: int = 7) -> pd.DataFrame:
    """A survey for correlation/summary demos (online vs classroom)."""
    rng = np.random.default_rng(seed)
    group = rng.choice(["online", "classroom"], size=n_rows, p=[0.5, 0.5])
    age = rng.integers(18, 40, n_rows)
    hours = rng.uniform(1, 15, n_rows)
    score = 45 + 3.2 * hours + rng.normal(0, 6, n_rows)
    score = np.clip(score, 0, 100)

    df = pd.DataFrame(
        {
            "group": group,
            "score": np.round(score, 1).astype(float),
            "age": age.astype(int),
            "hours_studied": np.round(hours, 1).astype(float),
        }
    )
    # A couple blank hours to exercise missing handling.
    df.loc[rng.choice(len(df), size=2, replace=False), "hours_studied"] = _MISSING
    return df


def training(n_pairs: int = 12, seed: int = 11) -> pd.DataFrame:
    """A paired pre/post training dataset for the paired t-test demo.

    Same subjects measured twice (skill score before / after training) with
    a clear improvement, so the paired test is expected to be significant.
    """
    rng = np.random.default_rng(seed)
    before = rng.normal(58.0, 7.0, n_pairs)
    after = before + rng.normal(9.0, 3.0, n_pairs)
    df = pd.DataFrame(
        {
            "subject": [f"S{i+1:02d}" for i in range(n_pairs)],
            "before": np.round(before, 1).astype(float),
            "after": np.round(after, 1).astype(float),
        }
    )
    return df


def diets(n_per_group: int = 10, seed: int = 23) -> pd.DataFrame:
    """Three diets with weight loss outcome (one-way ANOVA demo).

    Also carries an 'adherence' 2-level category so the dataset can serve the
    chi-square demo (diet x adherent vs not-adherent).
    """
    rng = np.random.default_rng(seed)
    loss_a = rng.normal(1.2, 0.6, n_per_group)
    loss_b = rng.normal(2.8, 0.7, n_per_group)
    loss_c = rng.normal(4.1, 0.8, n_per_group)
    diet = (["diet_a"] * n_per_group + ["diet_b"] * n_per_group
            + ["diet_c"] * n_per_group)
    loss = np.concatenate([loss_a, loss_b, loss_c])
    adherence = rng.choice(["adherent", "not_adherent"],
                           size=len(loss), p=[0.6, 0.4])
    df = pd.DataFrame(
        {
            "diet": diet,
            "weight_loss_kg": np.round(loss, 2).astype(float),
            "adherence": adherence,
        }
    )
    return df


def cohort(n_rows: int = 120, seed: int = 53) -> pd.DataFrame:
    """A 2x2 epidemiology table (odds-and-risk demo).

    Exposure x disease with known, hand-checkable counts:
    exposed: 40 disease / 20 no-disease; unexposed: 15 disease / 45 no-disease.
    OR = (a*d)/(b*c) = (40*45)/(20*15) = 6.0; RR = (40/60)/(15/60) = 2.667.
    Carries a numeric 'age' column so the table rows are not trivially rigid.
    """
    rng = np.random.default_rng(seed)
    counts = {
        ("exposed", "yes"): 40,
        ("exposed", "no"): 20,
        ("unexposed", "yes"): 15,
        ("unexposed", "no"): 45,
    }
    rows = []
    for (exposure, disease), n in counts.items():
        age = rng.normal(48.0 if exposure == "exposed" else 42.0, 8.0, n)
        rows.append(pd.DataFrame({
            "exposure": [exposure] * n,
            "disease": [disease] * n,
            "age": np.round(age, 0).astype(int),
        }))
    df = pd.concat(rows, ignore_index=True)
    # p = exposed share of disease among `yes` rows etc.; keep it clean
    return df


def repeated(n_subjects: int = 24, n_times: int = 3, seed: int = 61) -> pd.DataFrame:
    """Repeated measures in LONG format (repeated-measures ANOVA / Friedman).

    Each subject (id) is measured at every time point (time = t1..t3). The
    outcome rises over time with a per-subject random intercept, so a
    repeated-measures design (not an independent-samples test) is the honest
    tool.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_subjects):
        intercept = rng.normal(0, 2.5)
        base = rng.normal(55.0 + intercept, 4.0)
        for t, lift in enumerate((0.0, 3.0, 6.0)):
            score = base + lift + rng.normal(0, 1.8)
            rows.append({
                "subject": f"S{s+1:02d}",
                "time": f"t{t+1}",
                "score": round(score, 1),
            })
    return pd.DataFrame(rows)


def bland_altman(n_pairs: int = 40, seed: int = 67) -> pd.DataFrame:
    """Two measures of the same quantity (Bland-Altman agreement demo).

    method_a and method_b measure the same value, with a small systematic
    bias (method_b reads ~0.6 lower on average) and measurement noise, so the
    limits of agreement are meaningful.
    """
    rng = np.random.default_rng(seed)
    true = rng.normal(100.0, 10.0, n_pairs)
    a = true + rng.normal(0, 1.5, n_pairs)
    b = true - 0.6 + rng.normal(0, 1.8, n_pairs)
    return pd.DataFrame({
        "subject": [f"P{i+1:02d}" for i in range(n_pairs)],
        "method_a": np.round(a, 1).astype(float),
        "method_b": np.round(b, 1).astype(float),
    })


def panel(n_firms: int = 30, n_years: int = 5, seed: int = 71) -> pd.DataFrame:
    """Panel (longitudinal) data (panel / fixed-effects regression demo).

    Repeated firm-year observations with an individual (firm) effect and
    time-varying covariates, so a panel regression (with firm fixed effects)
    is appropriate.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for f in range(n_firms):
        effect = rng.normal(0, 3.0)  # time-invariant firm effect
        for yr in range(n_years):
            invest = rng.normal(20.0, 6.0)
            market = rng.normal(8.0, 3.0)
            profit = 5.0 + effect + 0.5 * invest + 1.4 * market \
                + rng.normal(0, 2.0)
            rows.append({
                "firm": f"f{f+1:02d}",
                "year": 2019 + yr,
                "invest": round(invest, 2),
                "market_value": round(market, 2),
                "profit": round(profit, 2),
            })
    return pd.DataFrame(rows)


def time_series(n: int = 120, seed: int = 73) -> pd.DataFrame:
    """A single time series (time-series decomposition / trend demo).

    A monthly-ish series with a trend + seasonal component + noise, so
    trend/seasonal decomposition is meaningful.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    trend = 0.2 * t
    seasonal = 3.0 * np.sin(2 * np.pi * t / 12.0)
    noise = rng.normal(0, 1.5, n)
    value = trend + seasonal + noise
    return pd.DataFrame({
        "period": pd.date_range("2020-01-01", periods=n, freq="MS"),
        "value": np.round(value, 2).astype(float),
    })


def counts(n_samples_per: int = 6, n_genes: int = 100, seed: int = 79) -> pd.DataFrame:
    """A small RNA-seq-style counts matrix (differential-expression demo).

    One row per biological sample; a 'condition' column (control/treated);
    the remaining columns are per-gene integer counts. A handful of genes
    are over-expressed in 'treated' so differential expression is real.
    """
    rng = np.random.default_rng(seed)
    rows = []
    de_up = set(range(10, 18))      # genes over-expressed in treated
    de_down = set(range(40, 48))    # genes under-expressed in treated
    for i in range(n_samples_per * 2):
        cond = "control" if i < n_samples_per else "treated"
        size = rng.integers(4, 8) * 1_000_000
        exp = size / 1_000_000.0
        rec = {"condition": cond}
        for g in range(n_genes):
            base = rng.lognormal(mean=3.0, sigma=0.5)
            if cond == "treated" and g in de_up:
                base *= 4.0
            if cond == "treated" and g in de_down:
                base *= 0.25
            rec[f"g{g:03d}"] = int(rng.poisson(base * exp))
        rows.append(rec)
    return pd.DataFrame(rows)


def build_all(out_dir: str | None = None) -> dict[str, str]:
    """(Re)generate the bundled CSVs. Returns {name: path}."""
    from pathlib import Path

    from auphoria.sample_data import _DATA_DIR

    target = Path(out_dir) if out_dir else _DATA_DIR
    target.mkdir(parents=True, exist_ok=True)

    def to_csv(df: pd.DataFrame, name: str) -> str:
        path = target / f"{name}.csv"
        df.to_csv(path, index=False, na_rep="")  # blank cells, no imputation
        return str(path)

    out = {
        "plant_growth": to_csv(plant_growth(), "plant_growth"),
        "survey": to_csv(survey(), "survey"),
        "training": to_csv(training(), "training"),
        "diets": to_csv(diets(), "diets"),
        "growth_cov": to_csv(growth_cov(), "growth_cov"),
        "schools": to_csv(schools(), "schools"),
        "psych": to_csv(psych(), "psych"),
        "survival": to_csv(survival(), "survival"),
        "diagnosis": to_csv(diagnosis(), "diagnosis"),
        "features": to_csv(features(), "features"),
        "cohort": to_csv(cohort(), "cohort"),
        "repeated": to_csv(repeated(), "repeated"),
        "bland_altman": to_csv(bland_altman(), "bland_altman"),
        "panel": to_csv(panel(), "panel"),
        "time_series": to_csv(time_series(), "time_series"),
        "counts": to_csv(counts(), "counts"),
        "sem_items": to_csv(sem_items(), "sem_items"),
        "field_trial": to_csv(field_trial(), "field_trial"),
        "sequences": to_csv(sequences(), "sequences"),
        "alignment_pairs": to_csv(alignment_pairs(), "alignment_pairs"),
        "genotypes": to_csv(genotypes(), "genotypes"),
    }
    return out


def growth_cov(n_per_group: int = 20, seed: int = 31) -> pd.DataFrame:
    """Two treatments + a numeric covariate (ANCOVA demo).

    Outcome (final height) depends on a baseline covariate and a treatment
    effect, so ANCOVA can separate the two. Groups are independent.
    """
    rng = np.random.default_rng(seed)
    group = (["control"] * n_per_group + ["treatment"] * n_per_group)
    baseline = rng.normal(20.0, 3.0, len(group))
    effect = np.where(np.asarray(group) == "treatment", 4.0, 0.0)
    final = 0.8 * baseline + effect + rng.normal(0, 1.5, len(group))
    return pd.DataFrame({
        "group": group,
        "baseline_cm": np.round(baseline, 1).astype(float),
        "final_cm": np.round(final, 1).astype(float),
    })


def schools(n_schools: int = 6, per_school: int = 12, seed: int = 37) -> pd.DataFrame:
    """Pupils nested in schools (mixed-effects / multilevel demo).

    Outcome (test score) has a fixed teaching-method effect plus a random
    per-school intercept, so a mixed model (not a plain regression) is the
    honest tool.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_schools):
        intercept = rng.normal(0, 3.0)  # random school effect
        method = "new" if s % 2 == 0 else "old"
        n = per_school
        score = 60 + intercept + (4.0 if method == "new" else 0.0) \
            + rng.normal(0, 2.5, n)
        rows.append(pd.DataFrame({
            "school": [f"sch{s+1}"] * n,
            "method": [method] * n,
            "score": np.round(score, 1).astype(float),
        }))
    return pd.concat(rows, ignore_index=True)


def sem_items(n_rows: int = 300, seed: int = 43) -> pd.DataFrame:
    """One-factor questionnaire items (structural-equation-model demo).

    Four items all load onto a single latent factor with strong, positive
    loadings, so a one-factor CFA fits well (CFI near 1, RMSEA < 0.06). Only
    the numeric item columns are returned because the CFA treats every
    numeric column as an item.
    """
    rng = np.random.default_rng(seed)
    F = rng.normal(0, 1, n_rows)
    loadings = [0.80, 0.70, 0.75, 0.65]
    items = {}
    for i, lam in enumerate(loadings, start=1):
        items[f"item{i}"] = np.round(lam * F + rng.normal(0, 0.6, n_rows), 2)
    return pd.DataFrame(items)


def psych(n_rows: int = 120, seed: int = 41) -> pd.DataFrame:
    """Several correlated questionnaire items (PCA / EFA demo).

    Items load on two latent factors, so the correlation structure is
    non-trivial and PCA/EFA can recover structure.
    """
    rng = np.random.default_rng(seed)
    f1 = rng.normal(0, 1, n_rows)
    f2 = rng.normal(0, 1, n_rows)
    items = {}
    for i in range(1, 6):   # items 1-5 load on factor 1
        items[f"item{i}"] = np.round(0.8 * f1 + rng.normal(0, 0.6, n_rows), 2)
    for i in range(6, 11):  # items 6-10 load on factor 2
        items[f"item{i}"] = np.round(0.8 * f2 + rng.normal(0, 0.6, n_rows), 2)
    df = pd.DataFrame(items)
    df["group"] = rng.choice(["A", "B"], size=n_rows)
    return df


def survival(n_per_group: int = 40, seed: int = 47) -> pd.DataFrame:
    """Time-to-event data (Kaplan-Meier / Cox demo).

    Two treatment groups with different hazard; some observations are
    right-censored (event = 0). A continuous covariate (age) is included for
    Cox.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for g, base_hazard in (("control", 0.06), ("drug", 0.03)):
        for _ in range(n_per_group):
            age = rng.integers(40, 80)
            hazard = base_hazard * (1 + (age - 60) * 0.01)
            # Exponential survival time; censor after a fixed horizon.
            time = rng.exponential(1.0 / hazard)
            event = 1 if time < 24 else 0
            time = min(time, 24)
            rows.append({"group": g, "time_months": round(time, 2),
                         "event": event, "age": int(age)})
    return pd.DataFrame(rows)


def diagnosis(n_rows: int = 100, seed: int = 53) -> pd.DataFrame:
    """A test score + true disease status (diagnostic / ROC demo)."""
    rng = np.random.default_rng(seed)
    true = rng.binomial(1, 0.35, n_rows)  # ~35% diseased
    score = 3.0 * true + rng.normal(0, 1.2, n_rows)
    return pd.DataFrame({
        "true_status": true.astype(int),
        "test_score": np.round(score, 2).astype(float),
    })


def features(n_rows: int = 150, seed: int = 59) -> pd.DataFrame:
    """Feature matrix + label + numeric target (ML-eval demos)."""
    rng = np.random.default_rng(seed)
    x1 = rng.normal(0, 1, n_rows)
    x2 = rng.normal(0, 1, n_rows)
    x3 = rng.normal(0, 1, n_rows)
    label = (1.5 * x1 - 0.8 * x2 + rng.normal(0, 0.8, n_rows) > 0).astype(int)
    target = 2.0 * x1 + 1.5 * x2 - 0.5 * x3 + rng.normal(0, 0.5, n_rows)
    df = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3,
                       "label": label, "target": target})
    df = df.round(3)
    return df


def field_trial(n_blocks: int = 4, seed: int = 83) -> pd.DataFrame:
    """A designed field experiment for the experimental-design demo.

    RCBD layout: 4 blocks x 3 treatments (A/B/C) with a clear treatment
    effect (means 12/15/18) and a block effect, plus row/col and a second
    factor so CRD / RCBD / Latin / factorial demos can all run on it.
    """
    rng = np.random.default_rng(seed)
    rows = []
    treatment_means = {"A": 12.0, "B": 15.0, "C": 18.0}
    block_effect = [0.0, 1.5, -1.0, 2.0]
    for b, be in enumerate(block_effect, start=1):
        for t, tm in treatment_means.items():
            for rep, fb in enumerate(["low", "high"], start=1):
                rows.append({
                    "plot": f"b{b}_{t}{rep}",
                    "block": f"b{b}",
                    "treatment": t,
                    "row": f"r{b}",
                    "col": f"c{rep}",
                    "factor_b": fb,
                    "yield": round(tm + be + rng.normal(0, 1.5), 1),
                })
    return pd.DataFrame(rows)


def sequences(n_rows: int = 12, seed: int = 89) -> pd.DataFrame:
    """A text column of DNA sequences (sequence-composition demo).

    Mix of plausible coding-like sequences with realistic GC content and a
    couple of short ones; used as the composition and translation sample.
    """
    rng = np.random.default_rng(seed)
    seqs = []
    for _ in range(n_rows):
        length = int(rng.integers(24, 90))
        gc = rng.uniform(0.35, 0.65)
        bases = rng.choice(["A", "T", "G", "C"], size=length,
                           p=[(1 - gc) / 2, (1 - gc) / 2, gc / 2, gc / 2])
        seqs.append("".join(bases))
    return pd.DataFrame({"sequence": seqs})


def alignment_pairs(n_pairs: int = 6, seed: int = 97) -> pd.DataFrame:
    """Sequence pairs with a conserved core (sequence-alignment demo).

    Each pair shares a 10-bp core with random flanks, so the local
    alignment finds the core and the global alignment reports high identity.
    """
    rng = np.random.default_rng(seed)
    core = "ATGCGTACGT"
    rows = []
    for _ in range(n_pairs):
        def _flank() -> str:
            n = int(rng.integers(3, 8))
            return "".join(rng.choice(list("ACGT"), size=n))
        a = _flank() + core + _flank()
        b = _flank() + core + _flank()
        rows.append({"sequence_a": a, "sequence_b": b})
    return pd.DataFrame(rows)


def genotypes(n_markers: int = 10, seed: int = 101) -> pd.DataFrame:
    """Biallelic genotype counts (hardy-weinberg demo).

    Mixed markers: most near equilibrium, a few deliberately deviating
    (e.g. an excess of homozygotes), so the demo shows both verdicts.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_markers):
        n = int(rng.integers(60, 140))
        p = rng.uniform(0.2, 0.8)
        if i % 4 == 3:  # deviate: excess homozygotes
            hom = int(n * p) + int(n * 0.15)
            het = max(0, n - 2 * hom)
        else:
            aa = n * p * p
            het = 2 * n * p * (1 - p)
            hom = n - aa - het
            hom = int(round(aa + rng.normal(0, n * 0.01)))
        het = max(0, int(round(n - 2 * hom)))
        alt = max(0, n - hom - het)
        rows.append({"n_homo_ref": hom, "n_het": het, "n_homo_alt": alt})
    return pd.DataFrame(rows)
