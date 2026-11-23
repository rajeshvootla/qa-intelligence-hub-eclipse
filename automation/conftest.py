"""Shared fixtures for the Playwright automation suite.

Run from the ``automation`` folder:
    pytest --base-url https://your-app.example.com
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from framework.ui_actions import UiActions  # noqa: E402


@pytest.fixture
def ui(page) -> UiActions:
    timeout = int(os.getenv("UI_TIMEOUT_MS", "10000"))
    page.set_default_timeout(timeout)
    return UiActions(page, timeout_ms=timeout)


def pytest_configure(config):
    config.addinivalue_line("markers", "testrail(case_id): link a test to a TestRail case id")
