"""Environment and package-version reporting for reproducible runs."""

from __future__ import annotations

import platform

import auphoria.core.version as _ver

_PACKAGE_IMPORTS = {
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "statsmodels": "statsmodels",
    "scikit-learn": "sklearn",
}


def python_version() -> str:
    return platform.python_version()


def platform_name() -> str:
    return platform.platform()


def package_versions() -> dict[str, str]:
    """Return {package: version} for the scientific stack."""
    out: dict[str, str] = {"auphoria": _ver.__version__}
    for name, module in _PACKAGE_IMPORTS.items():
        try:
            mod = __import__(module)
            out[name] = str(getattr(mod, "__version__", "?"))
        except Exception:  # noqa: BLE001 - never fail to report
            out[name] = "?"
    return out


def environment_info() -> dict[str, str]:
    """Everything useful about the run environment."""
    info = package_versions()
    info["python"] = python_version()
    info["platform"] = platform_name()
    return info
