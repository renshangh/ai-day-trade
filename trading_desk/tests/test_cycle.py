"""Tests for the AI data center cycle score: the log, the doc parser, the view.

Run: python3 trading_desk/tests/test_cycle.py

Offline throughout. The log is always a temp file; the document is the real
one, deliberately -- the code and the framework text must agree, and this is
where that agreement is held.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import tempfile
import threading
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cycle  # noqa: E402
import server as srv  # noqa: E402

DESK = Path(__file__).resolve().parent.parent
REPO = DESK.parent
DOC = (DESK / "AI_DATA_CENTER_CYCLE_DASHBOARD.md").read_text()


# ----------------------------------------------------------------- fixtures
def _tmp_log(rows: list[dict] | None = None, header: list[str] | None = None,
             raw_lines: list[str] | None = None, bom: bool = False) -> Path:
    """A throwaway log. `rows` are dicts over the template columns; `raw_lines`
    bypasses the writer for malformed-file cases."""
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="",
                                     encoding="utf-8-sig" if bom else "utf-8")
    with fh:
        if raw_lines is not None:
            fh.write("\n".join(raw_lines) + "\n")
        else:
            w = csv.DictWriter(fh, fieldnames=header or cycle.COLUMNS)
            w.writeheader()
            for r in rows or []:
                w.writerow(r)
    return Path(fh.name)


def _csv_row(review_date: str, scores: list, total="", status="", **text) -> dict:
    """One raw CSV row over the template columns."""
    r = {"review_date": review_date, "total": total, "status": status,
         "core_question": text.get("core_question", ""),
         "assumption_changed": text.get("assumption_changed", ""),
         "notes": text.get("notes", "")}
    for k, v in zip(cycle.KEYS, scores):
        r[k] = "" if v is None else str(v)
    return r


def _review(review_date: str = "2026-08-31", scores: list | None = None, **over) -> dict:
    """A POST-shaped review, complete unless told otherwise."""
    scores = [2, 2, 2, 1, 1, 2, 2, 2] if scores is None else scores
    body = {"review_date": review_date, "scores": dict(zip(cycle.KEYS, scores)),
            "core_question": "yes", "assumption_changed": "unchanged", "notes": "test"}
    body.update(over)
    return body


def _read_all(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------- the three sources agree
def test_template_header_matches_the_columns():
    """The committed template is what a hand-started log copies; the writer must
    produce the identical layout or the two files stop being interchangeable."""
    with (REPO / "trading_records" / "TEMPLATE-cycle-score.csv").open(newline="") as f:
        header = next(csv.reader(f))
    assert header == cycle.COLUMNS


def test_doc_score_table_lists_the_indicators_in_order():
    labels = re.findall(r"^\| (.+?) \| 0–2 \|$", DOC, re.M)
    assert labels == [label for _, label in cycle.INDICATORS], labels


def test_doc_bands_match_the_code():
    bands = [(s, int(lo), int(hi)) for lo, hi, s in
             re.findall(r"^### (\d+)–(\d+): (GREEN|YELLOW|RED)$", DOC, re.M)]
    assert bands == cycle.BANDS, bands
    assert re.search(r"^Maximum score: \*\*%d\*\*$" % cycle.MAX_SCORE, DOC, re.M)


def test_rubric_parses_every_indicator_and_level_from_the_doc():
    rub = cycle.rubric()
    assert list(rub) == cycle.KEYS
    for key, entry in rub.items():
        assert entry["title"], key
        for lv in cycle.LEVELS:
            assert entry["rubric"][lv], f"{key} has no {lv} text"
        assert entry["track"], f"{key} has no tracking bullets"
    # Spot-checks that the mapping section N -> indicator N-1 is right.
    assert rub["capex"]["rubric"]["GREEN"] == "Capex guidance is maintained or raised."
    assert rub["electrical"]["rubric"]["YELLOW"] == "Backlog growth slows but remains elevated."
    assert "AXTI" in rub["optical"]["track"]
    assert rub["agent_capability"]["rubric"]["RED"].startswith("Enterprise agent deployments")


def test_rubric_is_the_first_paragraph_only():
    """The vacancy section's closing remark is commentary, not the RED criterion."""
    red = cycle.rubric()["vacancy"]["rubric"]["RED"]
    assert red.startswith("Vacancy rises significantly")
    assert "clearest early signs" not in red


