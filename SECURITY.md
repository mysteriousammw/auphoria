# Security Policy

## Supported versions

AUPHORIA is pre-1.0 software. Only the latest release on the default branch
receives security fixes.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Instead email
the maintainers directly (address managed at https://github.com/mysteriousammw/auphoria) with:

1. A short description of the issue.
2. The steps or code needed to reproduce it.
3. The version of AUPHORIA and its dependencies.

You will receive a response as soon as possible.

## Scope

AUPHORIA runs entirely on the user's own computer (or Google Colab) and
makes **no network calls at run time**. It reads the data files and Python
packages already present on the machine. The main security considerations
are therefore:

- **Data files are treated as untrusted input.** AUPHORIA reads CSV/TSV/XLSX
  files and produces figures and HTML reports locally; it never executes
  code from them. Adding parsers for new file formats is a security-sensitive
  change and will be reviewed with this lens.
- **Ancillary dependencies** (NumPy, pandas, SciPy, Matplotlib, PyYAML) are
  pinned to permissive ranges in `pyproject.toml`; we aim to stay current
  with their security releases without breaking the supported Python range.

## Disclosure policy

We will acknowledge the report, investigate, and keep the reporter informed.
A coordinated fix is preferred; we will credit the reporter unless they
prefer otherwise.