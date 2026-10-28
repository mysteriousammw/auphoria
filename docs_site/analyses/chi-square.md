# Chi-Square Test of Independence

`chi-square` · maturity: **experimental**

Validation reference: 2x2 table [[30,10],[10,30]]; cross-checked vs scipy.stats.chi2_contingency  


## What it does

Tests whether two categorical variables are associated — whether the pattern of counts in one variable differs across the categories of the other (for example, treatment x outcome category).

## What you need

- **var1** (categorical-column, required): First categorical variable (e.g. treatment group).
- **var2** (categorical-column, required): Second categorical variable (e.g. outcome category).

## Options

- `alpha` (default 0.05): Significance level (probability of a false positive you accept).

## What you get out

- contingency table with counts and a row-total column
- row percentage table (percentages within each row, with totals)
- chi-square test result table (chi-square, df, p-value, Cramer's V)
- stacked bar figure of proportions within each var1 category
- methods.txt paragraph
- report.html

## Assumptions

- The categories of each variable are mutually exclusive — every observation belongs to exactly one category of each variable.
- The expected cell count is at least 5 in every cell of the table; when any expected count is 5 or fewer the result is flagged as approximate and Fisher's exact test is recommended (for 2x2 tables).
- Observations are independent of each other (the same subject is not measured twice across the rows of the table).

## Limitations

- A significant p-value means the pattern of counts differs between the groups, NOT that one variable caused the other; association is not causation.
- Chi-square does not say which category drives the association, or how large the effect is in absolute terms — Cramer's V only expresses strength relative to the strongest possible association.
- Missing values in the two chosen columns are counted, excluded, and reported; they are never imputed.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis chi-square --extra var1=<var1> --extra var2=<var2>
```
