"""Shared notion of "is this credential actually set".

Extracted so the suite has one definition rather than several. `conftest.py`'s
per-provider API gate and the acceptance backtests' env requirement both need to
answer the same question, and answering it two different ways is how an
environment ends up skipped by one check and hard-failed by the other.
"""

from __future__ import annotations

import os

# Values that are present but mean "not filled in". Copying an example env file
# leaves these behind, and treating them as real credentials is worse than
# treating them as absent: the test proceeds and fails on a confusing auth error
# instead of skipping with a clear reason.
_PLACEHOLDERS = frozenset({
    "<your key here>",
    "<your api key>",
    "<api key>",
    "uname",
    "username",
    "password",
    "<username>",
    "<password>",
    "none",
    "null",
    "changeme",
})


def is_placeholder(value: str | None) -> bool:
    """True when `value` is missing, blank, or an obvious fill-me-in token."""
    if value is None:
        return True
    v = str(value).strip().lower()
    if not v:
        return True
    return v in _PLACEHOLDERS


def is_configured(key: str) -> bool:
    """True when env var `key` holds something usable as a credential.

    GitHub Actions injects `${{ secrets.X }}` as an empty string when the secret
    does not exist, so "set but empty" is the normal shape of an absent secret in
    CI and must read as unconfigured.
    """
    return not is_placeholder(os.environ.get(key))
