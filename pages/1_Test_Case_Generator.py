"""Test Case Generator: convert manual test cases into Playwright automated tests."""
from __future__ import annotations

import ast
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core import llm_enhancer  # noqa: E402
from core.manual_parser import parse_csv, parse_text  # noqa: E402
from core.playwright_generator import build_module, generate_test, slugify  # noqa: E402

AUTOMATION_DIR = ROOT / "automation"
GENERATED_DIR = AUTOMATION_DIR / "tests" / "generated"
SAMPLE = (ROOT / "samples" / "manual_test_cases.txt").read_text(encoding="utf-8")

st.set_page_config(page_title="Test Case Generator", page_icon="🧪", layout="wide")
st.title("🧪 Test Case Generator")
st.caption("Convert manual test cases into automated Playwright (pytest) tests.")

with st.sidebar:
    st.header("Settings")
    base_url = st.text_input("Application base URL", value=os.getenv("BASE_URL", "https://example.com"))
    module_name = st.text_input("Test module name", value="eclipse_automation_pack")
    use_llm = st.checkbox(
        "Complete TODO steps with AI (OpenAI)",
        value=False,
        disabled=not llm_enhancer.is_available(),
        help="Set OPENAI_API_KEY to enable.",
    )
    browser = st.selectbox("Browser for test run", ["chromium", "firefox", "webkit"])
    headed = st.checkbox("Run headed", value=False)

st.subheader("1. Provide manual test cases")
source = st.radio("Input", ["Paste text", "Upload CSV / TXT (e.g. TestRail export)"], horizontal=True)
cases = []
if source == "Paste text":
    text = st.text_area("Manual test cases", value=SAMPLE, height=300)
    cases = parse_text(text)
else:
    upload = st.file_uploader("File", type=["csv", "txt"])
    if upload:
        content = upload.getvalue().decode("utf-8-sig")
        cases = parse_csv(content) if upload.name.lower().endswith(".csv") else parse_text(content)

st.write(f"Parsed **{len(cases)}** test case(s).")
for case in cases:
    with st.expander(f"{case.case_id + ' - ' if case.case_id else ''}{case.title} ({len(case.steps)} steps)"):
        st.table([{"#": i, "Action": s.action, "Expected": s.expected} for i, s in enumerate(case.steps, 1)])

st.subheader("2. Generate Playwright tests")
if st.button("⚙️ Generate", type="primary", disabled=not cases):
    tests = [generate_test(c) for c in cases]
    code = build_module(tests)
    if use_llm and any(t.unmapped_steps for t in tests):
        with st.spinner("Completing TODO steps with AI..."):
            try:
                code = llm_enhancer.enhance(code)
            except Exception as exc:  # keep rule-based output on failure
                st.warning(f"AI enhancement failed, using rule-based output: {exc}")
    st.session_state["generated_code"] = code
    st.session_state["unmapped"] = {t.case_title: t.unmapped_steps for t in tests if t.unmapped_steps}

code = st.session_state.get("generated_code")
if code:
    unmapped = st.session_state.get("unmapped", {})
    if unmapped:
        st.warning("Some steps could not be converted automatically and are marked `# TODO` in the code:")
        for title, steps in unmapped.items():
            st.markdown(f"**{title}**\n" + "\n".join(f"- {s}" for s in steps))
    else:
        st.success("All steps were converted.")

    edited = st.text_area("Generated code (editable)", value=code, height=450, key="code_editor")
    try:
        ast.parse(edited)
        valid = True
    except SyntaxError as exc:
        valid = False
        st.error(f"Syntax error at line {exc.lineno}: {exc.msg}")

    filename = f"test_{slugify(module_name)}.py"
    col1, col2, col3 = st.columns(3)
    col1.download_button("⬇️ Download", edited, file_name=filename, mime="text/x-python")

    if col2.button("💾 Save to framework", disabled=not valid):
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        (GENERATED_DIR / filename).write_text(edited, encoding="utf-8")
        st.success(f"Saved to `{(GENERATED_DIR / filename).relative_to(ROOT)}`")

    if col3.button("▶️ Save & run", disabled=not valid):
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        target = GENERATED_DIR / filename
        target.write_text(edited, encoding="utf-8")
        cmd = [sys.executable, "-m", "pytest", str(target.relative_to(AUTOMATION_DIR)),
               "--base-url", base_url, "--browser", browser, "-v", "--junitxml", "test-results/junit.xml"]
        if headed:
            cmd.append("--headed")
        with st.spinner(f"Running: {' '.join(cmd[2:])}"):
            result = subprocess.run(cmd, cwd=AUTOMATION_DIR, capture_output=True, text=True, timeout=1800)
        (st.success if result.returncode == 0 else st.error)(
            f"pytest exited with code {result.returncode} at {dt.datetime.now():%H:%M:%S}"
        )
        st.code(result.stdout[-20000:] + result.stderr[-5000:], language="text")

with st.expander("Supported manual step phrasing"):
    st.markdown(
        """
| Manual step | Generated code |
|---|---|
| Navigate to `/login` / Open the application | `ui.goto('/login')` |
| Enter "bob" in "Username" / Enter username "bob" | `ui.fill('Username', 'bob')` |
| Click "Login" button / Click on Submit | `ui.click('Login', role='button')` |
| Select "India" from "Country" | `ui.select('Country', 'India')` |
| Check / Uncheck "Remember me" | `ui.check('Remember me')` |
| Hover over "Profile" · Press Enter · Wait 2 seconds | `ui.hover` · `ui.press('Enter')` · `page.wait_for_timeout(2000)` |
| Expected: "Welcome" is displayed / not displayed | `ui.expect_visible('Welcome')` / `ui.expect_hidden(...)` |
| Expected: URL contains "/dashboard" · User is redirected to dashboard | `ui.expect_url_contains('/dashboard')` |
| Expected: page title is "Home" · "Save" is disabled | `expect(page).to_have_title(...)` · `ui.expect_disabled('Save')` |

Use quotes around field names, button labels and values for best results.
"""
    )
