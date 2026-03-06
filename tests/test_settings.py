"""Verify downstream settings modules export all required base settings."""

import importlib


def _get_uppercase_attrs(module):
    return {name for name in dir(module) if name.isupper() and not name.startswith("_")}


def test_prod_settings_have_all_base_settings():
    base = importlib.import_module("wine_cellar.conf.settings")
    prod = importlib.import_module("wine_cellar.conf.prod")
    base_attrs = _get_uppercase_attrs(base)
    prod_attrs = _get_uppercase_attrs(prod)
    missing = base_attrs - prod_attrs
    assert not missing, f"prod.py missing settings from base: {missing}"


def test_test_settings_have_all_base_settings():
    base = importlib.import_module("wine_cellar.conf.settings")
    test = importlib.import_module("wine_cellar.conf.test")
    base_attrs = _get_uppercase_attrs(base)
    test_attrs = _get_uppercase_attrs(test)
    missing = base_attrs - test_attrs
    assert not missing, f"test.py missing settings from base: {missing}"
