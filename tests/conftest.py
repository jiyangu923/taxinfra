"""Pytest configuration and shared fixtures."""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "filterwarnings",
        "ignore::DeprecationWarning:httpx",
    )