def test_rubric_failure_names_what_is_missing():
    fd, name = tempfile.mkstemp(suffix=".md")
    os.close(fd)
    broken = Path(name)
    broken.write_text("# x\n\n## 1. Only one\n\n### GREEN\nfine\n\n### RED\nbad\n")
    try:
        cycle.rubric(broken)
    except cycle.CycleError as e:
        assert "YELLOW" in str(e), e
    else:
        raise AssertionError("a doc missing a level must not parse")
    finally:
        broken.unlink(missing_ok=True)


def test_core_question_is_read_from_the_doc():
    q = cycle.core_question()
    assert q and "AXTI, LITE, COHR, FN, and POWL" in q
    assert "\n" not in q


def test_client_declares_the_view_and_levels():
    """app.js cannot import cycle.py, so the pieces that must agree are asserted."""
    js = (DESK / "app.js").read_text()
    html = (DESK / "index.html").read_text()
    assert "key: 'cycle'" in js and "card: 'cycle-card'" in js
    assert 'id="cycle-card"' in html
    m = re.search(r"const LEVEL_OF_SCORE = \{ ([^}]+) \};", js)
    assert m, "app.js must declare LEVEL_OF_SCORE"
    pairs = dict(re.findall(r"(\d): '(GREEN|YELLOW|RED)'", m.group(1)))
    assert {int(k): v for k, v in pairs.items()} == cycle.LEVEL_OF_SCORE


# -------------------------------------------------------------------- bands
def test_status_bands_are_inclusive_at_their_edges():
    assert cycle.status_for(0) == "RED" and cycle.status_for(7) == "RED"
    assert cycle.status_for(8) == "YELLOW" and cycle.status_for(12) == "YELLOW"
    assert cycle.status_for(13) == "GREEN" and cycle.status_for(16) == "GREEN"
    assert cycle.status_for(None) is None
    # Every integer total has exactly one band.
    assert all(cycle.status_for(t) for t in range(cycle.MAX_SCORE + 1))


def test_parse_score_is_strict():
    assert cycle.parse_score("") is None and cycle.parse_score(None) is None
    assert cycle.parse_score(" 2 ") == 2 and cycle.parse_score(1) == 1
    for bad in ("3", "-1", "2.0", "two", True, 1.5):
        try:
            cycle.parse_score(bad)
        except cycle.CycleError:
            pass
        else:
            raise AssertionError(f"{bad!r} must not parse as a score")


# ------------------------------------------------------------------ reading
def test_missing_log_is_absence_not_an_empty_history():
    out = cycle.read_log(Path("/nonexistent/cycle-score.csv"))
    assert out["exists"] is False and out["rows"] == [] and out["warnings"] == []


def test_blank_score_leaves_total_and_status_blank():
    p = _tmp_log([_csv_row("2026-08-31", [None, 2, 2, 2, 2, 2, 2, 2])])
    try:
        row = cycle.read_log(p)["rows"][0]
    finally:
        p.unlink()
    assert row["scores"]["capex"] is None
    assert row["scored"] == 7
    assert row["total"] is None and row["status"] is None


def test_stored_total_that_disagrees_is_reported_not_corrected():
    p = _tmp_log([_csv_row("2026-08-31", [2, 2, 2, 1, 1, 2, 2, 2], total="15", status="GREEN")])
    try:
        out = cycle.read_log(p)
    finally:
        p.unlink()
    row = out["rows"][0]
    assert row["total"] == 14 and row["status"] == "GREEN"     # derived from the scores
    assert any("stored total 15" in w for w in out["warnings"]), out["warnings"]


def test_bad_score_cell_becomes_blank_with_a_warning():
    p = _tmp_log([_csv_row("2026-08-31", [3, 2, 2, 2, 2, 2, 2, 2])])
    try:
        out = cycle.read_log(p)
    finally:
        p.unlink()
    assert out["rows"][0]["scores"]["capex"] is None
    assert out["rows"][0]["total"] is None
    assert any("Hyperscaler Capex" in w and "'3'" in w for w in out["warnings"]), out["warnings"]


