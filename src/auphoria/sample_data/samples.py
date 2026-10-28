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
