import ast

import pytest

from core.manual_parser import parse_csv, parse_text
from core.playwright_generator import build_module, convert_action, convert_expected, generate_test


def test_parse_text_multiple_cases_with_expected():
    cases = parse_text(
        """Title: Login
ID: C1
1. Navigate to /login
2. Click "Login" button
Expected: "Welcome" is displayed

Title: Logout
1. Click "Logout"
"""
    )
    assert [c.title for c in cases] == ["Login", "Logout"]
    assert cases[0].case_id == "C1"
    assert cases[0].steps[1].expected == '"Welcome" is displayed'


def test_parse_csv_testrail_multiline_steps():
    content = (
        'ID,Title,Steps (Step),Steps (Expected Result)\n'
        'C5,Search,"1. Navigate to /\n2. Enter ""shoes"" in ""Search""","1. Home shown\n2. ""shoes"" is displayed"\n'
    )
    [case] = parse_csv(content)
    assert case.case_id == "C5"
    assert [s.action for s in case.steps] == ["Navigate to /", 'Enter "shoes" in "Search"']
    assert case.steps[1].expected == '"shoes" is displayed'


@pytest.mark.parametrize(
    "step, expected",
    [
        ("Navigate to https://x.io/login", ["ui.goto('https://x.io/login')"]),
        ("Open the application", ["ui.goto('/')"]),
        ('Enter "bob" in "Username"', ["ui.fill('Username', 'bob')"]),
        ('Type into "Search" the text "shoes"', ["ui.fill('Search', 'shoes')"]),
        ('Enter username "bob"', ["ui.fill('username', 'bob')"]),
        ('Enter "bob" in the user name field', ["ui.fill('user name', 'bob')"]),
        ('Click "Login" button', ["ui.click('Login', role='button')"]),
        ("Click on Submit button", ["ui.click('Submit', role='button')"]),
        ('Select "India" from "Country"', ["ui.select('Country', 'India')"]),
        ('Uncheck "Remember me"', ["ui.uncheck('Remember me')"]),
        ("Press Enter key", ["ui.press('Enter')"]),
        ("Wait 2 seconds", ["page.wait_for_timeout(2000)"]),
        ('Verify "Products" is displayed', ["ui.expect_visible('Products')"]),
        ("Do something unusual", None),
    ],
)
def test_convert_action(step, expected):
    assert convert_action(step) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ('"Error" is not displayed', ["ui.expect_hidden('Error')"]),
        ('URL contains "/dashboard"', ["ui.expect_url_contains('/dashboard')"]),
        ("User is redirected to inventory page", ["ui.expect_url_contains('inventory')"]),
        ("Dashboard page is displayed", ["ui.expect_visible('Dashboard')"]),
        ('"Save" button is disabled', ["ui.expect_disabled('Save')"]),
    ],
)
def test_convert_expected(text, expected):
    assert convert_expected(text) == expected


def test_generated_module_is_valid_python_and_reports_todos():
    cases = parse_text('Title: A\nID: C9\n1. Navigate to /\n2. Do magic\nTitle: A\n1. Click "X"')
    tests = [generate_test(c) for c in cases]
    module = build_module(tests)
    ast.parse(module)
    assert tests[0].unmapped_steps == ["Do magic"]
    assert "@pytest.mark.testrail('C9')" in module
    assert "def test_c9_a(" in module and "def test_a(" in module
