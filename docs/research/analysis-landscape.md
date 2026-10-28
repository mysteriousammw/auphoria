# AUPHORIA — Analysis Landscape (research phase 0)

What statistical analyses do BS / MPhil / PhD students actually run in their
theses, across ten disciplines? This document records how we answered that,
what the evidence shows, the resulting analysis coverage matrix, the P1
(ship-first) list and why, and — importantly — what we could NOT verify.

Date: 2026-10-24. Phase: research only (no application code changed here).

---

## 1. Method

Evidence was gathered two ways in parallel:

1. **Five delegated web-research passes**, each covering a discipline cluster,
   instructed to prefer (in priority order):
   - university statistics / research-methods course syllabi;
   - thesis & dissertation repositories with readable methods sections;
   - journal statistical-reporting guidelines (APA JARS, ICMJE, CONSORT,
     STROBE, PRISMA, SAMPL, ASA p-value statement, NEJM policy);
   - textbook tables of contents (Rosner, Triola, Gravetter & Wallnau, etc.);
   - the analysis menus of jamovi, JASP, SPSS and R (stats packages, CRAN Task
     Views, sklearn docs) as a *proxy* for what students expect to find.
2. **Worked directly in this environment** for the two things that must be
   verified by running, not reading:
   - every proposed library was `pip install`ed under Python 3.11 and its
     Python-3.10 support resolved via `pip --dry-run --python-version 3.10`;
   - every proposed data file format was actually written and read back
     (see docs/research/library-check.md and file-formats.md).

### Honesty about estimates

Delegated agents were required to tag every finding `[EVIDENCE]` (a source
actually seen) or `[ESTIMATE]` (inferred), and to say explicitly when they had
NO direct evidence for a specific level and were extrapolating. The single
most common honesty caveat across all five reports:

> **There is no public, level-by-level (BS vs MPhil vs PhD) census of which
> statistical tests appear inside thesis methods sections.** PubMed/ProQuest
> theses are largely paywalled or not full-text-indexed per-analysis. Most
> level-specific claims below are therefore **extrapolated from (a) the depth
> of statistics courses at each level and (b) published studies / repository
> snippets**, not measured in thesis samples. Where this is the case we say so.

Two agents reported search results they could only see as search snippets
(not full pages). Everything from a "search snippet" is treated as weaker
than evidence read in full, and this matters: e.g. exact jamovi/SPSS default
checkbox states and the precise SPSS effect-size option availability-by-version
should be re-checked against the live apps before we mirror them exactly.

---

## 2. Evidence sources actually consulted (representative)

Syllabi / programmes:
- Texas Tech AAEC 3401 Agricultural Statistics (one-way ANOVA & Tukey)
  http://appserv.itts.ttu.edu/CoreCurriculumFiles/AAEC_3401_CORE.pdf
- TAMU-Commerce AEC 380 Agricultural Statistics (t-tests)
  https://inside.tamuc.edu/academics/cvSyllabi/syllabi/202520/21938.pdf
- TAMU-Commerce BSC 504 Graduate Biostatistics (t, ANOVA, Kruskal-Wallis,
  Wilcoxon/Mann-Whitney, Pearson & Spearman, linear regression)
  https://inside.tamuc.edu/academics/cvSyllabi/syllabi/202420/28848.pdf
- Univ. Illinois School of Integrative Biology — undergrad "basic statistics"
  requirement (t, ANOVA, chi-square)
  https://sib.illinois.edu/undergraduate/guidelines/basic_statistics
- Ohio State Psych 3321 (t-test, ANOVA between/within/mixed, correlation, reg)
  https://psychology.osu.edu/courses/psych-3321
- KFU (Kuwait) MPH / Purdue MPH / Case Western MPH capstone
  https://grad.ku.edu.kw/sites/default/files/..., https://hhs.purdue.edu/graduate-programs/master-of-public-health-mph/, https://case.edu/medicine/pqhs/sites/default/files/2020-04/capstone_kit.pdf
