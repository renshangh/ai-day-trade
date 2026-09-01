import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from lumibot.backtesting import PandasDataBacktesting
from lumibot.components.agents import AgentRunResult, MCPServer
from lumibot.entities import Asset, Data
from lumibot.strategies import Strategy
import lumibot.components.agents.runtime as runtime_module


SERVER_SCRIPT = """
import argparse
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("transport-test", host="127.0.0.1", port=0)

@mcp.tool()
def echo_market_state(symbol: str = "TEST", note: str = "") -> dict:
    return {
        "symbol": symbol,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.transport == "streamable-http":
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)
"""


def _utc_iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _event(kind: str, *, text: str | None = None, tool_name: str | None = None, payload: dict | None = None):
    from lumibot.components.agents import AgentTraceEvent

    return AgentTraceEvent(
        kind=kind,
        text=text,
        tool_name=tool_name,
        payload=payload,
        timestamp=_utc_iso_timestamp(),
    )


class TransportRuntime:
    def run(self, request):
        tool_map = {tool.name: tool.function for tool in request.bound_tools}
        payload = {"symbol": request.context["symbol"], "note": request.context["note"]}
        events = [_event("tool_call", tool_name="echo_market_state", payload=payload)]
        result = tool_map["echo_market_state"](payload)
        normalized = result if isinstance(result, dict) else {"value": result}
        events.append(_event("tool_result", tool_name="echo_market_state", payload=normalized))
        structured = normalized.get("structuredContent") or {}
        if not isinstance(structured, dict):
            structured = {}
        summary_symbol = structured.get("symbol") or normalized.get("symbol")
        if not summary_symbol:
            for entry in normalized.get("content") or []:
                if not isinstance(entry, dict):
                    continue
                text = entry.get("text")
                if not isinstance(text, str):
                    continue
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict) and isinstance(parsed.get("symbol"), str):
                    summary_symbol = parsed["symbol"]
                    break
        if not summary_symbol:
            summary_symbol = "unknown"
        summary = f"Transport said: {summary_symbol}"
        events.append(_event("text", text=summary))
        return AgentRunResult(summary=summary, model=request.model, events=events)


class TransportStrategy(Strategy):
    def initialize(self):
        self.sleeptime = "1D"
        self.agents.create(
            name="research",
            system_prompt="Call the external MCP tool once.",
            default_model="stub-transport",
            tools=[],
            mcp_servers=[self.parameters["mcp_server"]],
            _runtime=TransportRuntime(),
        )

    def on_trading_iteration(self):
        result = self.agents["research"].run(context={"symbol": "TRNS", "note": "hello"})
        self.vars.agent_result = result.summary


@pytest.fixture
def stdio_mcp_script():
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "stdio_mcp_server.py"
        script_path.write_text(textwrap.dedent(SERVER_SCRIPT), encoding="utf-8")
        yield script_path


