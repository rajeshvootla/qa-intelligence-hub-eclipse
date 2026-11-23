"""Parse manual test cases (free text or CSV) into structured objects."""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field


@dataclass
class TestStep:
    action: str
    expected: str = ""


@dataclass
class ManualTestCase:
    title: str
    steps: list[TestStep] = field(default_factory=list)
    preconditions: str = ""
    case_id: str = ""


_STEP_PREFIX = re.compile(r"^\s*(?:step\s*)?\d+[\.\):-]\s*", re.IGNORECASE)
_EXPECTED_PREFIX = re.compile(r"^\s*(?:expected(?:\s+result)?|=>|->)\s*[:\-]?\s*", re.IGNORECASE)
_TITLE_PREFIX = re.compile(r"^\s*(?:test\s*case|title|tc)\s*(?:[:\-]|\s+(?=[A-Z0-9]))\s*", re.IGNORECASE)
_PRECOND_PREFIX = re.compile(r"^\s*pre-?conditions?\s*[:\-]\s*", re.IGNORECASE)
_ID_PREFIX = re.compile(r"^\s*(?:id|case\s*id)\s*[:\-]\s*", re.IGNORECASE)


def parse_text(text: str) -> list[ManualTestCase]:
    """Parse free-text manual test cases.

    Cases are separated by blank lines followed by a ``Title:``/``Test Case:`` line,
    or by a line of ``---``. Numbered lines are steps; ``Expected:`` lines attach to
    the preceding step.
    """
    cases: list[ManualTestCase] = []
    current: ManualTestCase | None = None

    def ensure_case() -> ManualTestCase:
        nonlocal current
        if current is None:
            current = ManualTestCase(title=f"Test case {len(cases) + 1}")
            cases.append(current)
        return current

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if set(line) <= {"-", "="}:
            current = None
            continue
        if _TITLE_PREFIX.match(line):
            current = ManualTestCase(title=_TITLE_PREFIX.sub("", line).strip())
            cases.append(current)
        elif _ID_PREFIX.match(line):
            ensure_case().case_id = _ID_PREFIX.sub("", line).strip()
        elif _PRECOND_PREFIX.match(line):
            ensure_case().preconditions = _PRECOND_PREFIX.sub("", line).strip()
        elif _EXPECTED_PREFIX.match(line):
            case = ensure_case()
            expected = _EXPECTED_PREFIX.sub("", line).strip()
            if case.steps:
                prev = case.steps[-1]
                prev.expected = f"{prev.expected}; {expected}" if prev.expected else expected
            else:
                case.steps.append(TestStep(action="", expected=expected))
        elif _STEP_PREFIX.match(line):
            ensure_case().steps.append(TestStep(action=_STEP_PREFIX.sub("", line).strip()))
        else:
            case = ensure_case()
            if case.steps:
                case.steps[-1].action = f"{case.steps[-1].action} {line}".strip()
            else:
                case.steps.append(TestStep(action=line))
    return [c for c in cases if c.steps]


def _get(row: dict, *names: str) -> str:
    lowered = {(k or "").strip().lower(): (v or "") for k, v in row.items()}
    for name in names:
        if name in lowered and lowered[name].strip():
            return lowered[name].strip()
    return ""


def parse_csv(content: str) -> list[ManualTestCase]:
    """Parse CSV exports (TestRail style or simple one-row-per-step).

    Supported columns (case-insensitive): Title, ID, Preconditions,
    Steps / Steps (Step) / Step, Expected Result / Steps (Expected Result) / Expected.
    Rows with the same Title are merged into one case. A multi-line Steps cell
    with numbered lines is split into individual steps.
    """
    reader = csv.DictReader(io.StringIO(content))
    by_title: dict[str, ManualTestCase] = {}
    for row in reader:
        title = _get(row, "title", "test case", "name", "summary")
        if not title:
            continue
        case = by_title.get(title)
        if case is None:
            case = ManualTestCase(
                title=title,
                case_id=_get(row, "id", "case id"),
                preconditions=_get(row, "preconditions", "precondition"),
            )
            by_title[title] = case
        step_text = _get(row, "steps (step)", "steps", "step", "action")
        expected_text = _get(row, "steps (expected result)", "expected result", "expected")
        if not step_text and not expected_text:
            continue
        actions = [_STEP_PREFIX.sub("", s).strip() for s in step_text.splitlines() if s.strip()]
        expecteds = [_STEP_PREFIX.sub("", s).strip() for s in expected_text.splitlines() if s.strip()]
        if len(actions) > 1 and len(expecteds) == len(actions):
            case.steps.extend(TestStep(a, e) for a, e in zip(actions, expecteds))
        elif len(actions) > 1:
            case.steps.extend(TestStep(a) for a in actions)
            if expecteds:
                case.steps[-1].expected = "; ".join(expecteds)
        else:
            case.steps.append(TestStep(" ".join(actions), "; ".join(expecteds)))
    return [c for c in by_title.values() if c.steps]