- UPenn Biostatistics for Epidemiology (chi-square, Fisher, RR/OR,
  sens/spec, logistic, ROC, Mantel-Haenszel, McNemar, Poisson, kappa,
  Kaplan-Meier, log-rank, Cox)
  https://catalog.upenn.edu/courses/bsta/bsta.pdf
- UPenn Epidemiology I/II  https://catalog.upenn.edu/courses/epid/epid.pdf
- UNSW GSOE9712 Design of Experiments (Montgomery-based: ANOVA, factorial,
  response surface)  https://www.unsw.edu.au/engineering//sites/default/files/documents/GSOE9712_Course-Outline_T1-2019.pdf
- Univ. Utah ME EN 5035/6035 DOE (one-way ANOVA, regression, factorial,
  MANOVA, RSM)  https://class-tools.app.utah.edu/syllabus/1214/12276/MEEN5035_6035_Design_of_Experiments_Syllabus_Sp2021_Revised_01.08.2021.pdf
- NTU HE3003 Econometrics II (OLS, MLE, IV, probit/logit, unit-root,
  cointegration, panel)  https://www.ntu.edu.sg/media/docs/librariesprovider117/admission/courses/he3003-econometrics-ii.pdf
- NYU Stern PhD panel econometrics (FE/RE, IV, GMM, MLE)
  https://pages.stern.nyu.edu/~wgreene/Econometrics/PanelDataOutline.htm
- UNISI / UNIPD PhD econometrics for management (FE/RE, Hausman, IV, GMM, DiD)
  https://phdeconomics.unisi.it/wp-content/uploads/sites/127/2024/12/Panel-Data-Econometrics_40.pdf
- ASU / DU / U Delaware / UW social-work PhD quantitative-methods (SEM, HLM,
  latent growth, IRT)  https://degrees.asu.edu/masters-phd/major/ASU00/LAPSYQUPHD/..., https://morgridge.du.edu/academics-advising/programs-gr/phd-research-methods-and-statistics

Thesis/dissertation methods:
- Chula (Thailand) biotechnology BS thesis (descriptive, independent t-test,
  one-way ANOVA, Pearson correlation, multiple linear regression)
  https://digital.car.chula.ac.th/chulaetd/43702/
- Student environmental thesis using ANOVA + permutation test
  https://www.diva-portal.org/smash/get/diva2:1571835/FULLTEXT01.pdf
- Marquette MS bioinformatics RNA-seq thesis (Cuffdiff/DESeq2/edgeR/limma/DESeq)
  https://epublications.marquette.edu/cgi/viewcontent.cgi?article=1587&context=theses_open
- Univ. di Padova ecology thesis (UPGMA clustering on Bray-Curtis)
  https://thesis.unipd.it/retrieve/6813265a-fa53-40a9-9a65-55b47b7ee74f/Dalla%20Bona_Riccardo.pdf
- Wayne State dissertation-methods corpus study (descriptive, correlation,
  ANOVA, t, multiple regression most common)
  https://digitalcommons.wayne.edu/oa_theses/90/
- NIT Rourkela mechanical thesis (RSM + ANOVA + regression)
  http://ethesis.nitrkl.ac.in/2480/1/thesis.pdf
- MIT economics dissertations (synthetic control, IV, NPIV, panel)
  https://dspace.mit.edu/entities/publication/7e39ba05-cb98-4924-aa3c-f0d6ce6b837b
- ERIC ed-dissertation full texts (univariate & RM ANOVA, t-tests, chi-square,
  hierarchical multiple regression)
  https://eric.ed.gov/?id=ED540181, https://eric.ed.gov/?id=ED624718

Literature / reporting guidelines:
- PLoS ONE (2025) ranking ANOVA > t-test > chi-square as most-used tests in
  theses/dissertations  https://pdfs.semanticscholar.org/4467/3ea5f5e031432abee5f3a9c49a79f3ba3efb.pdf
- PLoS ONE study of 216 public-health journal articles (descriptive >95%,
  chi-square/Fisher 25.9%, logistic regression 38.4% most common model, OR
  40.7%)  https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0179032&type=printable
- APA Journal Article Reporting Standards (effect size + CI required)
  https://www.apa.org/pubs/authors/jars.pdf ; https://www.apa.org/pubs/journals/releases/amp-amp0000191.pdf