@pytest.fixture
def streamable_http_server(stdio_mcp_script):
    port = _find_free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            str(stdio_mcp_script),
            "--transport",
            "streamable-http",
            "--port",
            str(port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port(port)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, timeout_s: float = 10.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for MCP streamable HTTP server on port {port}")


def _test_data():
    index = pd.date_range("2025-01-06", periods=2, freq="D", tz="America/New_York")
    asset = Asset("TRNS", Asset.AssetType.STOCK)
    df = pd.DataFrame(
        {
            "open": [10.0, 10.5],
            "high": [10.5, 11.0],
            "low": [9.8, 10.1],
            "close": [10.2, 10.8],
            "volume": [1000, 1000],
        },
        index=index,
    )
    return {asset: Data(asset, df, timestep="day")}


@pytest.mark.usefixtures("disable_datasource_override")
def test_stdio_mcp_transport_support(monkeypatch, tmp_path, stdio_mcp_script):
    monkeypatch.setenv("LUMIBOT_CACHE_FOLDER", str(tmp_path / "cache"))
    server = MCPServer(
        name="stdio-test",
        transport="stdio",
        command=sys.executable,
        args=[str(stdio_mcp_script)],
        exposed_tools=["echo_market_state"],
    )
    _, strategy = TransportStrategy.run_backtest(
        datasource_class=PandasDataBacktesting,
        backtesting_start=datetime(2025, 1, 6),
        backtesting_end=datetime(2025, 1, 7),
        pandas_data=_test_data(),
        benchmark_asset=None,
        analyze_backtest=False,
        show_plot=False,
        save_tearsheet=False,
        show_tearsheet=False,
        show_indicators=False,
        save_logfile=False,
        show_progress_bar=False,
        quiet_logs=True,
        parameters={"mcp_server": server},
    )
    assert strategy.vars.agent_result == "Transport said: TRNS"


@pytest.mark.usefixtures("disable_datasource_override")
def test_streamable_http_mcp_transport_support(monkeypatch, tmp_path, streamable_http_server):
    monkeypatch.setenv("LUMIBOT_CACHE_FOLDER", str(tmp_path / "cache"))
    server = MCPServer(
        name="streamable-http-test",
        transport="streamable_http",
        url=streamable_http_server,
        exposed_tools=["echo_market_state"],
    )
    _, strategy = TransportStrategy.run_backtest(
        datasource_class=PandasDataBacktesting,
        backtesting_start=datetime(2025, 1, 6),
        backtesting_end=datetime(2025, 1, 7),
        pandas_data=_test_data(),
        benchmark_asset=None,
        analyze_backtest=False,
        show_plot=False,
        save_tearsheet=False,
        show_tearsheet=False,
        show_indicators=False,
        save_logfile=False,
        show_progress_bar=False,
        quiet_logs=True,
        parameters={"mcp_server": server},
    )
    assert strategy.vars.agent_result == "Transport said: TRNS"


def test_stdio_transport_sends_child_stderr_to_devnull_when_quiet(monkeypatch):
    captured: dict[str, object] = {}

    class DummyStdioContext:
        async def __aenter__(self):
            return object(), object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def initialize(self):
            return None

        async def list_tools(self):
            return type("Result", (), {"tools": []})()

    def fake_stdio_client(parameters, errlog=None):
        captured["errlog"] = errlog
        return DummyStdioContext()

    monkeypatch.setattr(runtime_module, "stdio_client", fake_stdio_client)
    monkeypatch.setattr(runtime_module, "ClientSession", lambda read_stream, write_stream: DummySession())
    monkeypatch.setenv("IS_BACKTESTING", "true")
    monkeypatch.setenv("BACKTESTING_QUIET_LOGS", "true")

    server = MCPServer(
        name="stdio-test",
        transport="stdio",
        command=sys.executable,
        args=["fake_server.py"],
        exposed_tools=["echo_market_state"],
    )

    runtime_module.list_mcp_tools(server)

    errlog = captured["errlog"]
    assert errlog is not sys.stderr
    assert getattr(errlog, "name", None) == runtime_module.os.devnull


def test_stdio_transport_keeps_child_stderr_when_not_quiet(monkeypatch):
    captured: dict[str, object] = {}

    class DummyStdioContext:
        async def __aenter__(self):
            return object(), object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def initialize(self):
            return None

        async def list_tools(self):
            return type("Result", (), {"tools": []})()

    def fake_stdio_client(parameters, errlog=None):
        captured["errlog"] = errlog
        return DummyStdioContext()

    monkeypatch.setattr(runtime_module, "stdio_client", fake_stdio_client)
    monkeypatch.setattr(runtime_module, "ClientSession", lambda read_stream, write_stream: DummySession())
    monkeypatch.setenv("IS_BACKTESTING", "true")
    monkeypatch.setenv("BACKTESTING_QUIET_LOGS", "false")

    server = MCPServer(
        name="stdio-test",
        transport="stdio",
        command=sys.executable,
        args=["fake_server.py"],
        exposed_tools=["echo_market_state"],
    )

    runtime_module.list_mcp_tools(server)

    assert captured["errlog"] is sys.stderr


# --- mcp API contract -------------------------------------------------------
#
# `mcp` was pinned `>=1.26.0` with no upper bound, so mcp 2.0 was installed
# automatically and broke the agent runtime three ways at once:
#
#   1. `streamablehttp_client` was renamed `streamable_http_client`
#   2. `headers` / `timeout` / `sse_read_timeout` were replaced by an injected
#      `http_client`
#   3. the yielded `TransportStreams` went from a 3-tuple to a 2-tuple, dropping
#      the get-session-id callable that `_stream_http_session` unpacks
#
# The symptom was an ImportError surfacing from inside a strategy's agent
# runtime, which says nothing about a dependency having moved. These assert the
# shape `runtime.py` actually depends on, so the next incompatible release fails
# here with a message naming the problem instead.


_RENAME_HINT = (
    "mcp renamed streamablehttp_client (2.0 calls it streamable_http_client). "
    "lumibot/components/agents/runtime.py imports the old name; either adapt "
    "the runtime to the new API or keep the mcp<2 pin."
)


def _client_factory():
    """The factory `runtime.py` imports, or a named failure if it is gone.

    Resolved with getattr on the module rather than `from ... import <name>`:
    a direct import of a removed symbol raises a bare ImportError, which is
    precisely the uninformative failure these tests exist to replace.
    """
    from mcp.client import streamable_http

    factory = getattr(streamable_http, "streamablehttp_client", None)
    assert factory is not None, _RENAME_HINT
    return factory


def test_streamable_http_client_exists_under_the_name_runtime_imports():
    assert _client_factory() is not None


def test_streamable_http_client_accepts_the_arguments_runtime_passes():
    """runtime.py passes headers/timeout/sse_read_timeout/terminate_on_close.

    mcp 2.0 removed the first three in favour of a pre-built httpx client, so a
    rename-only shim would still fail at the call.
    """
    import inspect

    params = inspect.signature(_client_factory()).parameters
    for name in ("headers", "timeout", "sse_read_timeout", "terminate_on_close"):
        assert name in params, (
            f"mcp's streamablehttp_client no longer accepts {name!r}; "
            "runtime._stream_http_session passes it"
        )


def test_streamable_http_client_still_yields_three_values():
    """`async with streamablehttp_client(...) as (read, write, get_session_id)`.

    mcp 2.0's TransportStreams is a 2-tuple, so this unpacking raises a
    ValueError at runtime rather than anything that names the cause.
    """
    import typing

    factory = _client_factory()
    # Read from the annotation, and treat *failing to read it* as a reportable
    # outcome rather than letting a NameError or KeyError surface raw. mcp already
    # has TYPE_CHECKING-only names in this signature (`httpx2.AsyncClient` in
    # 2.x), so get_type_hints is not guaranteed to resolve.
    try:
        yielded = typing.get_args(typing.get_type_hints(factory)["return"])[0]
        arity = len(typing.get_args(yielded))
    except (KeyError, NameError, IndexError, TypeError) as exc:
        pytest.fail(
            f"Could not read the yield type of mcp's streamablehttp_client ({exc!r}). "
            "runtime._stream_http_session unpacks (read, write, get_session_id); "
            "verify that shape by hand before lifting the mcp<2 pin."
        )
    assert arity == 3, (
        "mcp's streamablehttp_client no longer yields (read, write, get_session_id); "
        "runtime._stream_http_session unpacks three values"
    )
