"""AI data center cycle score -- the monthly thesis log behind the Cycle view.

The framework is AI_DATA_CENTER_CYCLE_DASHBOARD.md, the desk owner's own text;
the per-month scores live in trading_records/cycle-score.csv. Unlike the trade
journal, this file is tracked in git and pushed -- it holds 0-2 judgment
scores and research notes, never a position, a fill, or an account detail, so
there is nothing in it that needs to stay off the public remote. This module
is the only code that reads or writes that file,
and it deliberately knows nothing about market data: every score here is a
judgment a person typed in. Three rules, stated in the READMEs and held by
tests/test_cycle.py:

* a skipped indicator is blank, never carried forward from last month, and a
  review with any blank has no total and no status;
* the file's header must match the committed template before the view writes
  to it -- a hand-edited layout is surfaced, never rewritten;
* a hand-edited row's stored total and status are checked against its scores
  and any disagreement is reported, not corrected.

The rubric shown beside each score (what GREEN / YELLOW / RED mean for that
indicator) is parsed out of the markdown rather than copied into code, so the
document stays the single source and a drift between the two is a test
failure, not a silent divergence.
"""

from __future__ import annotations

import csv
import os
import re
import tempfile
import threading
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DOC_PATH = HERE / "AI_DATA_CENTER_CYCLE_DASHBOARD.md"
TEMPLATE_PATH = REPO_ROOT / "trading_records" / "TEMPLATE-cycle-score.csv"
LOG_PATH = REPO_ROOT / "trading_records" / "cycle-score.csv"

# (csv column, label as it appears in the doc's score table). The order matters
# twice over: it is the CSV column order, and it is the order of the doc's
# numbered sections, which is how the rubric parser maps section N to the
# (N-1)th indicator here.
INDICATORS: list[tuple[str, str]] = [
    ("capex", "Hyperscaler Capex"),
    ("construction", "Construction Pipeline"),
    ("vacancy", "Pre-Leasing / Vacancy"),
    ("power", "Power / Grid Demand"),
    ("monetization", "AI Monetization"),
    ("optical", "Optical Demand"),
    ("electrical", "Electrical Equipment Demand"),
    ("agent_capability", "AI Agent Capability / Adaptation"),
]
KEYS = [k for k, _ in INDICATORS]
LABELS = dict(INDICATORS)
SCORE_MIN, SCORE_MAX = 0, 2
MAX_SCORE = SCORE_MAX * len(INDICATORS)   # 16
# Inclusive bands over the total, exactly as the doc states them.
BANDS: list[tuple[str, int, int]] = [("GREEN", 13, 16), ("YELLOW", 8, 12), ("RED", 0, 7)]
LEVELS = ("GREEN", "YELLOW", "RED")
# A score of 2 means the indicator's GREEN criterion is met, 1 YELLOW, 0 RED.
# The server never consults this itself; it is the declared contract that
# tests/test_cycle.py holds app.js's LEVEL_OF_SCORE to, since the client cannot
# import it.
LEVEL_OF_SCORE = {2: "GREEN", 1: "YELLOW", 0: "RED"}
COLUMNS = ["review_date", *KEYS, "total", "status", "core_question", "assumption_changed", "notes"]
TEXT_FIELDS = ("core_question", "assumption_changed", "notes")
MAX_TEXT = 4000
# `date.fromisoformat` also accepts 20260801 and 2026-W31-6. Both would be
# written verbatim, sort after every hyphenated date, and never match a later
# save of the same day -- so the log's dates are held to one spelling.
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The server is threaded and a save is a read-modify-write of the whole file.
# Two saves at once (a double-clicked button, two tabs) would each read the
# same rows and the second write would drop the first's row.
_WRITE_LOCK = threading.Lock()


class CycleError(ValueError):
    """A row the view refuses to read as intended or to write, with the reason."""


# --------------------------------------------------------------------------
# Scores, dates and bands
# --------------------------------------------------------------------------
def status_for(total: int | None) -> str | None:
    """GREEN / YELLOW / RED for a complete total; None for an incomplete review."""
    if total is None:
        return None
    for status, lo, hi in BANDS:
        if lo <= total <= hi:
            return status
    return None