- APA 1999 "Statistical Methods in Psychology" (Wilkinson)
  https://www.apa.org/pubs/journals/releases/amp-54-8-594.pdf
- ICMJE recommendations (CI, effect size, software/version, prespecified vs
  exploratory) https://www.icmje.org/icmje-recommendations.pdf
- SAMPL guidelines (Lang & Altman) https://www.equator-network.org/wp-content/uploads/2013/07/SAMPL-Guidelines-6-27-13.pdf
- ASA Statement on p-values https://www.amstat.org/asa/files/pdfs/P-ValueStatement.pdf
- NEJM statistical-methods editorial policy https://evidence.nejm.org/about/editorial-policies
- Demsar 2006, "Statistical Comparisons of Classifiers over Multiple Data
  Sets", JMLR — Friedman/Wilcoxon/Nemenyi for ML model comparison
  https://jmlr.org/papers/v7/demsar06a.html
- Raschka STAT 451 "Model Evaluation" lecture (k-fold CV paired t-test,
  McNemar, 5x2 CV) https://sebastianraschka.com/pdf/lecture-notes/stat451fs20/11-eval4-algo__slides.pdf

Textbooks:
- Rosner, *Fundamentals of Biostatistics* (TOC: descriptive, one-sample,
  two-sample, nonparametric, categorical, regression/correlation, multisample
  ANOVA, epidemiologic/person-time) https://faculty.cengage.com/works/9781305268920
- Triola, *Biostatistics for the Biological and Health Sciences* (t two-sample,
  matched pairs, correlation/regression incl. logistic, chi-square, one- &
  two-way ANOVA, nonparametric incl. sign/Wilcoxon/Mann-Whitney/Kruskal-Wallis,
  survival = life tables & Kaplan-Meier)
  https://www.pearson.com/en-us/subject-catalog/p/biostatistics-for-the-biological-and-health-sciences/P200000007576
- Gravetter & Wallnau, *Statistics for the Behavioral Sciences* (t, ANOVA incl.
  RM and two-factor, correlation, regression, chi-square, nonparametric)
  https://faculty.cengage.com/works/9781305504912

Software menus (student-expectation proxy):
- jamovi core: Descriptives, Independent/Paired/One-Sample t, One-Way ANOVA,
  (factorial/mixed) ANOVA, RM ANOVA, ANCOVA, MANCOVA, Correlation matrix,
  partial correlation, linear regression, binomial/multinomial/ordinal
  logistic, proportion tests, contingency tables, log-linear, reliability,
  PCA/EFA/CFA  https://docs.jamovi.org/jmv/jmv_overview.html ; https://www.jamovi.org/features.html ; https://www.jamovi.org/modules.html
- JASP: Descriptives, t-tests, ANOVA (RM, ANCOVA, MANOVA), Mixed Models,
  Regression (Correlation/Linear/Logistic/GLM), Frequencies, Factor (PCA/EFA/
  CFA), + optional ML module (clustering incl. hierarchical/DBSCAN, random
  forest, classification) https://jasp-stats.org/features/
- SPSS Analyze menu (student guide): Frequencies, Descriptives, Explore,
  Crosstabs, Compare Means (t-tests), One-Way ANOVA, GLM, Regression
  https://sscc.wisc.edu/sscc/pubs/spss/classintro/spss_students2.html ;
  jamovi SPSS-to-jamovi comparison https://docs.jamovi.org/spss2jamovi/s2j_Comparison_of_analyses.html
- R: base stats (t.test, aov, lm, cor, chisq.test, kmeans, hclust, prcomp);
  CRAN Task Views ML & Cluster https://cran.r-project.org/web/views/MachineLearning.html ; https://cran.r-project.org/web/views/Cluster.html
- scikit-learn model-selection & cross-validation user guide
  https://scikit-learn.org/stable/model_selection.html ; https://scikit-learn.org/stable/modules/cross_validation.html

---

## 3. Findings by discipline and level

