# QA Intelligence Hub – Eclipse

A Streamlit app that turns **manual test cases** into **automated Playwright (pytest) tests**.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium
streamlit run app.py          # open http://localhost:8501/Test_Case_Generator
```

## Test Case Generator

1. Paste manual test cases, or upload a TestRail CSV export (`Title`, `ID`, `Preconditions`,
   `Steps (Step)`, `Steps (Expected Result)`, or `Steps` / `Expected Result` columns).
2. Click **Generate**. Steps are mapped to Playwright code. Any step that can't be mapped gets a `# TODO` comment and is listed in the UI.
   If `OPENAI_API_KEY` is set (optional: `OPENAI_MODEL`), you can let AI finish the TODO steps.
3. Edit the code if needed, then **Download**, **Save to framework** (`automation/tests/generated/`) or **Save & run**.

Text input format:

```
Title: Successful login
ID: C1001
1. Navigate to /login
2. Enter "standard_user" in "Username"
3. Click "Login" button
Expected: "Products" is displayed
```

Put quotes around field names, labels and values to get the best results. The app's
**Supported manual step phrasing** panel lists every phrase it recognizes.

## Automation framework (`automation/`)

- `framework/ui_actions.py`: `UiActions` helpers (`click`, `fill`, `select`, `expect_visible`, …).
  They find elements by their plain-language name in this order: role → label → placeholder → test id → text.
- `conftest.py`: provides the `ui` fixture and the `testrail(case_id)` marker.
- On failure, tests save screenshots and traces to `automation/test-results/`.

```bash
cd automation
pytest --base-url https://your-app.example.com --browser chromium [--headed]
```

## Unit tests

```bash
pytest            # from the repo root
```
