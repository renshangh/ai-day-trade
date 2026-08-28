# SEC Submissions Cache Never Expires, Silently Staling Earnings Data

**Date:** 2026-08-28
**Last Updated:** 2026-08-28
**Status:** Fixed for SEC (TTL + regression tests). `lumibot/macro/fred.py` still affected.
**Audience:** Both (AI agents and contributors)
**Scope:** `lumibot/fundamentals/sec.py` `_get_json`, and its downstream consumer
`trading_desk/research/earnings_dates.py` -> `trading_desk/research/earnings_dates.json`.

## Summary

`SECFundamentals._get_json` caches SEC responses to disk **permanently**. There is
no TTL and no staleness check:

```python
def _get_json(self, url: str, cache_path: Path) -> dict[str, Any]:
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    ...
```

For immutable objects this is correct. But it is also applied to
`submissions/CIK*.json` — the endpoint that lists everything a company has ever
filed, which changes **every time that company files anything**. Once a symbol's
submissions file is on disk, LumiBot never sees another filing from that company
again.

The practical effect: **re-running the earnings collector is a silent no-op.** It
prints a full, healthy-looking progress log, reports "wrote ...json", and
rewrites byte-for-byte the same stale data it started with. Nothing warns you.

## How it surfaced

While reviewing open swing positions, `trading_desk/earnings.py` was used to
check for upcoming prints. FN's `last_reported` came back as **2026-05-04**, but
FN had demonstrably reported on **2026-08-17** — that print gapped the stock
-13.58% the next morning and is recorded in the trade journal.

Diagnosis sequence:

1. `earnings_dates.json` mtime was **Aug 17 11:12**, 11 days old. Initial (wrong)
   hypothesis: the collector simply ran that morning, before FN's after-close
   release.
2. Re-ran the collector. It completed cleanly, exit 0, 249/271 symbols — and FN
   still showed only `['2026-02-02', '2026-05-04']` for 2026. The newest date
   anywhere in the 249-symbol file was still `2026-08-13`, unchanged.
3. Queried EDGAR through `SECFundamentals` directly: FN's most recent filing of
   any kind appeared to be a Form 4 on 2026-08-13. No 8-K since May.
4. Inspected `~/.lumibot/cache/sec/submissions/`: **all 255 files dated Aug 17 or
   earlier.** Nothing had been re-fetched.
5. Re-ran the same single-symbol query with `LUMIBOT_SEC_CACHE_DIR` pointed at an
   empty directory. FN's 8-K appeared immediately:

   ```
   2026-08-18  10-K
   2026-08-17  8-K   items='1.01,2.02,2.03,5.02,9.01'  accepted=2026-08-17T20:22:03.000Z
   ```

   Item 2.02, accepted 20:22 UTC = 4:22 PM ET = `after_close`. Exactly the print
   the journal recorded. The cache had been hiding it.

## Blast radius

Any code path reading a mutable SEC endpoint through this cache:

| Endpoint | Mutable? | Cached forever? | Safe? |
|---|---|---|---|
| `submissions/CIK*.json` | **Yes** — grows with every filing | Yes | **No** |
| `api/xbrl/companyfacts/CIK*.json` | **Yes** — new facts each report | Yes | **No** |
| `filings/<cik>/<accession>/<doc>` | No — a filed document is immutable | Yes | Yes |
| `company_tickers.json` | Yes — slowly (listings change) | Yes | Marginal |

So `companyfacts` has the same defect as `submissions` and is used by
fundamentals consumers beyond the earnings collector. Individual filing documents
are genuinely immutable and caching them forever is correct.

This is not a Rule #1 violation — no market data is fabricated, and nothing
invents bars. But it is adjacent in spirit: a stale answer is served with the
same confidence as a fresh one, and the caller cannot tell the difference.

## What was done

1. **Data refreshed for real.** Re-ran the collector with
   `LUMIBOT_SEC_CACHE_DIR` pointed at a clean directory, forcing live fetches.
   `earnings_dates.json` now contains FN `2026-08-17`; newest date in the file
   moved from `2026-08-13` to `2026-08-27`.
2. **Live cache repaired, scoped to `submissions/` only.** The stale directory was
   **moved, not deleted**, and the fresh copy put in its place:

   ```
   ~/.lumibot/cache/sec/submissions.stale-2026-08-17/   # backup, 255 files, Aug 17
   ~/.lumibot/cache/sec/submissions/                    # current, 254 files, Aug 28
   ```

   `companyfacts/` and `filings/` were left untouched. The backup can be restored
   by swapping the two directory names.
3. **No code change.** See below.

## Same defect exists independently in `lumibot/macro/fred.py`

`FREDMacro` does **not** share `SECFundamentals`' cache helpers — it has its own
`_get_json` at `lumibot/macro/fred.py:121` with the identical shape:

```python
def _get_json(self, url: str, params: dict[str, Any], cache_path: Path) -> dict[str, Any]:
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
```

FRED series are both **extended** (new observations each period) and **revised**
(existing observations restated), so a permanent cache is wrong there for two
reasons rather than one. It is untouched by the SEC fix and still carries the bug.

