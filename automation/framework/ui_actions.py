"""Resilient, human-readable UI actions used by generated Playwright tests.

Each helper resolves an element from a plain-language name (as written in a
manual test case) by trying accessible locators in order: role+name, label,
placeholder, test id, and finally visible text. Resolution is retried until the
timeout so elements rendered late are still found.
"""
from __future__ import annotations

import re
from typing import Callable

from playwright.sync_api import Locator, Page, expect

CLICKABLE_ROLES = ("button", "link", "tab", "menuitem", "option", "checkbox", "radio")
_POLL_MS = 250


class UiActions:
    def __init__(self, page: Page, timeout_ms: int = 10_000):
        self.page = page
        self.timeout_ms = timeout_ms

    # ---- locator resolution -------------------------------------------------
    def _resolve(self, build: Callable[[], list[Locator]]) -> Locator:
        waited = 0
        while True:
            candidates = build()
            for loc in candidates:
                try:
                    if loc.count() > 0:
                        return loc.first
                except Exception:
                    continue
            if waited >= self.timeout_ms:
                # Return the most specific candidate so Playwright raises a clear error.
                return candidates[0].first
            self.page.wait_for_timeout(_POLL_MS)
            waited += _POLL_MS

    def clickable(self, name: str, role: str | None = None) -> Locator:
        p = self.page
        roles = (role,) if role else CLICKABLE_ROLES

        def build():
            return (
                [p.get_by_role(r, name=name, exact=True) for r in roles]
                + [p.get_by_role(r, name=name) for r in roles]
                + [p.get_by_test_id(name), p.get_by_text(name, exact=True), p.get_by_text(name)]
            )

        return self._resolve(build)

    def field(self, name: str) -> Locator:
        p = self.page
        return self._resolve(
            lambda: [
                p.get_by_label(name, exact=True),
                p.get_by_label(name),
                p.get_by_placeholder(name),
                p.get_by_role("textbox", name=name),
                p.get_by_role("combobox", name=name),
                p.get_by_test_id(name),
                p.locator(f"[name='{_css_attr(name)}' i], [id='{_css_attr(name)}' i]"),
            ]
        )

    def element(self, text: str) -> Locator:
        p = self.page
        return self._resolve(
            lambda: [p.get_by_text(text, exact=True), p.get_by_role("heading", name=text), p.get_by_text(text)]
        )

    def _checkable(self, name: str) -> Locator:
        p = self.page
        return self._resolve(
            lambda: [p.get_by_role("checkbox", name=name), p.get_by_role("radio", name=name), p.get_by_label(name)]
        )

    # ---- actions ------------------------------------------------------------
    def goto(self, url: str) -> None:
        self.page.goto(url)

    def click(self, name: str, role: str | None = None) -> None:
        self.clickable(name, role).click()

    def double_click(self, name: str, role: str | None = None) -> None:
        self.clickable(name, role).dblclick()

    def fill(self, field_name: str, value: str) -> None:
        self.field(field_name).fill(value)

    def select(self, field_name: str, option: str) -> None:
        self.field(field_name).select_option(label=option)

    def check(self, name: str) -> None:
        self._checkable(name).check()

    def uncheck(self, name: str) -> None:
        self._checkable(name).uncheck()

    def hover(self, name: str) -> None:
        self.clickable(name).hover()

    def press(self, key: str) -> None:
        self.page.keyboard.press(key)

    def scroll_to(self, text: str) -> None:
        self.element(text).scroll_into_view_if_needed()

    # ---- assertions ---------------------------------------------------------
    def expect_visible(self, text: str) -> None:
        expect(self.element(text)).to_be_visible(timeout=self.timeout_ms)

    def expect_hidden(self, text: str) -> None:
        expect(self.page.get_by_text(text)).to_have_count(0, timeout=self.timeout_ms)

    def expect_enabled(self, name: str) -> None:
        expect(self.clickable(name)).to_be_enabled(timeout=self.timeout_ms)

    def expect_disabled(self, name: str) -> None:
        expect(self.clickable(name)).to_be_disabled(timeout=self.timeout_ms)

    def expect_url_contains(self, fragment: str) -> None:
        expect(self.page).to_have_url(re.compile(re.escape(fragment), re.IGNORECASE), timeout=self.timeout_ms)


def _css_attr(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")
