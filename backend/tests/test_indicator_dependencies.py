"""Dependency proof tests for the indicator feature layer."""

from __future__ import annotations

import importlib
import importlib.util

REQUIRED_INDICATOR_MODULES = {
    "pandas_ta_classic": "pandas-ta-classic",
    "talib": "TA-Lib",
    "vectorbt": "vectorbt",
}


def test_indicator_dependency_imports() -> None:
    missing = [
        package_name
        for module_name, package_name in REQUIRED_INDICATOR_MODULES.items()
        if importlib.util.find_spec(module_name) is None
    ]

    assert missing == []


def test_indicator_dependency_versions_are_present() -> None:
    versions = {
        package_name: getattr(importlib.import_module(module_name), "__version__", None)
        for module_name, package_name in REQUIRED_INDICATOR_MODULES.items()
    }

    assert versions["pandas-ta-classic"]
    assert versions["TA-Lib"]
    assert versions["vectorbt"]
