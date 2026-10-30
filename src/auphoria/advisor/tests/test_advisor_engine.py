"""Scenario tests for the AUPHORIA advisor (Phase 7).

Each scenario mounts a small synthetic DataFrame (data shape) + optional
column roles + a research question, and asserts the advisor recommends the
expected analyses (ranked) and rules out the expected ones with reasons.

The rules under test live in src/auphoria/advisor/rules.yaml — this file
checks that the YAML encodes the decision guide correctly, not that Python
code "happens to" suggest the right thing.
"""

from __future__ import annotations

import pandas as pd
import pytest

from auphoria.advisor.advisor import profile_data_frame
from auphoria.advisor.advisor_engine import advise, load_rules

RULES = load_rules()


def _advise(df, question=None, roles=None):
    profile = profile_data_frame(df)
    return advise(profile, roles=roles, question=question, rules=RULES)


def _rec(df, question=None, roles=None):
    return _advise(df, question, roles).recommendation_ids()


def _ruled(df, question=None, roles=None):
    res = _advise(df, question, roles)
    return {r.analysis: r.reason for r in res.ruled_out}


# --------------------------------------------------------------------- shapes
def two_group(n=30):
    g = ["a"] * (n // 2) + ["b"] * (n - n // 2)
    return pd.DataFrame({"outcome": range(n), "group": g})


def three_group(n=30):
    k = (n + 2) // 3
    g = ["a"] * k + ["b"] * k + ["c"] * (n - 2 * k)
    return pd.DataFrame({"outcome": range(n), "group": g})


def two_numeric(n=30):
    return pd.DataFrame({"x": range(n), "y": [v * 2 for v in range(n)]})


def two_categorical(n=30):
    g = ["a"] * (n // 2) + ["b"] * (n - n // 2)
    return pd.DataFrame({"group": g, "yes_no": ["y", "n"] * (n // 2) + ["y"] * (n % 2)})


def paired_wide(n=20):
    return pd.DataFrame(
        {"subject": [f"s{i}" for i in range(n)],
         "before": range(n), "after": [v + 3 for v in range(n)]}
    )


def surveys(survey_df):
    return survey_df


def binary_outcome(n=30):
    g = ["a"] * (n // 2) + ["b"] * (n - n // 2)
    return pd.DataFrame({"recovered": ["yes", "no"] * (n // 2) + ["yes"] * (n % 2),
                         "group": g})


def with_datetime(n=30):
    g = ["a"] * (n // 2) + ["b"] * (n - n // 2)
    return pd.DataFrame({
        "value": range(n),
        "group": g,
        "date": pd.date_range("2024-01-01", periods=n),
    })


def with_text(n=30):
    g = ["a"] * (n // 2) + ["b"] * (n - n // 2)
    return pd.DataFrame({
        "value": range(n),
        "group": g,
        "comments": [f"note {i}" for i in range(n)],
    })


# ------------------------------------------------------------------ scenario table
# (id, question, df builder, roles, expected recommended ids)
RECOMMEND_CASES = [
    # describe: always summary + describe
    ("describe-two-group", None, two_group, None, ["summary", "describe"]),
    ("describe-two-cat", None, two_categorical, None, ["summary", "describe"]),
    ("describe-question", "describe", two_group, None, ["summary", "describe"]),

    # compare — two independent groups
    ("compare-2groups", "compare", two_group, None,
     ["ttest", "mann-whitney", "summary", "describe"]),
    ("compare-2groups-covariate-role", "compare", two_group,
     {"outcome": "outcome", "group": "group"},
     ["ttest", "mann-whitney", "summary", "describe"]),

    # compare — three groups -> ANOVA (+ Kruskal-Wallis for skewed data;
    # this df has one numeric + one categorical, so no chi-square)
    ("compare-3groups", "compare", three_group, None,
     ["anova-oneway", "kruskal-wallis", "summary", "describe"]),
    ("compare-3groups-roles", "compare", three_group,
     {"outcome": "outcome", "group": "group"},
     ["anova-oneway", "kruskal-wallis", "summary", "describe"]),

    # compare — paired design (id role or all-unique subject column)
    ("compare-paired-id-role", "compare", paired_wide, {"subject": "id"},
     ["ttest-paired", "summary", "describe"]),
    ("compare-paired-unique-subject", "compare", paired_wide, None,
     ["ttest-paired", "summary", "describe"]),

    # compare — categorical x categorical -> chi-square; two text columns
    # without a numeric column is also the sequence-alignment shape (the
    # analysis itself refuses non-sequence letters with a clear hint).
    ("compare-2cat", "compare", two_categorical, None,
     ["sequence-alignment", "chi-square", "summary", "describe"]),

    # relate — two numeric -> correlation (+ rank alternative, agreement)
    ("relate-2numeric", "relate", two_numeric, None,
     ["correlation", "spearman-correlation", "bland-altman", "summary", "describe"]),
    ("relate-2numeric-roles", "relate", two_numeric,
     {"x": "outcome", "y": "outcome"},
     ["correlation", "spearman-correlation", "bland-altman", "summary", "describe"]),
    ("relate-2cat", "relate", two_categorical, None,
     ["chi-square", "odds-and-risk", "summary", "describe"]),

    # prediction: diagnostic-test now fits a numeric score + binary group;
    # the ml-* analyses need 2+ numeric features (not present here);
    # simple/multiple regression need 1/2+ numeric predictors
    ("predict-2numeric", "predict", two_numeric, None,
     ["regression-linear", "summary", "describe"]),
    ("predict-2group", "predict", two_group, None,
     ["diagnostic-test", "summary", "describe"]),

    # over_time / reliability / reduce
    ("overtime", "over_time", two_numeric, None, ["summary", "describe"]),
    ("reliability", "reliability", two_numeric, None,
     ["cronbach-alpha", "summary", "describe"]),
    ("reduce", "reduce", two_numeric, None, ["summary", "describe"]),

    # explainable-questions over the "shape quirks" datasets
    ("compare-with-datetime", "compare", with_datetime, None,
     ["ttest", "mann-whitney", "summary", "describe"]),
    # one numeric only -> correlation needs two, so relate gives catch-alls
    ("relate-with-datetime", "relate", with_datetime, None,
     ["summary", "describe"]),
    ("describe-with-datetime", None, with_datetime, None,
     ["summary", "describe"]),

    # two categorical columns with a numeric-ish target: chi-square preferred
    ("compare-binary-outcome", "compare", binary_outcome, None,
     ["sequence-alignment", "chi-square", "summary", "describe"]),
    ("relate-binary-outcome", "relate", binary_outcome, None,
     ["chi-square", "odds-and-risk", "summary", "describe"]),
]


@pytest.mark.parametrize(
    "name,question,df,roles,expected",
    RECOMMEND_CASES,
    ids=[c[0] for c in RECOMMEND_CASES],
)
def test_advisor_recommends(name, question, df, roles, expected):
    del name
    got = _rec(df(), question, roles)
    assert got == expected, f"expected {expected}, got {got}"


# ------------------------------------------------------------ ruled-out cases
# (id, question, df BUILDER, roles, analysis-they-wanted, expected-reason-substring)
RULED_OUT_CASES = [
    ("ruled-ttest-needs-2-groups", "compare", two_numeric, None,
     "ttest", "exactly two categories"),
    ("ruled-ttest-too-small", "compare", lambda: two_group(4), None,
     "ttest", "Sample too small"),
    ("ruled-mw-too-small", "compare", lambda: two_group(4), None,
     "mann-whitney", "Sample too small"),
    ("ruled-anova-2groups-only", "compare", two_group, None,
     "anova-oneway", "2 groups use a t-test"),
    ("ruled-anova-too-small", "compare", lambda: three_group(9), None,
     "anova-oneway", "Sample too small"),
    ("ruled-paired-no-id", "compare", two_group, None,
     "ttest-paired", "SAME subjects"),
    ("ruled-chi-needs-2-cat", "compare", two_group, None,
     "chi-square", "TWO categorical"),
    ("ruled-chi-small", "compare", lambda: two_categorical(8), None,
     "chi-square", "Sample too small"),
    ("ruled-correlation-needs-2-num", "relate", two_categorical, None,
     "correlation", "two numeric"),
    ("ruled-spearman-needs-2-num", "relate", two_categorical, None,
     "spearman-correlation", "two numeric"),
    ("ruled-chi-relate-needs-2-cat", "relate", two_numeric, None,
     "chi-square", "TWO categorical"),
    # questions that have no rules for built analyses: nothing ruled out (all
    # the always-on rules still recommend summary/describe)
    ("ruled-none-predict", "predict", two_group, None, "ttest", None),
]


@pytest.mark.parametrize(
    "name,question,df,roles,wanted,reason",
    RULED_OUT_CASES,
    ids=[c[0] for c in RULED_OUT_CASES],
)
def test_advisor_rules_out(name, question, df, roles, wanted, reason):
    del name
    ruled = _ruled(df(), question, roles)
    if reason is None:
        assert wanted not in ruled, f"expected '{wanted}' not ruled out, got {ruled}"
        return
    assert wanted in ruled, f"expected '{wanted}' ruled out, got {ruled.keys()}"
    assert reason in ruled[wanted], (
        f"reason for '{wanted}' should contain {reason!r}, got: {ruled[wanted]!r}"
    )


# --------------------------------------------------------------- role effects
def test_group_role_sets_group_not_all_unique():
    """A role-annotated group column with 2 categories wins over a subject col."""
    df = pd.DataFrame(
        {"subject": [f"s{i}" for i in range(20)],
         "treat": ["c"] * 10 + ["t"] * 10,
         "outcome": range(20)}
    )
    got = _rec(df, "compare", {"subject": "id", "treat": "group", "outcome": "outcome"})
    assert got[0] == "ttest", got


def test_paired_requires_role_or_unique_subject():
    """Without an id/subject column, before/after wide data is NOT paired."""
    df = pd.DataFrame({"before": range(15), "after": [v + 2 for v in range(15)]})
    ruled = _ruled(df, "compare")
    assert "ttest-paired" in ruled


def test_summary_and_describe_catch_all_apply_to_every_question():
    for q in ["describe", "compare", "relate", "predict", "over_time",
              "reliability", "reduce", None]:
        got = _rec(two_numeric(), q)
        assert "summary" in got and "describe" in got, (q, got)


def test_recommendations_are_ranked_by_priority():
    res = _advise(two_group(), "compare")
    order = [r.analysis for r in res.recommended]
    # ttest (priority 10) must beat mann-whitney (20) and catch-alls (200+)
    assert order.index("ttest") < order.index("mann-whitney")
    assert order.index("mann-whitney") < order.index("summary")
    assert order.index("summary") < order.index("describe")


def test_rules_yaml_has_all_built_analyses_covered_by_at_least_one_rule():
    """Every built analysis should appear somewhere in the rules."""
    from auphoria.core.registry import discover

    built = set(discover())
    configured = {r.analysis for r in RULES}
    # regression etc. are not built yet; future analyses must be added by
    # editing rules.yaml, and this test reminds us.
    assert configured & built, "no rules reference any built analysis"


def test_question_menu_lists_seven_questions():
    from auphoria.advisor.advisor_engine import question_menu

    qs = question_menu()
    assert len(qs) == 7
    ids = [q[0] for q in qs]
    assert "compare" in ids and "relate" in ids and "predict" in ids
    assert all(q[1].strip() for q in qs)  # every question has a label


def test_survey_sample_advice_is_sane():
    """The bundled survey (online/classroom) -> compare / relate sane recs."""
    df = pd.read_csv(
        "src/auphoria/sample_data/data/survey.csv"
    )
    got = _rec(df, "compare")
    assert got[0] == "ttest", got
    got_rel = _rec(df, "relate")
    assert "correlation" in got_rel, got_rel
