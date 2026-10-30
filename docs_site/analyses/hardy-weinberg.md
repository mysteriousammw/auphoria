# Hardy-Weinberg Equilibrium Test

`hardy-weinberg` · maturity: **experimental**

Validation reference: Classic textbook example: counts AA=30, Aa=50, aa=20 -> n=100, p=0.55, q=0.45; expected AA=30.25, Aa=49.5, aa=20.25; chi2 = 0.0027, df=1, p ≈ 0.958 (hand-computed, cross-checked vs scipy.stats.chisquare).  


## What it does

Tests whether observed genotype counts at a biallelic locus are consistent with Hardy-Weinberg equilibrium (HWE): expected genotype frequencies are computed from the observed allele frequencies and compared with the observed counts via a chi-square goodness-of-fit test (1 degree of freedom). Reports observed vs expected counts, allele frequencies, the chi-square statistic and p-value, and a PASS/WARN verdict. The classic first check in population genetics — deviation hints at selection, inbreeding, or genotyping error.

## What you need

- **n_homo_ref** (numeric-column, required): Count of homozygous genotype AA (reference allele A).
- **n_het** (numeric-column, required): Count of heterozygous genotype Aa.
- **n_homo_alt** (numeric-column, required): Count of homozygous genotype aa (alternate allele a).

## Options

- `alpha` (default 0.05): Significance level for the chi-square test.

## What you get out

- observed vs expected genotype counts table (per marker/row)
- allele frequency table (p for A, q for a)
- chi-square test table (statistic, df, p-value)
- PASS/WARN/HWE verdict per row
- methods.txt paragraph
- report.html

## Assumptions

- Biallelic locus only (two alleles, three genotypes AA/Aa/aa).
- Counts are non-negative integers (rounded, with a warning if decimals appear).
- Expected counts are large enough for the chi-square approximation (expected >= 5 per cell in most cells; otherwise a warning is issued).
- Random mating, no selection/migration/mutation in the reference population.

## Limitations

- A non-significant test does NOT prove equilibrium — it only fails to reject it; small samples are underpowered.
- Deviation from HWE has many causes (inbreeding, population structure, genotyping error, selection); the test alone cannot say which.
- Testing many markers inflates the false-positive rate — apply a multiple-testing correction when a whole-genome table is tested row by row.

## Run it

```bash
auphoria run --data YOURFILE.csv --analysis hardy-weinberg --extra n_homo_ref=<n_homo_ref> --extra n_het=<n_het> --extra n_homo_alt=<n_homo_alt>
```