Deliberately left out of scope: FRED is a different data source with different
revision semantics, and folding it in would widen a targeted fix into a
two-provider change. It deserves its own PR, ideally sharing a single TTL-aware
cache helper between the two clients rather than duplicating the logic a third
time.

## Recommended fix

Add a TTL to `_get_json`/`_get_text` for mutable endpoints — respect
`cache_path.stat().st_mtime` and re-fetch past a max age (24h is reasonable for
`submissions`; filings documents should stay permanent). Options worth weighing:

- TTL parameter on `_get_json`, passed per call site, so immutable filing
  documents keep permanent caching while `submissions` and `companyfacts` expire.
- SEC supports conditional requests; an `If-Modified-Since` / ETag path would
  refresh cheaply without giving up cache benefit.

**Implemented.** `_get_json` and `_get_text` now take an optional
`max_age_seconds`; `None` still means "cache forever" and is kept for archive
filing documents, which are immutable. TTLs are applied only to the mutable index
endpoints (`SUBMISSIONS_CACHE_MAX_AGE_SECONDS` and
`COMPANY_FACTS_CACHE_MAX_AGE_SECONDS` at 24h, `TICKER_MAP_CACHE_MAX_AGE_SECONDS`
at 7 days).

Two robustness behaviors came with it, because adding expiry introduces failure
modes a permanent cache did not have:

- **Stale-on-failure.** If the re-fetch fails and an expired copy is on disk, the
  expired copy is served with a loud warning rather than raising. Without this, a
  run that previously worked offline would start failing the moment a TTL lapsed
  and SEC was unreachable. With no cached copy at all, the error still surfaces.
- **Corrupt-cache recovery.** An interrupted write leaves unparseable JSON.
  Previously that `JSONDecodeError` propagated to the caller forever, since
  nothing ever replaced the file. It is now discarded and re-fetched.

## Secondary finding: `filings.recent` is a truncated window

The fresh run returned **8,797** events across 248 symbols, *fewer* than the
stale run's 8,856 across 249. That is not a regression from the refresh.

`earnings_dates.py` reads only `filings.recent`, which SEC caps at roughly the
last 1,000 filings per company. For companies that file often, old 8-Ks age out
of that array over time, so the deep history shortens as the window slides
forward. Older filings live in the `filings.files[]` archive pages, which the
collector never reads.

Consequence: earnings history silently erodes at the back for high-filing-volume
companies. `project_next` uses only the last 8 slots
(`RECENT_SLOTS_FOR_PROJECTION`) so projections are unaffected, but the drift
studies in `trading_desk/research/` that want long history are exposed. Worth
following the `filings.files[]` pagination if deep history matters.

The 17 symbols that failed with `ValueError` are mostly ETFs (`IWM`, `SMH`,
`XLB`, `XLC`, `XLE`, `XLF`, `XLI`, `XLK`, `XLP`) which file no 8-Ks — expected.
The handful of real operating companies in that list (`EA`, `EQR`, `HES`, `MMC`)
varied between the two runs, which points at transient SEC errors rather than
anything structural; the collector already swallows per-symbol failures so one
bad response cannot abort a run.

## For the next agent

- Do **not** trust `earnings_dates.json` freshness from its mtime alone. The file
  is rewritten on every run whether or not the underlying data changed.
- To force a genuine refresh:
  `LUMIBOT_SEC_CACHE_DIR=<empty dir> python3 trading_desk/research/earnings_dates.py`
- Sanity check after any run: the newest date across the file should be within a
  few days of today during earnings season.
  ```bash
  python3 -c "import json;d=json.load(open('trading_desk/research/earnings_dates.json'));print(max(x['date'] for v in d.values() for x in v))"
  ```
- The collector **overwrites** `earnings_dates.json` wholesale with
  `OUT.write_text(...)`. A partial or failed run clobbers good data. Back the file
  up before re-running.

## Incidental finding: `.gitignore` `*cache*` swallows UPPERCASE docs on macOS

Writing this file exposed a separate trap. `.gitignore` line 10 is a bare
`*cache*`, and macOS filesystems are case-insensitive, so the pattern matches
`..._CACHE_NEVER_EXPIRES.md` too. This document was silently untracked on
creation — `git status` showed nothing at all.

It collides directly with the `AGENTS.md` naming convention, which mandates
UPPERCASE doc filenames. Any future doc about caching is invisible to git by
default, and the failure is silent: no error, no warning, the file simply never
appears.

Fixed following the negation pattern already established around that rule:

```
!docs/**/*.md
!docsrc/**/*.rst
```

Scoped to documentation file extensions rather than loosening `*cache*`, per the
guidance in `trading_records/README.md` — "add an explicit negation, don't loosen
the wildcard." Verified that `git status` afterwards showed only this doc and
`.gitignore` itself, and that `trading_records/` and `earnings_dates.json` remain
correctly ignored.

Note the gitignore limitation this does *not* solve: a negation cannot re-include
a file whose **parent directory** is excluded. A doc at `docs/cache/FOO.md` would
still be ignored because `docs/cache/` itself matches `*cache*`. Avoid `cache` in
directory names under `docs/`.