def test_rows_come_back_oldest_first_whatever_the_file_order():
    p = _tmp_log([_csv_row("2026-08-31", [2] * 8), _csv_row("2026-06-30", [1] * 8),
                  _csv_row("2026-07-31", [0] * 8)])
    try:
        rows = cycle.read_log(p)["rows"]
    finally:
        p.unlink()
    assert [r["review_date"] for r in rows] == ["2026-06-30", "2026-07-31", "2026-08-31"]


def test_example_row_is_flagged():
    p = _tmp_log([_csv_row("2026-01-31", [2] * 8, notes="Example row - delete me.")])
    try:
        out = cycle.read_log(p)
    finally:
        p.unlink()
    assert any("example row" in w for w in out["warnings"]), out["warnings"]


def test_bom_header_is_tolerated():
    """A spreadsheet re-save prepends a BOM; that must not blank review_date."""
    p = _tmp_log([_csv_row("2026-08-31", [2] * 8)], bom=True)
    try:
        out = cycle.read_log(p)
        assert out["rows"][0]["review_date"] == "2026-08-31"
        assert not out["warnings"], out["warnings"]
        # And the strict writer accepts the same file.
        cycle.upsert_row(_review("2026-09-30"), p, today=date(2026, 9, 30))
    finally:
        p.unlink()


def test_extra_column_reads_with_a_warning_and_blocks_writes():
    p = _tmp_log([{**_csv_row("2026-08-31", [2] * 8), "mood": "fine"}],
                 header=cycle.COLUMNS + ["mood"])
    try:
        out = cycle.read_log(p)
        assert len(out["rows"]) == 1
        assert any("mood" in w for w in out["warnings"]), out["warnings"]
        try:
            cycle.upsert_row(_review("2026-09-30"), p, today=date(2026, 9, 30))
        except cycle.CycleError as e:
            assert "header differs" in str(e)
        else:
            raise AssertionError("a hand-edited layout must not be rewritten")
        assert not list(p.parent.glob(p.name + ".*.tmp"))
    finally:
        p.unlink()


# ------------------------------------------------------------------ writing
def test_first_save_creates_the_file_with_the_template_header():
    d = Path(tempfile.mkdtemp())
    p = d / "cycle-score.csv"
    try:
        assert cycle.upsert_row(_review("2026-08-31"), p, today=date(2026, 9, 1)) == "2026-08-31"
        with p.open(newline="") as f:
            header = next(csv.reader(f))
        assert header == cycle.COLUMNS
        rows = _read_all(p)
        assert len(rows) == 1
        assert rows[0]["total"] == "14" and rows[0]["status"] == "GREEN"
        assert rows[0]["capex"] == "2" and rows[0]["power"] == "1"
        assert not list(d.glob("*.tmp")), "atomic write left its temp file"
    finally:
        for f in d.iterdir():
            f.unlink()
        d.rmdir()


def test_same_date_replaces_and_other_dates_sort():
    p = _tmp_log([_csv_row("2026-08-31", [2] * 8, total="16", status="GREEN")])
    try:
        cycle.upsert_row(_review("2026-06-30", scores=[1] * 8), p, today=date(2026, 9, 1))
        cycle.upsert_row(_review("2026-08-31", scores=[0] * 8, notes="revised"), p,
                         today=date(2026, 9, 1))
        rows = _read_all(p)
    finally:
        p.unlink()
    assert [r["review_date"] for r in rows] == ["2026-06-30", "2026-08-31"]
    assert rows[1]["total"] == "0" and rows[1]["status"] == "RED" and rows[1]["notes"] == "revised"


def test_incomplete_review_writes_blank_total_and_status():
    p = _tmp_log()
    try:
        cycle.upsert_row(_review("2026-08-31", scores=[2, 2, 2, None, 2, 2, 2, 2]), p,
                         today=date(2026, 9, 1))
        row = _read_all(p)[0]
    finally:
        p.unlink()
    assert row["power"] == "" and row["total"] == "" and row["status"] == ""