The recurring core across every discipline and almost every level is:
**descriptive statistics first, then t-test / ANOVA / chi-square / correlation
& regression**, with the non-parametric counterparts (Mann-Whitney, Kruskal-
Wallis, Wilcoxon, Spearman) introduced when normality fails. Higher levels add
multivariable and specialised methods.

| Discipline | BS final-year | MPhil / MS | PhD |
|---|---|---|---|
| Agriculture & animal science | descriptive stats, t-test, one-way ANOVA + Tukey/LSD/Duncan's, chi-square [EVIDENCE: ag syllabi; RCBD thesis snippets] | ANOVA (most-used per PLoS 2025), t-test, chi-square, regression, PCA (germplasm) [EVIDENCE] | multi-factor ANOVA, RM/mixed models [ESTIMATE — no full ag PhD thesis methods read] |
| Biology & biotechnology | descriptive, t-test, one-way ANOVA, Pearson corr, multiple linear regression [EVIDENCE: Chula BS thesis] | t-test, one-way ANOVA + posthoc, Kruskal-Wallis, Wilcoxon/MWU, correlation, linear regression [EVIDENCE: BSC 504 syllabus] | Cox survival, mixed-effects, GLM [ESTIMATE extrapolated from biostat graduate context] |
| Medicine & public health | survey/cross-sectional: descriptive, chi-square, independent t, one-way ANOVA, Pearson corr, logistic regression [EVIDENCE: undergrad health studies] | chi-square/Fisher, t-test, Mann-Whitney, ANOVA, linear/MLR, logistic/multinomial/Poisson, survival, OR/RR, sens/spec [EVIDENCE: MPH & MS syllabi, UWC MPhil transcripts] | + generalized linear models for correlated data, Cox, RM, GLMM [EVIDENCE: UPenn PhD biostat core] |
| Psychology & social sciences | t-test, one/two-way ANOVA, RM ANOVA, correlation & regression, chi-square [EVIDENCE: psych syllabi] | + Mann-Whitney U, Kruskal-Wallis, Spearman, multiple regression, ANOVA/ANCOVA/MANOVA, factor, discriminant, logistic [EVIDENCE: MPhil psych/ed/social-work syllabi]; psychometrics strong (Cronbach alpha, EFA, CMA) | SEM, multilevel/HLM, latent growth, IRT, mediation, longitudinal [EVIDENCE: PhD QRM programmes]; APA JARS requires effect size + CI |
| Education | t-test (ind/paired), one-way ANOVA, chi-square, correlation, simple/multiple regression [EVIDENCE: ed stats syllabi] | + multiple regression, ANOVA/ANCOVA/MANOVA, MWU, nonparametrics [EVIDENCE] | descriptive, correlation, ANOVA, t most frequent; multiple regression most common intermediate; RM ANOVA in quasi-experimental EdD [EVIDENCE: dissertation corpus + full texts] |
| Economics & business | multiple regression, Pearson corr, ANOVA, reliability (Cronbach), descriptives, hypothesis testing; logistic in marketing [EVIDENCE: undergrad business theses] | OLS/multiple regression, logit/probit, time series & panel basics, IV [EVIDENCE: econometrics courses] | panel FE/RE, IV/GMM/2SLS, DiD, synthetic control, NPIV, shift-share [EVIDENCE: MIT theses, PhD panel courses] |
| Engineering & physics | engineering: ANOVA, DOE (factorial, RSM), regression modeling [EVIDENCE: B.Tech theses]; physics: least-squares/chi-square fitting + uncertainty propagation [EVIDENCE: physics-lab notes] | ANOVA (1-/2-way, MANOVA), factorial & fractional designs, blocking, RSM, regression, nonparametrics [EVIDENCE: UNSW/Utah/NJIT DOE syllabi] | reliability & life-data (Weibull, KS, likelihood-ratio), advanced DOE [EVIDENCE]; physics MS/PhD = same fitting toolkit at depth (OLS/WLS, MCMC-ish) [ESTIMATE] |
| Environmental science | descriptive, t-test, ANOVA (with data transformation), correlation [ESTIMATE: general + one student thesis] | NMDS/permanova/PCA-type ordination, Bray-Curtis clustering, linear models [EVIDENCE: ecology journal + UniPD thesis] | GLMM/GAMM (ecology modelling standard) [EVIDENCE: Springer/Bolker GLMM material] |
| Computer science & ML | ML evaluation: train/test, k-fold CV, accuracy/precision/recall/F1, confusion matrix, ROC/AUC, RMSE/MAE/R2; benchmark classic classifiers; hypothesis-testing for model comparison RARE at BS [EVIDENCE: sklearn + Raschka; BS split ESTIMATE] | + stratified/repeated CV, CV paired t-test, McNemar, gradient boosting/deep learning [EVIDENCE: grad ML courses] | systematic multi-dataset benchmark + Friedman/Wilcoxon/Nemenyi, McNemar, nested CV [EVIDENCE: Demsar; framing is PhD/ML-research] |
| Bioinformatics | descriptive, t-test, chi-square, correlation/regression [ESTIMATE — NO direct BS bioinformatics thesis found] | differential expression (negative-binomial: DESeq2/edgeR), FDR correction, PCA, clustering, enrichment (Fisher/hypergeometric) [EVIDENCE: Marquette MS thesis + DEG course material] | integration with ML, pathway/enrichment, multivariate genomics [ESTIMATE on the specific methods; count-based DE is EVIDENCE] |

