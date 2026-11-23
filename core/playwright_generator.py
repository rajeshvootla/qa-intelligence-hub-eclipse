"""Convert structured manual test cases into Playwright (pytest) test code.

The rule-based converter maps common manual-test phrasing ("Navigate to",
"Click", "Enter ... in ...", "Verify ... is displayed", ...) onto the helper API
in ``automation/framework/ui_actions.py``. Steps it cannot map are emitted as
``TODO`` comments and reported back so they can be finished by hand or by the
optional LLM enhancer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.manual_parser import ManualTestCase

_QUOTED = re.compile(r"[\"'“”‘’]([^\"'“”‘’]+)[\"'“”‘’]")
_URL = re.compile(r"(https?://\S+|(?<!\w)/[\w\-./?=&%#]*)")
_ELEMENT_WORDS = r"(?:button|link|tab|menu|icon|checkbox|field|textbox|input|option|dropdown|item)"


@dataclass
class GeneratedTest:
    case_title: str
    function_name: str
    code: str
    unmapped_steps: list[str] = field(default_factory=list)


def _quoted(text: str) -> list[str]:
    return [q.strip() for q in _QUOTED.findall(text)]


def _lit(value: str) -> str:
    return repr(value)


def slugify(text: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    if not slug:
        slug = "case"
    if slug[0].isdigit():
        slug = f"tc_{slug}"
    return slug[:80]


def _role_for(text: str) -> str | None:
    lowered = text.lower()
    for word, role in (
        ("button", "button"),
        ("link", "link"),
        ("tab", "tab"),
        ("checkbox", "checkbox"),
        ("menu item", "menuitem"),
    ):
        if re.search(rf"\b{word}\b", lowered):
            return role
    return None


def _unquoted_target(text: str, verb_pattern: str) -> str:
    """Return the object of a verb when no quotes are used, e.g. 'Click Login button' -> 'Login'."""
    m = re.search(rf"{verb_pattern}\s+(?:on\s+|the\s+)*(.+)$", text, re.IGNORECASE)
    if not m:
        return ""
    target = re.sub(rf"\s+{_ELEMENT_WORDS}\b.*$", "", m.group(1), flags=re.IGNORECASE)
    return target.strip(" .")


def convert_action(step: str) -> list[str] | None:
    """Convert a single action sentence into Python statements, or ``None`` if unknown."""
    s = step.strip().rstrip(".")
    low = s.lower()
    quoted = _quoted(s)

    if re.match(r"^(navigate|go|open|launch|visit|browse)\b", low):
        url = _URL.search(s)
        if url:
            return [f"ui.goto({_lit(url.group(1).rstrip('.,'))})"]
        if quoted and (quoted[0].startswith("/") or quoted[0].startswith("http")):
            return [f"ui.goto({_lit(quoted[0])})"]
        if re.search(r"\b(application|app|site|home ?page|url|portal|login page)\b", low):
            return ["ui.goto('/')"]
        return None

    m = re.match(r"^(enter|type|fill|input|provide|set)\b(.*)$", s, re.IGNORECASE)
    if m:
        if len(quoted) >= 2:
            # The quoted text after "in"/"into"/"field" is the target; the other is the value.
            target_m = re.search(r"\b(?:in|into|field)\s+(?:the\s+)?[\"'“‘]([^\"'”’]+)", s, re.IGNORECASE)
            if target_m and target_m.group(1).strip() == quoted[0]:
                target, value = quoted[0], quoted[1]
            else:
                value, target = quoted[0], quoted[1]
            return [f"ui.fill({_lit(target)}, {_lit(value)})"]
        if len(quoted) == 1:
            # "Enter 'bob' in the username field" / "Enter username 'bob'"
            after = re.search(r"\b(?:in|into)\s+(?:the\s+)?(.+?)(?:\s+" + _ELEMENT_WORDS + r")?$", s, re.IGNORECASE)
            if after and quoted[0] not in after.group(1):
                return [f"ui.fill({_lit(after.group(1).strip(' .'))}, {_lit(quoted[0])})"]
            before = re.match(rf"^\w+\s+(?:the\s+)?(?:valid\s+|invalid\s+)?(.+?)\s+(?:as\s+)?[\"'“‘]", s, re.IGNORECASE)
            if before:
                return [f"ui.fill({_lit(before.group(1).strip())}, {_lit(quoted[0])})"]
        return None

    if re.match(r"^(select|choose|pick)\b", low) and len(quoted) >= 2:
        return [f"ui.select({_lit(quoted[1])}, {_lit(quoted[0])})"]

    m = re.match(r"^(uncheck|untick|deselect)\b", low)
    if m:
        target = quoted[0] if quoted else _unquoted_target(s, r"(?:uncheck|untick|deselect)")
        return [f"ui.uncheck({_lit(target)})"] if target else None

    if re.match(r"^(check|tick)\b", low) and not re.match(r"^check\s+(that|if|whether)\b", low):
        target = quoted[0] if quoted else _unquoted_target(s, r"(?:check|tick)")
        return [f"ui.check({_lit(target)})"] if target else None

    if re.match(r"^(hover|mouse over)\b", low):
        target = quoted[0] if quoted else _unquoted_target(s, r"(?:hover(?:\s+over)?|mouse over)")
        return [f"ui.hover({_lit(target)})"] if target else None

    if re.match(r"^(click|tap|press|submit|double[- ]click)\b", low):
        key = re.match(r"^press\s+(?:the\s+)?[\"'“‘]?(enter|tab|escape|esc|backspace|space|arrow\w+)[\"'”’]?(?:\s+key)?$", low)
        if key:
            name = {"esc": "Escape", "space": "Space"}.get(key.group(1), key.group(1).capitalize())
            return [f"ui.press({_lit(name)})"]
        target = quoted[0] if quoted else _unquoted_target(s, r"(?:double[- ]click|click|tap|press|submit)")
        if not target:
            return None
        role = _role_for(s)
        fn = "double_click" if "double" in low else "click"
        return [f"ui.{fn}({_lit(target)}, role={_lit(role)})" if role else f"ui.{fn}({_lit(target)})"]

    m = re.match(r"^wait\s+(?:for\s+)?(\d+(?:\.\d+)?)\s*(s|sec|secs|seconds?|ms|milliseconds?)\b", low)
    if m:
        ms = float(m.group(1)) * (1 if m.group(2).startswith("m") else 1000)
        return [f"page.wait_for_timeout({int(ms)})"]

    if re.match(r"^(refresh|reload)\b", low):
        return ["page.reload()"]

    if re.match(r"^(scroll)\b", low):
        return [f"ui.scroll_to({_lit(quoted[0])})"] if quoted else ["page.mouse.wheel(0, 2000)"]

    if re.match(r"^(verify|validate|assert|check that|check if|ensure|confirm|observe)\b", low):
        return convert_expected(s)

    return None


def convert_expected(text: str) -> list[str] | None:
    """Convert an expected-result sentence into Playwright assertions."""
    s = text.strip().rstrip(".")
    low = s.lower()
    quoted = _quoted(s)

    if re.search(r"\burl\b", low):
        url = quoted[0] if quoted else (_URL.search(s).group(1) if _URL.search(s) else "")
        if url:
            return [f"ui.expect_url_contains({_lit(url)})"]
        return None

    if re.search(r"\b(page\s+)?title\b", low) and quoted:
        return [f"expect(page).to_have_title(re.compile(re.escape({_lit(quoted[0])})))"]

    negative = re.search(r"\b(not\s+(be\s+)?(displayed|visible|shown|present)|hidden|disappear|is not|should not)\b", low)

    if quoted:
        if re.search(r"\b(disabled)\b", low):
            return [f"ui.expect_disabled({_lit(quoted[0])})"]
        if re.search(r"\b(enabled)\b", low):
            return [f"ui.expect_enabled({_lit(quoted[0])})"]
        fn = "expect_hidden" if negative else "expect_visible"
        return [f"ui.{fn}({_lit(q)})" for q in quoted]

    # Unquoted, e.g. "User is redirected to dashboard" / "Dashboard page is displayed"
    m = re.search(r"\b(?:redirected|navigated|taken|lands?)\s+(?:to|on)\s+(?:the\s+)?(\w[\w\s-]*?)(?:\s+page)?$", low)
    if m:
        return [f"ui.expect_url_contains({_lit(m.group(1).strip().replace(' ', '-'))})"]
    m = re.match(
        r"^(?:verify|validate|ensure|confirm|check that)?\s*(?:that\s+)?(?:the\s+)?(.+?)\s+"
        r"(?:is|are|should be|gets?)\s+(?:displayed|visible|shown|present|appears?)",
        s,
        re.IGNORECASE,
    )
    if m:
        target = re.sub(r"\s+(page|message|text|label|section|button|link)$", "", m.group(1).strip(), flags=re.IGNORECASE)
        fn = "expect_hidden" if negative else "expect_visible"
        return [f"ui.{fn}({_lit(target)})"]
    return None


def generate_test(case: ManualTestCase) -> GeneratedTest:
    name = f"test_{slugify(case.case_id + '_' + case.title if case.case_id else case.title)}"
    body: list[str] = []
    unmapped: list[str] = []
    for idx, step in enumerate(case.steps, start=1):
        if step.action:
            body.append(f"# Step {idx}: {step.action}")
            stmts = convert_action(step.action)
            if stmts is None:
                unmapped.append(step.action)
                body.append(f"# TODO: automate step -> {step.action}")
            else:
                body.extend(stmts)
        if step.expected:
            body.append(f"# Expected: {step.expected}")
            for part in (p.strip() for p in step.expected.split(";")):
                if not part:
                    continue
                stmts = convert_expected(part)
                if stmts is None:
                    unmapped.append(f"Expected: {part}")
                    body.append(f"# TODO: add assertion -> {part}")
                else:
                    body.extend(stmts)
    if not any(not line.startswith("#") for line in body):
        body.append("pytest.skip('No automatable steps were generated for this case')")

    doc_lines = [case.title]
    if case.case_id:
        doc_lines.append(f"TestRail case: {case.case_id}")
    if case.preconditions:
        doc_lines.append(f"Preconditions: {case.preconditions}")
    docstring = "\n    ".join(line.replace('"""', "'''") for line in doc_lines)

    marker = f"@pytest.mark.testrail({_lit(case.case_id)})\n" if case.case_id else ""
    code = (
        f"{marker}def {name}(page: Page, ui: UiActions):\n"
        f'    """{docstring}"""\n'
        + "".join(f"    {line}\n" for line in body)
    )
    return GeneratedTest(case.title, name, code, unmapped)


FILE_HEADER = '''"""Auto-generated by QA Intelligence Hub - Test Case Generator.

Review the TODO comments before committing.
"""
import re

import pytest
from playwright.sync_api import Page, expect

from framework.ui_actions import UiActions


'''


def build_module(tests: list[GeneratedTest]) -> str:
    seen: dict[str, int] = {}
    chunks = []
    for t in tests:
        code = t.code
        count = seen.get(t.function_name, 0)
        if count:
            code = code.replace(f"def {t.function_name}(", f"def {t.function_name}_{count + 1}(", 1)
        seen[t.function_name] = count + 1
        chunks.append(code)
    return FILE_HEADER + "\n\n".join(chunks)