def parse_score(raw) -> int | None:
    """A score cell: blank is None, '0'/'1'/'2' are ints, anything else is an error.

    Strict on purpose. '2.0', 'two', True and '3' are all rejected rather than
    coerced, because a coerced score is a judgment nobody made.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    if s not in {str(n) for n in range(SCORE_MIN, SCORE_MAX + 1)}:
        raise CycleError(f"score {raw!r} is not blank, 0, 1 or 2")
    return int(s)


def parse_review_date(raw) -> date:
    """A review date, YYYY-MM-DD only. Raises ValueError otherwise."""
    s = str(raw or "").strip()
    if not _DATE_RE.match(s):
        raise ValueError(f"{s!r} is not YYYY-MM-DD")
    return date.fromisoformat(s)


def _totals(scores: dict[str, int | None]) -> tuple[int, int | None, str | None]:
    """(how many scored, total or None, status or None). Blank anywhere -> no total."""
    scored = sum(v is not None for v in scores.values())
    total = sum(v for v in scores.values() if v is not None) if scored == len(KEYS) else None
    return scored, total, status_for(total)


# --------------------------------------------------------------------------
# Reading the log
# --------------------------------------------------------------------------
def _shape_row(raw: dict, line_no: int, warnings: list[str]) -> dict:
    rd = (raw.get("review_date") or "").strip()
    try:
        parse_review_date(rd)
    except ValueError:
        warnings.append(f"row {line_no}: review_date {rd!r} is not YYYY-MM-DD")

    scores: dict[str, int | None] = {}
    for k in KEYS:
        try:
            scores[k] = parse_score(raw.get(k))
        except CycleError:
            warnings.append(f"row {line_no} ({rd}): {LABELS[k]} score {raw.get(k)!r} is not "
                            f"0, 1 or 2; read as blank")
            scores[k] = None
    scored, total, status = _totals(scores)

    # The stored total/status are what a hand edit may have got wrong. Report the
    # disagreement; the derived figures are what the page shows.
    stored_total = (raw.get("total") or "").strip()
    stored_status = (raw.get("status") or "").strip().upper()
    if stored_total and stored_total != ("" if total is None else str(total)):
        warnings.append(f"row {line_no} ({rd}): stored total {stored_total} disagrees with the "
                        f"scores ({'incomplete' if total is None else total}); showing the scores")
    if stored_status and stored_status != (status or ""):
        warnings.append(f"row {line_no} ({rd}): stored status {stored_status} disagrees with the "
                        f"scores ({status or 'incomplete'}); showing the scores")

    notes = (raw.get("notes") or "").strip()
    if "example row" in notes.lower():
        warnings.append(f"row {line_no} ({rd}) looks like the template's example row; "
                        f"delete it by hand")

    return {
        "review_date": rd,
        "scores": scores,
        "scored": scored,
        "total": total,
        "status": status,
        "core_question": (raw.get("core_question") or "").strip(),
        "assumption_changed": (raw.get("assumption_changed") or "").strip(),
        "notes": notes,
    }


def read_log(path: Path | None = None) -> dict:
    """Every logged review, oldest first, plus what was wrong with the file.

    Tolerant on read: a missing column, a bad cell, a header the template does
    not have, a file that is not UTF-8 -- each becomes a warning the page shows,
    and where a row survives it is kept with the affected cell blank. Writing is
    the strict side (see `upsert_row`).
    """
    path = path or LOG_PATH
    out: dict = {"exists": path.exists(), "rows": [], "warnings": []}
    if not out["exists"]:
        return out
    warnings: list[str] = out["warnings"]
    try:
        # utf-8-sig: a spreadsheet re-save can prepend a BOM, which would
        # otherwise turn the first header cell into '﻿review_date'.
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
            if header is None:
                return out                  # empty file: nothing to read, nothing wrong
            missing = [c for c in COLUMNS if c not in header]
            extra = [c for c in header if c not in COLUMNS]
            if missing:
                warnings.append(f"{path.name} header is missing {', '.join(missing)}; "
                                f"those read as blank")
            if extra:
                # A spreadsheet's trailing comma is an extra column named '',
                # which would print as "()" and name nothing.
                names = ", ".join(repr(c) if c.strip() else "an empty column" for c in extra)
                warnings.append(f"{path.name} has columns the template does not ({names}); "
                                f"ignored here, and the view will not write to this file until "
                                f"the header matches the template")
            for raw in reader:
                if not any((v or "").strip() for v in raw.values() if isinstance(v, str)):
                    continue   # a blank line, not a review
                # line_num is the physical line, the number a spreadsheet shows
                # and the number the write path reports -- not a count of rows,
                # which would drift past every blank line.
                out["rows"].append(_shape_row(raw, reader.line_num, warnings))
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        warnings.append(f"could not read {path.name}: {e}. It must be a UTF-8 CSV; "
                        f"a spreadsheet's default 'CSV' export often is not")
    out["rows"].sort(key=lambda r: r["review_date"])
    return out


# --------------------------------------------------------------------------
# Writing the log
# --------------------------------------------------------------------------
def _read_raw_rows(path: Path) -> list[dict]:
    """The file's rows verbatim, for rewriting. Refuses a layout that is not the template's."""
    if not path.exists():
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                return []                   # zero bytes: nothing to preserve
            if header != COLUMNS:
                raise CycleError(
                    f"{path.name} header differs from {TEMPLATE_PATH.name}; the view will not "
                    f"rewrite a hand-edited layout. Expected columns: {', '.join(COLUMNS)}")
            rows = []
            for cells in reader:
                if not any(c.strip() for c in cells):
                    continue
                if len(cells) != len(COLUMNS):
                    # zip() would silently drop the extra cells or blank the
                    # missing ones; a malformed row is the owner's to fix.
                    raise CycleError(f"{path.name} row {reader.line_num} has {len(cells)} cells, "
                                     f"expected {len(COLUMNS)}; fix it by hand before saving "
                                     f"from the page")
                rows.append(dict(zip(COLUMNS, cells)))
            return rows
    except (UnicodeDecodeError, csv.Error) as e:
        raise CycleError(f"{path.name} is not a UTF-8 CSV ({e}); re-save it as UTF-8 before "
                         f"saving from the page") from None


def _write_rows(rows: list[dict], path: Path) -> None:
    """Write the whole log atomically: a private temp file in the same directory,
    then rename over the log, so a crash mid-write cannot leave it half-written.

    The path is resolved first. A log kept in a synced folder and symlinked into
    trading_records/ must be written through the link: renaming over the link
    itself would replace it with a plain file and leave the real log untouched.
    """
    path = Path(os.path.realpath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def upsert_row(data: dict, path: Path | None = None, today: date | None = None) -> str:
    """Validate one review and write it, replacing any row with the same date.

    Returns the review_date written. Raises CycleError for anything that should
    go back to the form as a message rather than into the file.
    """
    path = path or LOG_PATH
    today = today or date.today()

    try:
        d = parse_review_date(data.get("review_date"))
    except ValueError:
        raise CycleError("review_date must be a date, YYYY-MM-DD") from None
    if d > today:
        raise CycleError(f"review_date {d} is in the future; it is the date the scores were decided")
    rd = d.isoformat()

    scores_in = data.get("scores")
    if scores_in is None:
        scores_in = {}
    if not isinstance(scores_in, dict):
        raise CycleError("scores must be an object keyed by indicator")
    unknown = sorted(set(scores_in) - set(KEYS))
    if unknown:
        raise CycleError(f"unknown indicator(s): {', '.join(unknown)}")
    scores: dict[str, int | None] = {}
    for k in KEYS:
        try:
            scores[k] = parse_score(scores_in.get(k))
        except CycleError:
            raise CycleError(f"{LABELS[k]}: score must be blank, 0, 1 or 2") from None

    text: dict[str, str] = {}
    for field in TEXT_FIELDS:
        v = data.get(field)
        if v is not None and not isinstance(v, str):
            raise CycleError(f"{field} must be text")
        v = "" if v is None else v.replace("\r\n", "\n").strip()
        if len(v) > MAX_TEXT:
            raise CycleError(f"{field} is longer than {MAX_TEXT} characters")
        text[field] = v

    _, total, status = _totals(scores)
    new = {
        "review_date": rd,
        **{k: ("" if scores[k] is None else str(scores[k])) for k in KEYS},
        "total": "" if total is None else str(total),
        "status": status or "",
        **text,
    }
    with _WRITE_LOCK:
        existing = _read_raw_rows(path)
        rows = [r for r in existing if (r.get("review_date") or "").strip() != rd] + [new]
        rows.sort(key=lambda r: r["review_date"])
        _write_rows(rows, path)
    return rd


# --------------------------------------------------------------------------
# The framework document
# --------------------------------------------------------------------------
_SECTION_RE = re.compile(r"^## (\d+)\. (.+?)\s*$")
_LEVEL_RE = re.compile(r"^### (GREEN|YELLOW|RED)\b")
_BULLET_RE = re.compile(r"^\s*[-*] (.+?)\s*$")


def read_doc(doc_path: Path | None = None) -> str:
    """The framework document's text. Raises CycleError if it cannot be read."""
    path = doc_path or DOC_PATH
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        raise CycleError(f"cannot read {path.name}: {e}") from None