---

## 4. Coverage matrix (discipline × level)

Legend: ✓ = evidence-backed for that level exists; ~ = reasonable estimate
(no level-specific thesis methods read); blank = not covered.

| Analysis group | Agri/Animal | Biology/Biotech | Med/PH | Psych/Soc | Education | Econ/Bus | Eng/Phys | Env Sci | CS/ML | Bioinfo |
|---|---|---|---|---|---|---|---|---|---|---|
| Descriptive summary | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | ✓ | ~ |
| Independent t-test | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | ✓ | ~ |
| Paired t-test | ✓ | ✓ | ✓ | ✓ | ~ | ~ | ✓ | ~ | | ~ |
| One-way ANOVA | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | ~ |
| Chi-square | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | | ~ |
| Correlation (Pearson) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | ~ | | ~ |
| Spearman rank | ~ | ✓ | ✓ | ✓ | ~ | ~ | | ~ | | |
| Mann-Whitney U | ~ | ✓ | ✓ | ✓ | ~ | | | | | |
| Kruskal-Wallis | ~ | ✓ | ✓ | ✓ | ✓ | | | ~ | | |
| Simple linear regression | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ~ | ✓ | ~ |
| Multiple regression | ✓ | ~ | ✓ | ✓ | ✓ | ✓ | ~ | ~ | | ~ |
| Logistic regression | ~ | | ✓ | ✓ | ~ | ✓ | | | | ~ |
| RR / OR (2x2) | ~ | | ✓ | | | | | | | |
| Kaplan-Meier survival | | | ✓ | | | | ~ | | | |
| Cox regression | | | ✓ | | | | | | | |
| Reliability (Cronbach alpha) | | | ~ | ✓ | ~ | ✓ | | | | |
| Factor analysis (EFA) | ~ | | | ✓ | ~ | | | | | ~ |
| PCA / ordination | ✓ | ~ | | ~ | | | | ✓ | ~ | ✓ |
| RM ANOVA | | | ✓ | ✓ | ✓ | | | | | |
| ANCOVA | ~ | | ~ | ✓ | ✓ | | | | | |
| ML classification eval | | | | | | | | | ✓ | ~ |
| ML regression eval | | | | | | ~ | | | ✓ | ~ |
| Clustering | ~ | | | | | ~ | | ✓ | ✓ | ✓ |
| Mixed-effects / multilevel | ~ | ~ | ✓ | ✓ | ~ | | | ✓ | | |
| Diagnostic (sens/spec/ROC) | | | ✓ | | | | | | | ~ |
| Bland-Altman / Kappa | | ~ | ✓ | ~ | | | ~ | | | |
| Panel regression | | | | | | ✓ | | | | |
| Time series | | | ~ | | | ✓ | ~ | ~ | | |
| Differential expression | | | | | | | | | | ✓ (¬binomial) |
| SEM / CFA | | | | ✓ | | | | | | |

---

## 5. The P1 (ship-first) list