def test_rejects_bad_scores_dates_and_unknown_keys():
    p = _tmp_log()
    today = date(2026, 9, 1)
    cases = {
        "score 3": _review(scores=[3, 2, 2, 2, 2, 2, 2, 2]),
        "future date": _review((today + timedelta(days=1)).isoformat()),
        "not a date": _review("last month"),
        # date.fromisoformat would take both of these; written as typed they
        # sort after every hyphenated date and never match a later save.
        "compact date": _review("20260831"),
        "week date": _review("2026-W35-1"),
        "short month": _review("2026-8-31"),
        "unknown indicator": {**_review(), "scores": {**_review()["scores"], "mood": 2}},
        "scores not an object": {**_review(), "scores": [2] * 8},
        "notes too long": _review(notes="x" * (cycle.MAX_TEXT + 1)),
        "notes not text": _review(notes={"src": "CBRE"}),
        "answer not text": _review(core_question=False),
    }
    try:
        for name, body in cases.items():
            try:
                cycle.upsert_row(body, p, today=today)
            except cycle.CycleError:
                continue
            raise AssertionError(f"{name} must be rejected")
        assert _read_all(p) == [], "a rejected review must not touch the file"
    finally:
        p.unlink()


def test_malformed_row_blocks_the_write():
    header = ",".join(cycle.COLUMNS)
    p = _tmp_log(raw_lines=[header, "2026-08-31,2,2,2,2,2,2,2,2,14,GREEN,yes,unchanged"])  # 13 cells
    try:
        cycle.upsert_row(_review("2026-09-30"), p, today=date(2026, 9, 30))
    except cycle.CycleError as e:
        assert "13 cells" in str(e), e
    else:
        raise AssertionError("a short row would have been silently padded")
    finally:
        p.unlink()


def test_hand_edited_rows_are_preserved_verbatim():
    """Rewriting the file must not 'fix' a row the owner typed."""
    p = _tmp_log([_csv_row("2026-07-31", [2] * 8, total="99", status="GREEN", notes="typed")])
    try:
        cycle.upsert_row(_review("2026-08-31"), p, today=date(2026, 9, 1))
        rows = {r["review_date"]: r for r in _read_all(p)}
    finally:
        p.unlink()
    assert rows["2026-07-31"]["total"] == "99" and rows["2026-07-31"]["notes"] == "typed"


# ---------------------------------------------------------------- HTTP glue
def _with_tmp_log(fn):
    original = cycle.LOG_PATH
    p = _tmp_log()
    cycle.LOG_PATH = p
    try:
        return fn(p)
    finally:
        cycle.LOG_PATH = original
        p.unlink(missing_ok=True)


def test_post_requires_json_content_type():
    code, body = srv.cycle_post(json.dumps(_review()).encode(), "text/plain")
    assert code == 415 and "application/json" in body["error"]


def test_post_rejects_bad_json():
    assert srv.cycle_post(b"{not json", "application/json")[0] == 400
    assert srv.cycle_post(b"[1,2]", "application/json")[0] == 400


def test_post_validation_error_is_400_and_leaves_the_file_alone():
    def run(p):
        code, body = srv.cycle_post(json.dumps(_review(scores=[3] * 8)).encode(),
                                    "application/json; charset=utf-8")
        assert code == 400 and "Hyperscaler Capex" in body["error"], body
        assert _read_all(p) == []
    _with_tmp_log(run)


def test_post_returns_the_rebuilt_payload():
    def run(p):
        code, body = srv.cycle_post(json.dumps(_review("2026-08-31")).encode(),
                                    "application/json")
        assert code == 200, body
        assert body["latest"]["review_date"] == "2026-08-31"
        assert body["latest"]["total"] == 14 and body["latest"]["status"] == "GREEN"
        assert body["exists"] is True and body["warnings"] == []
        assert [i["key"] for i in body["indicators"]] == cycle.KEYS
    _with_tmp_log(run)