def rubric(doc_path: Path | None = None, *, text: str | None = None) -> dict[str, dict]:
    """Per indicator: the doc's section title, its GREEN/YELLOW/RED criteria, and
    the bullet list of what to track.

    Each criterion is the first paragraph under its `### LEVEL` heading. A
    section's later commentary (the vacancy remark, the power "key question") is
    left in the document, which the page names. Raises CycleError if any of the
    seven sections or any of the three levels is missing, so a restructured
    document fails a test rather than quietly blanking a rubric.
    """
    path = doc_path or DOC_PATH
    if text is None:
        text = read_doc(path)

    sections: dict[int, dict] = {}
    cur: dict | None = None
    level: str | None = None
    for line in text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            cur = sections[int(m.group(1))] = {"title": m.group(2).strip(), "levels": {}, "track": []}
            level = None
            continue
        if line.startswith("## "):
            cur, level = None, None       # an unnumbered section: out of scope
            continue
        if cur is None:
            continue
        lm = _LEVEL_RE.match(line)
        if lm:
            level = lm.group(1)
            cur["levels"].setdefault(level, [])
            continue
        if line.startswith("### "):
            level = None                  # e.g. "### Monitor": bullets, not a criterion
            continue
        bullet = _BULLET_RE.match(line)
        if level is not None:
            if line.strip():
                cur["levels"][level].append(bullet.group(1) if bullet else line.strip())
            elif cur["levels"][level]:
                level = None              # first paragraph ended; the rest is commentary
        elif bullet:
            cur["track"].append(bullet.group(1))

    out: dict[str, dict] = {}
    for i, (key, label) in enumerate(INDICATORS, start=1):
        sec = sections.get(i)
        if not sec:
            raise CycleError(f"{path.name}: no '## {i}.' section for {label}")
        levels = {lv: " ".join(sec["levels"].get(lv, [])).strip() for lv in LEVELS}
        missing = [lv for lv in LEVELS if not levels[lv]]
        if missing:
            raise CycleError(f"{path.name}: section {i} ({sec['title']}) has no text under "
                             f"{', '.join(missing)}")
        out[key] = {"title": sec["title"], "rubric": levels, "track": sec["track"]}
    return out