P1 contains 18 analyses — under the 30 cap — chosen to cover **every**
discipline at every level with the highest-evidence, lowest-risk methods.
Rationale for the list:

1. **Start with what everyone does.** Descriptive summary, independent and
   paired t-tests, one-way ANOVA, chi-square, Pearson and Spearman correlation,
   simple and multiple regression appear in essentially every discipline at BS
   level already (Chula biotechnology thesis; ag/ed/psych syllabi; PLoS 2025
   most-used-test ranking). These are the "core pack".
2. **Non-parametrics are not optional.** Mann-Whitney U and Kruskal-Wallis are
   the standard counter when normality fails, taught in BSC 504 biostatistics
   and in behavioral/health texts; they turn a normality refusal into a usable
   answer instead of a dead end.
3. **Cover the big health/econometrics demands early.** Logistic regression and
   OR/RR are the most-reported model in public-health journal articles (PLoS:
   logistic 38.4%, OR 40.7%) and expected at MS level; Kaplan-Meier survival is
   core to any health time-to-event thesis. These cover medicine/public-health
   and economics/business's binary-outcome needs.
4. **Include the cross-cutting advanced starters that small selected fields
   need at MS+:** PCA (bioinformatics/environmental/social), reliability
   (Cronbach alpha — the mandatory first psychometrics block), and the two ML
   evaluation analyses (classification & regression) that every CS/ML and
   increasingly bioinformatics thesis needs and that no common-menu tool
   (jamovi/JASP/SPSS) covers — a genuine gap AUPHORIA can own.
5. **Everything P1 is implementable with the verified lightweight stack.**
   All P1 analyses resolve under Python 3.10-3.12 with scipy/statsmodels/
   scikit-learn/lifelines/pingouin (see library-check.md) and need no "heavy"
   dependency. Heavier methods sit in P2/P3.

Full P1 (18): summary, ttest, ttest-paired, correlation, spearman-correlation,
chi-square, anova-oneway, mann-whitney, kruskal-wallis, regression-linear,
regression-multiple, logistic-regression, odds-and-risk, kaplan-meier,
cronbach-alpha, pca, ml-classification-eval, ml-regression-eval.

P2 (next): cox-regression, clustering-kmeans, anova-repeated, ancova, friedman,
mixed-effects, factor-analysis, diagnostic-test, bland-altman.

P3 (later / heavier): panel-regression, time-series, differential-expression,
sem.

---

## 6. What we could NOT verify (explicitly)

- **No level-by-level census of analyses inside actual thesis methods
  sections exists publicly** (theses are paywalled / not full-text-indexed per
  test). Every BS-vs-MPhil-vs-PhD distinction is an estimate built from course
  depth + published studies + repository snippets.
- No direct full text of: an agriculture/animal-science **PhD** thesis methods
  section, a pure-BA **economics** thesis, a **physics MS/PhD** thesis — those
  rows are extrapolations.
- No direct BS-level bioinformatics thesis or course source was found; the BS
  bioinformatics row is estimated from general biostat entry practice.
- Whether **undergraduate psychology** theses routinely include full CFA (vs
  only Cronbach alpha + EFA) is unverified; most likely many stop at alpha/EFA.
- Exact **software default states** (which jamovi/JASP checkbox is ticked by
  default, whether SPSS's "Estimate effect sizes" table is on by default and
  only from SPSS 27+) were read from snippets and docs, not a live install —
  treat as approximate until re-checked.
- Whether **data leakage / improper CV** is prevalent in real BS/CS theses is
  asserted from guidance (Demsar notes weak practice) rather than measured.
- NEJM exact p-value decimal conventions and the specific CONSORT item wording
  came from snippet/policy text, not rendered pages.
- The **permanova/NMDS MS-vs-PhD** split could not be verified because the
  supporting ecology sources were level-unlabelled theses/journal methods.
- One planned entry reference to a "permutation test" was drawn from a single
  student thesis; it is a real method but low in P1 priority and not yet in
  the catalogue because the evidence was thin.

See docs/library-check.md for the verified dependency facts, and
docs/file-formats.md for the verified file-type support.