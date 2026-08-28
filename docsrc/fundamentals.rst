SEC Fundamentals
================

LumiBot includes native SEC EDGAR fundamentals for US equities. These are core
strategy data tools, not AI-only tools: deterministic Python strategies can call
them directly, and AI agents receive the same point-in-time tools as built-ins.
The tools use public SEC APIs directly, require no API key, and cache responses
locally.

Available strategy methods:

.. code-block:: python

   self.fundamentals.get_income_statement("AAPL")
   self.fundamentals.get_balance_sheet("AAPL")
   self.fundamentals.get_cash_flow("AAPL")
   self.fundamentals.get_company_facts("AAPL")
   self.fundamentals.get_filings("AAPL", form="10-K")
   self.fundamentals.search_filing("AAPL", accession_number="...", query="risk")
   self.fundamentals.get_filing_document("AAPL", accession_number="...")

``get_company_facts()`` returns a compact latest-facts view by default, capped
at important fields so agent runs do not flood the model context. Pass
``max_facts=None`` for the full compact fact set, or ``raw=True`` for the raw
SEC companyfacts payload when you explicitly need it.

.. image:: ../docs/assets/ai_committee/docs_sec_point_in_time_cache.png
   :alt: SEC fundamentals and filing research flow

Point-In-Time Behavior
----------------------

Backtests must not see future financial statements or filings. LumiBot gates SEC
facts and filings by the current strategy datetime unless you explicitly pass
``as_of``. For facts, the SEC ``filed`` date is used. For filings, the SEC
acceptance datetime is used when available, with filing date as the fallback.

Caching
-------

SEC responses are cached under ``~/.lumibot/cache/sec`` by default. Override this
with ``LUMIBOT_SEC_CACHE_DIR``. LumiBot also rate limits SEC requests and sends a
contact-style user agent. Override the default with ``LUMIBOT_SEC_USER_AGENT``.

Cache lifetimes differ by what is being cached, because SEC objects are not all
equally stable:

.. list-table::
   :header-rows: 1
   :widths: 40 20 40

   * - Cached object
     - Expires after
     - Why
   * - Filing documents (10-K, 10-Q, 8-K text)
     - never
     - A filed document is immutable once EDGAR has it.
   * - Company submissions index
     - 24 hours
     - Grows every time the company files anything.
   * - Company facts (XBRL)
     - 24 hours
     - New facts are added with each report.
   * - Ticker-to-CIK map
     - 7 days
     - Listings change, but slowly.

This matters if you build your own collectors on top of ``SECFundamentals``. The
index endpoints previously cached forever, which meant a repeated run could
silently return the same stale answer and never see a newly filed report.

If a cached copy has expired and SEC cannot be reached, LumiBot serves the expired
copy and logs a warning rather than failing, so an outage does not break a run
that would otherwise work offline. To force a full refresh, point
``LUMIBOT_SEC_CACHE_DIR`` at an empty directory.

Agent Tools
-----------

Agents receive these built-ins:

- ``get_income_statement``
- ``get_balance_sheet``
- ``get_cash_flow``
- ``get_company_facts``
- ``get_filings``
- ``search_filing``
- ``get_filing_document``

Prefer ``search_filing`` before reading a full filing document. Annual reports
and quarterly filings can be long, and search keeps the model context focused.

Related Macro Data
------------------

For economic context such as rates, inflation, unemployment, GDP, liquidity, and
credit spreads, use :doc:`macro_data`. SEC fundamentals are company-specific;
FRED macro data is economy and market-regime context.

Filing Search
-------------

.. image:: ../docs/assets/ai_committee/docs_filing_search_workflow.png
   :alt: SEC filing search workflow for Lumibot agents

Filing search is useful for agent workflows modeled after real fundamental
research. A researcher can identify a relevant annual report, search for risk
factors or accounting details, and only open the full filing when it needs more
context.
