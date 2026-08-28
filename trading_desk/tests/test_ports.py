"""Tests for the fixed per-branch port assignment.

Run: python3 trading_desk/tests/test_ports.py

Three separate things used to pick a port independently -- the preview
launcher's autoPort, the .command launcher scanning 8799-8803, and the PORT env
var -- so the dashboard turned up somewhere different most times it started, and
a stale server from another branch could keep answering on the port you
expected. These pin the mapping and the HEAD parsing that drives it.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import server as srv  # noqa: E402

REPO_ROOT = HERE.parent.parent


def test_main_and_dev_own_distinct_ports():
    """The whole point: the two branches cannot collide."""
    assert srv.BRANCH_PORTS["main"] != srv.BRANCH_PORTS["dev"]
    assert srv.port_for_branch("main") == srv.BRANCH_PORTS["main"]
    assert srv.port_for_branch("dev") == srv.BRANCH_PORTS["dev"]


def test_unlisted_branches_share_the_dev_port():
    """Anything that is not main is work headed for dev.

    Giving every topic branch its own port would recreate the drift this exists
    to remove.
    """
    for branch in ("feat/whatever", "fix/some-bug", "version/4.5.31", "", None):
        assert srv.port_for_branch(branch) == srv.DEV_PORT, branch


def test_dev_port_constant_agrees_with_the_table():
    assert srv.DEV_PORT == srv.BRANCH_PORTS["dev"]


def _head_fixture(contents: str, *, worktree: bool = False) -> Path:
    """A throwaway repo root whose .git/HEAD (or .git file) holds `contents`."""
    root = Path(tempfile.mkdtemp())
    if worktree:
        real = root / "actual-git-dir"
        real.mkdir()
        (real / "HEAD").write_text(contents, encoding="utf-8")
        (root / ".git").write_text(f"gitdir: {real}\n", encoding="utf-8")
    else:
        gd = root / ".git"
        gd.mkdir()
        (gd / "HEAD").write_text(contents, encoding="utf-8")
    return root


def _branch_with_root(root: Path) -> str | None:
    original = srv.REPO_ROOT
    srv.REPO_ROOT = root
    try:
        return srv.current_branch()
    finally:
        srv.REPO_ROOT = original


def test_reads_a_normal_head_file():
    assert _branch_with_root(_head_fixture("ref: refs/heads/dev\n")) == "dev"
    assert _branch_with_root(_head_fixture("ref: refs/heads/main\n")) == "main"
    # A slash-bearing branch name must survive intact.
    assert _branch_with_root(_head_fixture("ref: refs/heads/feat/a/b\n")) == "feat/a/b"


def test_reads_head_through_a_worktree_gitdir_pointer():
    """Running the main and dev dashboards at once needs a second worktree.

    There `.git` is a *file* containing `gitdir: <path>`, not a directory, so
    parsing has to follow the pointer or the port silently falls back to dev's.
    """
    root = _head_fixture("ref: refs/heads/main\n", worktree=True)
    assert _branch_with_root(root) == "main"
    assert srv.port_for_branch(_branch_with_root(root)) == srv.BRANCH_PORTS["main"]


def test_detached_head_is_reported_as_unknown_not_guessed():
    """A bare SHA is not a branch; claiming one would pick a port on a guess."""
    root = _head_fixture("9f1a2b3c4d5e6f708192a3b4c5d6e7f809192a3b\n")
    assert _branch_with_root(root) is None
    assert srv.port_for_branch(None) == srv.DEV_PORT


def test_missing_or_unreadable_git_metadata_is_survivable():
    empty = Path(tempfile.mkdtemp())            # no .git at all
    assert _branch_with_root(empty) is None
    junk = _head_fixture("not a ref line\n")
    assert _branch_with_root(junk) is None
    bad_ptr = Path(tempfile.mkdtemp())
    (bad_ptr / ".git").write_text("this is not a gitdir pointer\n", encoding="utf-8")
    assert _branch_with_root(bad_ptr) is None


# ---- the three launchers must agree, or the drift comes straight back --------
def test_launch_json_ports_match_the_server_table():
    cfgs = json.loads((REPO_ROOT / ".claude" / "launch.json").read_text())["configurations"]
    by_name = {c["name"]: c for c in cfgs}
    assert set(by_name) == {"trading-desk-dev", "trading-desk-main"}
    assert by_name["trading-desk-dev"]["port"] == srv.BRANCH_PORTS["dev"]
    assert by_name["trading-desk-main"]["port"] == srv.BRANCH_PORTS["main"]


def test_launch_json_never_reintroduces_autoport():
    """autoPort is exactly the drift this change removes."""
    cfgs = json.loads((REPO_ROOT / ".claude" / "launch.json").read_text())["configurations"]
    for c in cfgs:
        assert c.get("autoPort") is False, f"{c['name']} must pin its port"
        # The declared port and the --port it passes must not disagree, or the
        # preview would open a URL the server is not listening on.
        args = c["runtimeArgs"]
        assert "--port" in args, c["name"]
        assert int(args[args.index("--port") + 1]) == c["port"], c["name"]


def test_command_launcher_uses_the_same_ports():
    """The double-click launcher is a third port-picker; it has to agree too."""
    script = (REPO_ROOT / "trading_desk" / "Launch Trading Desk.command").read_text()
    assert f"main) PORT={srv.BRANCH_PORTS['main']}" in script
    assert f"*)    PORT={srv.DEV_PORT}" in script
    # And it must not have gone back to scanning a range.
    assert "for candidate in" not in script, "launcher is scanning ports again"


def test_server_help_documents_the_override():
    """--port has to stay available: pinning must not remove the escape hatch."""
    src = (REPO_ROOT / "trading_desk" / "server.py").read_text()
    assert re.search(r'add_argument\(\s*"--port"', src)
    assert "override the branch's fixed port" in src


def test_wrong_branch_port_is_flagged():
    """`--port 8800` from a dev checkout serves dev code at main's URL.

    That is allowed -- an explicit port must be able to win -- but it has to be
    said out loud, or the confusion this change removes just moves somewhere else.
    """
    src = (REPO_ROOT / "trading_desk" / "server.py").read_text()
    assert "serving its code at {where} instead" in src
    # The trigger must be "not the port this branch would have chosen". Keying off
    # ownership alone warned on every topic branch, which shares dev's port by
    # design -- noise on every ordinary run.
    assert "if port != pinned:" in src


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