def test_post_answers_even_when_something_unexpected_breaks():
    """An exception out of do_POST closes the socket with no response, and the
    form shows "Failed to fetch" with no reason. Whatever breaks, the form gets JSON."""
    original = cycle.upsert_row

    def boom(*a, **k):
        raise RuntimeError("disk on fire")
    cycle.upsert_row = boom
    try:
        code, body = srv.cycle_post(json.dumps(_review()).encode(), "application/json")
    finally:
        cycle.upsert_row = original
    assert code == 500 and "disk on fire" in body["error"], body


# ------------------------------------------------ hand-edited files, harder cases
def test_compact_date_reads_with_a_warning():
    p = _tmp_log([_csv_row("20260831", [2] * 8)])
    try:
        out = cycle.read_log(p)
    finally:
        p.unlink()
    assert len(out["rows"]) == 1
    assert any("20260831" in w and "YYYY-MM-DD" in w for w in out["warnings"]), out["warnings"]


def test_empty_file_reads_as_nothing_and_accepts_the_first_save():
    """`touch cycle-score.csv` must not lock the owner out with "header differs"."""
    fd, name = tempfile.mkstemp(suffix=".csv")           # zero bytes
    os.close(fd)
    p = Path(name)
    try:
        out = cycle.read_log(p)
        assert out["exists"] is True and out["rows"] == [] and out["warnings"] == []
        cycle.upsert_row(_review("2026-08-31"), p, today=date(2026, 9, 1))
        rows = _read_all(p)
        assert [r["review_date"] for r in rows] == ["2026-08-31"]
    finally:
        p.unlink()


def test_non_utf8_file_is_a_warning_on_read_and_a_reason_on_write():
    """A spreadsheet's default CSV export is often cp1252; that must not 500 the view
    or drop the POST's connection."""
    fd, name = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    p = Path(name)
    header = ",".join(cycle.COLUMNS)
    p.write_bytes((header + "\n2026-08-31,2,2,2,2,2,2,2,2,14,GREEN,yes,unchanged,").encode()
                  + b"caf\x92 notes\n")                      # 0x92: cp1252 right single quote
    try:
        out = cycle.read_log(p)
        assert out["rows"] == []
        assert any("UTF-8" in w for w in out["warnings"]), out["warnings"]
        try:
            cycle.upsert_row(_review("2026-09-30"), p, today=date(2026, 9, 30))
        except cycle.CycleError as e:
            assert "UTF-8" in str(e), e
        else:
            raise AssertionError("a file we cannot decode must not be rewritten")
        # cycle_post checks the date against the real clock, so use one in the past.
        original = cycle.LOG_PATH
        cycle.LOG_PATH = p
        try:
            code, body = srv.cycle_post(json.dumps(_review("2026-08-31")).encode(), "application/json")
        finally:
            cycle.LOG_PATH = original
        assert code == 400 and "UTF-8" in body["error"], body
    finally:
        p.unlink()


def test_save_through_a_symlink_writes_the_target_not_the_link():
    d = Path(tempfile.mkdtemp())
    target = d / "synced" / "cycle-score.csv"
    target.parent.mkdir()
    link = d / "cycle-score.csv"
    link.symlink_to(target)
    try:
        cycle.upsert_row(_review("2026-08-31"), link, today=date(2026, 9, 1))
        assert link.is_symlink(), "the save replaced the link with a plain file"
        assert [r["review_date"] for r in _read_all(target)] == ["2026-08-31"]
        assert not list(d.glob("*.tmp")) and not list(target.parent.glob("*.tmp"))
    finally:
        link.unlink(missing_ok=True)
        for f in target.parent.iterdir():
            f.unlink()
        target.parent.rmdir()
        d.rmdir()


def test_rubric_accepts_star_and_indented_bullets():
    fd, name = tempfile.mkstemp(suffix=".md")
    os.close(fd)
    doc = Path(name)
    body = "\n".join([
        "# x", "",
        *[f"## {i}. Section {i}\n\n- dash\n* star\n  - indented\n\n### GREEN\n- as a bullet\n\n"
          f"### YELLOW\ny\n\n### RED\nr\n" for i in range(1, 9)],
    ])
    doc.write_text(body)
    try:
        rub = cycle.rubric(doc)
    finally:
        doc.unlink()
    assert rub["capex"]["track"] == ["dash", "star", "indented"]
    assert rub["capex"]["rubric"]["GREEN"] == "as a bullet", "bullet marker must not reach the tile"


