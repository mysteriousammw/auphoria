# Acknowledgements

## Open-source libraries

AUPHORIA is built on the shoulders of established open-source scientific and
Python libraries, and we are grateful to their maintainers and contributors.
These are the core runtime dependencies declared in `pyproject.toml`; each
keeps its own licence (permissive open-source), which governs its use in
AUPHORIA:

| Library | Licence (as declared by the project) | Used for |
|---------|--------------------------------------|----------|
| NumPy | BSD-3-Clause | array / numerical computation |
| pandas | BSD-3-Clause | data loading, cleaning, tabular results |
| SciPy | BSD-3-Clause | statistical tests and distributions |
| Matplotlib | Matplotlib (BSD-style / PSF-based) | figures in reports |
| PyYAML | MIT | manifests and configuration |
| Typer | MIT | command-line interface |
| Pydantic | MIT | manifest validation |
| Jinja2 | BSD-3-Clause | HTML report rendering |

Optional extras add further permissive libraries — for example
`openpyxl` (BSD) for Excel, `python-docx` (MIT) for Word output, and the
discipline-pack libraries `statsmodels`, `scikit-learn`, `PyDESeq2` and
`gseapy` (BSD / MIT / Apache-2.0-style), each also under permissive licences.

We are also grateful to the wider open-source Python ecosystem and to the
developers of the pip/Python tooling that distributes AUPHORIA.

## Funding and institutional support

[CONFIRM] - Funding and institutional acknowledgements. No university or
institution is named by default; add your funders and host institutions here
once confirmed.

## AI assistance

AI tools helped create this project. All results the software produces come
from deterministic open-source libraries, not from an AI model. Maintainers
are responsible for the content and for checking it.