def core_question(doc_path: Path | None = None, *, text: str | None = None) -> str | None:
    """The bold question the doc says every review must end on, or None."""
    if text is None:
        try:
            text = read_doc(doc_path)
        except CycleError:
            return None
    m = re.search(r"^## Core Question\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return None
    q = re.search(r"\*\*(.+?)\*\*", m.group(1), re.S)
    return " ".join(q.group(1).split()) if q else None


# --------------------------------------------------------------------------
# The payload the page renders
# --------------------------------------------------------------------------
def build_cycle(path: Path | None = None, doc_path: Path | None = None) -> dict:
    path = path or LOG_PATH
    log = read_log(path)
    rows = log["rows"]
    rub: dict = {}
    question = None
    try:
        text = read_doc(doc_path)     # one read; both parsers work from it
        rub = rubric(doc_path, text=text)
        question = core_question(doc_path, text=text)
        rubric_error = None
    except CycleError as e:
        rubric_error = str(e)
    try:
        log_rel = str(path.relative_to(REPO_ROOT))
    except ValueError:
        log_rel = str(path)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "log": path.name,
        "log_path": log_rel,
        "exists": log["exists"],
        "doc": f"trading_desk/{DOC_PATH.name}",
        "max_score": MAX_SCORE,
        "score_max": SCORE_MAX,
        "bands": [{"status": s, "lo": lo, "hi": hi} for s, lo, hi in BANDS],
        "indicators": [
            {"key": k, "label": LABELS[k],
             **rub.get(k, {"title": None, "rubric": {}, "track": []})}
            for k in KEYS
        ],
        "rubric_error": rubric_error,
        "core_question": question,
        "rows": rows,
        "latest": rows[-1] if rows else None,
        "previous": rows[-2] if len(rows) > 1 else None,
        "warnings": log["warnings"],
    }
