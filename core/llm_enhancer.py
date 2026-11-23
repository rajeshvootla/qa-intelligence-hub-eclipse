"""Optional LLM pass that completes TODO steps in rule-generated Playwright tests."""
from __future__ import annotations

import os
import re

SYSTEM_PROMPT = """You are a senior QA automation engineer. You receive a pytest + Playwright (Python, sync API)
test module generated from manual test cases. Replace every '# TODO:' line with working code.
Prefer the `ui` helper (framework.ui_actions.UiActions) methods: goto, click(name, role=None),
double_click, fill(field, value), select(field, option), check, uncheck, hover, press(key), scroll_to,
expect_visible, expect_hidden, expect_enabled, expect_disabled, expect_url_contains.
Fall back to the raw `page` / `expect` Playwright API only when necessary.
Keep all existing imports, function names, docstrings, markers and step comments.
Return ONLY the full Python module, no markdown fences."""


def is_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def enhance(module_code: str, model: str | None = None) -> str:
    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.create(
        model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": module_code},
        ],
    )
    return strip_fences(response.choices[0].message.content or module_code)


def strip_fences(text: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip() + "\n"
