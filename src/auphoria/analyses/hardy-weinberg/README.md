# Hardy-Weinberg Equilibrium (`hardy-weinberg`)

Tests whether observed **biallelic genotype counts** are consistent with
Hardy-Weinberg equilibrium, by comparing them with the expectations
derived from the observed allele frequencies (chi-square goodness-of-fit,
1 df).

## When to use it

- You have genotype counts at a locus (or many loci) and want the
  equilibrium check every population-genetics course teaches.
- Deviation hints at inbreeding, structure, selection or genotyping error —
  worth investigating, never proof of any single cause.

## Expected input shape

One row per marker/locus with three count columns:

| n_homo_ref | n_het | n_homo_alt |
|-----------|-------|------------|
| 30        | 50    | 20         |
| 40        | 20    | 40         |

(`n_homo_ref` = AA, `n_het` = Aa, `n_homo_alt` = aa.)

## What you get

- **Observed vs expected genotype counts** per marker.
- **Allele frequencies** (p for A, q for a).
- **Chi-square table** (statistic, df=1, p-value).
- Per-row verdict: `consistent` or `deviation`.

## Guardrails

- Negative counts refused; zero-total markers refused.
- Small expected counts (< 5) raise a WARN that the chi-square
  approximation is unreliable.
- Decimal counts are rounded with a warning.

## Honest limits

- Failing to reject is *not* proof of equilibrium (low power at small n).
- Testing many markers row-by-row inflates false positives — correct for
  multiple testing when you test a whole-genome table.