def test_empty_header_cell_is_named_in_the_warning():
    """A spreadsheet's trailing comma is an extra column called ''."""
    header = ",".join(cycle.COLUMNS) + ","
    p = _tmp_log(raw_lines=[header, "2026-08-31,2,2,2,2,2,2,2,2,14,GREEN,yes,unchanged,x,"])
    try:
        out = cycle.read_log(p)
    finally:
        p.unlink()
    assert any("an empty column" in w for w in out["warnings"]), out["warnings"]
    assert not any("()" in w for w in out["warnings"]), out["warnings"]


def test_row_numbers_are_physical_lines_on_both_paths():
    """The number the page names must be the one a spreadsheet shows, and the same
    number the write path would report for the same line."""
    header = ",".join(cycle.COLUMNS)
    p = _tmp_log(raw_lines=[header, "", "2026-08-31,3,2,2,2,2,2,2,2,,,yes,unchanged,x",
                            "2026-09-30,2,2,2,2,2,2,2,2,14,GREEN,yes,unchanged"])   # 13 cells
    try:
        out = cycle.read_log(p)
        assert any(w.startswith("row 3 ") for w in out["warnings"]), out["warnings"]
        try:
            cycle.upsert_row(_review("2026-10-31"), p, today=date(2026, 10, 31))
        except cycle.CycleError as e:
            assert "row 4 " in str(e), e
        else:
            raise AssertionError("the 12-cell row must block the write")
    finally:
        p.unlink()


def test_concurrent_saves_keep_every_row():
    """ThreadingHTTPServer runs handlers concurrently; a double-clicked Save or two
    tabs must not lose a row or trip over each other's temp file."""
    p = _tmp_log()
    dates = [f"2026-{m:02d}-01" for m in range(1, 9)] * 3          # 24 saves, 8 distinct dates
    errors: list[Exception] = []

    def save(rd):
        try:
            cycle.upsert_row(_review(rd, notes=rd), p, today=date(2026, 9, 1))
        except Exception as e:  # noqa: BLE001 - collected for the assertion
            errors.append(e)

    threads = [threading.Thread(target=save, args=(rd,)) for rd in dates]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    try:
        rows = _read_all(p)
    finally:
        p.unlink()
        for leftover in p.parent.glob(p.name + ".*.tmp"):
            leftover.unlink()
    assert not errors, errors
    assert [r["review_date"] for r in rows] == sorted(set(dates))


# ------------------------------------------------------------------ payload
def test_build_cycle_reports_latest_and_previous():
    p = _tmp_log([_csv_row("2026-07-31", [1] * 8), _csv_row("2026-08-31", [2] * 8)])
    try:
        out = cycle.build_cycle(p)
    finally:
        p.unlink()
    assert out["latest"]["review_date"] == "2026-08-31" and out["latest"]["total"] == 16
    assert out["previous"]["review_date"] == "2026-07-31" and out["previous"]["total"] == 8
    assert out["max_score"] == 16 and out["rubric_error"] is None
    assert out["core_question"] and "AXTI" in out["core_question"]
    assert out["bands"][0] == {"status": "GREEN", "lo": 13, "hi": 16}


def test_build_cycle_survives_a_missing_doc():
    """No rubric is a warning on the page, not a dead view: scores still save."""
    out = cycle.build_cycle(Path("/nonexistent/cycle-score.csv"),
                            doc_path=Path("/nonexistent/doc.md"))
    assert out["rubric_error"]
    assert [i["label"] for i in out["indicators"]] == [lbl for _, lbl in cycle.INDICATORS]
    assert out["indicators"][0]["rubric"] == {}
    assert out["latest"] is None and out["exists"] is False


def _main() -> int:
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL  {name}: {e}")
        except Exception as e:  # noqa: BLE001 - surface any error as a failure
            failures += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{'FAILED' if failures else 'ALL PASSED'} ({failures} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
