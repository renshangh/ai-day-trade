"""Gating rules for the acceptance backtests' credential requirements.

Run: python3 -m pytest tests/backtest/test_acceptance_env_gating.py

`_require_env` decides between failing CI loudly and skipping. Both behaviours
matter and they pull in opposite directions, so the boundary is pinned here
rather than left to be rediscovered the next time a fork goes red.

No network, no credentials, no subprocess -- only the decision function.
"""

from __future__ import annotations

import pytest

from tests.backtest import test_acceptance_backtests_ci as acc

# Spelled out locally rather than imported, so the behavioural tests below fail
# *behaviourally* against the previous implementation (skip vs fail) instead of
# erroring on a symbol that did not exist yet. `test_union_covers_...` guards the
# two lists against drifting apart.
ACCEPTANCE_ENV = [
    "LUMIBOT_CACHE_S3_BUCKET",
    "LUMIBOT_CACHE_S3_PREFIX",
    "LUMIBOT_CACHE_S3_REGION",
    "LUMIBOT_CACHE_S3_ACCESS_KEY_ID",
    "LUMIBOT_CACHE_S3_SECRET_ACCESS_KEY",
    "DATADOWNLOADER_BASE_URL",
    "DATADOWNLOADER_API_KEY",
    "THETADATA_USERNAME",
    "THETADATA_PASSWORD",
]


def _clear_all(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ACCEPTANCE_ENV:
        monkeypatch.delenv(key, raising=False)
    for key in ("CI", "GITHUB_ACTIONS", "GITHUB_WORKFLOW"):
        monkeypatch.delenv(key, raising=False)


def test_union_covers_every_list_the_cases_actually_require():
    """If a new requirement joins one list but not the union, the
    never-configured check silently stops seeing it."""
    for group in (acc._REQUIRED_S3, acc._REQUIRED_DOWNLOADER, acc._REQUIRED_THETADATA):
        for key in group:
            assert key in acc._ALL_ACCEPTANCE_ENV, f"{key} missing from _ALL_ACCEPTANCE_ENV"
    # And this file's copy must not drift from the module's.
    assert sorted(ACCEPTANCE_ENV) == sorted(acc._ALL_ACCEPTANCE_ENV)


def test_ci_without_any_secret_skips_rather_than_failing(monkeypatch):
    """A fork has none of these. Failing would make CI permanently red for a
    reason a contributor cannot fix, burying the real failures next to it."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(pytest.skip.Exception):
        acc._require_env(["THETADATA_USERNAME", "THETADATA_PASSWORD"])


def test_ci_with_partial_configuration_still_fails_loudly(monkeypatch):
    """This is the case the hard failure exists for: the environment was set up
    and has since lost a key. Silently skipping here would let a real
    misconfiguration pass as green."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("THETADATA_USERNAME", "someone")
    with pytest.raises(pytest.fail.Exception) as excinfo:
        acc._require_env(["THETADATA_USERNAME", "THETADATA_PASSWORD"])
    # The message must name what is missing, not merely that something is.
    assert "THETADATA_PASSWORD" in str(excinfo.value)


def test_partial_configuration_in_an_unrelated_group_still_fails(monkeypatch):
    """The never-configured test spans the union, so a key set in *any* group
    proves the environment was configured -- even a group this case does not need."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("LUMIBOT_CACHE_S3_BUCKET", "some-bucket")
    with pytest.raises(pytest.fail.Exception):
        acc._require_env(["THETADATA_USERNAME", "THETADATA_PASSWORD"])


def test_outside_ci_always_skips(monkeypatch):
    """Unchanged behaviour: a developer's clone should not fail on absent creds."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("THETADATA_USERNAME", "someone")   # partial, but not CI
    with pytest.raises(pytest.skip.Exception):
        acc._require_env(["THETADATA_USERNAME", "THETADATA_PASSWORD"])


def test_release_workflow_skips_even_when_partially_configured(monkeypatch):
    """Pre-existing carve-out: the tag-driven release build does not carry the
    acceptance secrets and must not fail the release over them."""
    _clear_all(monkeypatch)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_WORKFLOW", "Release (PyPI + GitHub)")
    monkeypatch.setenv("THETADATA_USERNAME", "someone")
    with pytest.raises(pytest.skip.Exception):
        acc._require_env(["THETADATA_USERNAME", "THETADATA_PASSWORD"])


def test_fully_configured_env_does_not_skip_or_fail(monkeypatch):
    _clear_all(monkeypatch)
    monkeypatch.setenv("CI", "true")
    for key in ACCEPTANCE_ENV:
        monkeypatch.setenv(key, "value")
    assert acc._require_env(list(ACCEPTANCE_ENV)) is None
