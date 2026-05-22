from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from lumibot.credentials import ALPACA_CONFIG


EASTERN = ZoneInfo("America/New_York")
DEFAULT_SYMBOLS = (
    "NVDA",
    "AAPL",
    "AMD",
    "TSLA",
    "PLTR",
    "META",
    "MSFT",
    "AMZN",
    "GOOGL",
    "AVGO",
    "SMCI",
)
INDEX_SYMBOL = "QQQ"


@dataclass(frozen=True)
class Candidate:
    symbol: str
    last_price: float
    return_from_open_pct: float
    relative_strength_pct: float
    gap_pct: float | None
    vwap: float
    above_vwap: bool
    opening_range_high: float | None
    opening_range_low: float | None
    near_high_of_day_pct: float
    intraday_volume: int
    volume_vs_avg_daily_pct: float | None
    score: float
    reason: str


def _now_et() -> datetime:
    return datetime.now(EASTERN)


def _market_window(now: datetime) -> tuple[datetime, datetime]:
    session_open = datetime.combine(now.date(), time(9, 30), tzinfo=EASTERN)
    session_close = datetime.combine(now.date(), time(16, 0), tzinfo=EASTERN)
    if now < session_open:
        end = session_open
    elif now > session_close:
        end = session_close
    else:
        end = now
    return session_open, end


def _alpaca_client() -> StockHistoricalDataClient:
    api_key = ALPACA_CONFIG.get("API_KEY")
    api_secret = ALPACA_CONFIG.get("API_SECRET")
    if not api_key or not api_secret:
        raise SystemExit("Missing ALPACA_API_KEY or ALPACA_API_SECRET in environment/.env.")
    return StockHistoricalDataClient(api_key, api_secret)


def _normalize_bars_df(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.index, pd.MultiIndex):
        if symbol not in df.index.get_level_values(0):
            return pd.DataFrame()
        df = df.xs(symbol, level=0, drop_level=True)
    df = df.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert(EASTERN)
    return df.sort_index()


def _fetch_bars(
    client: StockHistoricalDataClient,
    symbols: list[str],
    *,
    start: datetime,
    end: datetime,
    timeframe: TimeFrame,
    feed: DataFeed,
) -> dict[str, pd.DataFrame]:
    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=timeframe,
        start=start,
        end=end,
        adjustment=Adjustment.ALL,
        feed=feed,
    )
    barset = client.get_stock_bars(request)
    raw_df = getattr(barset, "df", pd.DataFrame())
    return {symbol: _normalize_bars_df(raw_df, symbol) for symbol in symbols}


def _vwap(df: pd.DataFrame) -> float | None:
    if df.empty or "volume" not in df.columns:
        return None
    volume = float(df["volume"].sum())
    if volume <= 0:
        return None
    typical = (df["high"] + df["low"] + df["close"]) / 3
    return float((typical * df["volume"]).sum() / volume)


def _previous_close(daily_df: pd.DataFrame, today: datetime) -> float | None:
    if daily_df.empty:
        return None
    previous = daily_df[daily_df.index.date < today.date()]
    if previous.empty:
        return None
    return float(previous.iloc[-1]["close"])


def _average_daily_volume(daily_df: pd.DataFrame, today: datetime) -> float | None:
    previous = daily_df[daily_df.index.date < today.date()]
    if previous.empty:
        return None
    volume = previous.tail(20)["volume"].mean()
    if pd.isna(volume) or volume <= 0:
        return None
    return float(volume)


def _score_candidate(
    *,
    return_from_open_pct: float,
    relative_strength_pct: float,
    gap_pct: float | None,
    above_vwap: bool,
    near_high_of_day_pct: float,
    volume_vs_avg_daily_pct: float | None,
) -> float:
    score = 0.0
    score += max(min(relative_strength_pct, 5.0), -5.0) * 8.0
    score += max(min(return_from_open_pct, 5.0), -5.0) * 5.0
    if gap_pct is not None:
        score += max(min(gap_pct, 4.0), -4.0) * 2.0
    if above_vwap:
        score += 18.0
    score += max(0.0, 1.0 - near_high_of_day_pct / 2.0) * 12.0
    if volume_vs_avg_daily_pct is not None:
        score += max(min(volume_vs_avg_daily_pct, 80.0), 0.0) * 0.25
    return round(score, 2)


def _build_reason(candidate: Candidate) -> str:
    parts = [
        f"{candidate.return_from_open_pct:+.2f}% from open",
        f"{candidate.relative_strength_pct:+.2f}% vs {INDEX_SYMBOL}",
        "above VWAP" if candidate.above_vwap else "below VWAP",
    ]
    if candidate.volume_vs_avg_daily_pct is not None:
        parts.append(f"{candidate.volume_vs_avg_daily_pct:.1f}% of avg daily volume")
    parts.append(f"{candidate.near_high_of_day_pct:.2f}% below high of day")
    return "; ".join(parts)


def rank_candidates(symbols: list[str], *, feed: DataFeed) -> list[Candidate]:
    client = _alpaca_client()
    now = _now_et()
    start, end = _market_window(now)
    all_symbols = sorted(set([symbol.upper() for symbol in symbols] + [INDEX_SYMBOL, "SPY"]))

    minute_bars = _fetch_bars(
        client,
        all_symbols,
        start=start,
        end=end,
        timeframe=TimeFrame.Minute,
        feed=feed,
    )
    daily_bars = _fetch_bars(
        client,
        all_symbols,
        start=now - timedelta(days=45),
        end=now,
        timeframe=TimeFrame.Day,
        feed=feed,
    )

    index_df = minute_bars.get(INDEX_SYMBOL, pd.DataFrame())
    if index_df.empty:
        index_return = 0.0
    else:
        index_open = float(index_df.iloc[0]["open"])
        index_last = float(index_df.iloc[-1]["close"])
        index_return = ((index_last / index_open) - 1.0) * 100.0 if index_open > 0 else 0.0

    candidates: list[Candidate] = []
    for symbol in [symbol.upper() for symbol in symbols]:
        df = minute_bars.get(symbol, pd.DataFrame())
        if df.empty or len(df.index) < 5:
            continue

        last_price = float(df.iloc[-1]["close"])
        open_price = float(df.iloc[0]["open"])
        high_of_day = float(df["high"].max())
        intraday_volume = int(df["volume"].sum())
        vwap = _vwap(df)
        if vwap is None or open_price <= 0 or high_of_day <= 0:
            continue

        daily_df = daily_bars.get(symbol, pd.DataFrame())
        prev_close = _previous_close(daily_df, now)
        avg_daily_volume = _average_daily_volume(daily_df, now)
        return_from_open_pct = ((last_price / open_price) - 1.0) * 100.0
        relative_strength_pct = return_from_open_pct - index_return
        gap_pct = ((open_price / prev_close) - 1.0) * 100.0 if prev_close else None
        near_high_of_day_pct = max(((high_of_day - last_price) / high_of_day) * 100.0, 0.0)
        volume_vs_avg_daily_pct = (
            (intraday_volume / avg_daily_volume) * 100.0 if avg_daily_volume else None
        )
        opening_range = df.between_time("09:30", "10:00", inclusive="left")
        opening_range_high = float(opening_range["high"].max()) if not opening_range.empty else None
        opening_range_low = float(opening_range["low"].min()) if not opening_range.empty else None
        above_vwap = last_price > vwap
        score = _score_candidate(
            return_from_open_pct=return_from_open_pct,
            relative_strength_pct=relative_strength_pct,
            gap_pct=gap_pct,
            above_vwap=above_vwap,
            near_high_of_day_pct=near_high_of_day_pct,
            volume_vs_avg_daily_pct=volume_vs_avg_daily_pct,
        )
        candidate = Candidate(
            symbol=symbol,
            last_price=round(last_price, 2),
            return_from_open_pct=round(return_from_open_pct, 2),
            relative_strength_pct=round(relative_strength_pct, 2),
            gap_pct=round(gap_pct, 2) if gap_pct is not None and math.isfinite(gap_pct) else None,
            vwap=round(vwap, 2),
            above_vwap=above_vwap,
            opening_range_high=round(opening_range_high, 2) if opening_range_high else None,
            opening_range_low=round(opening_range_low, 2) if opening_range_low else None,
            near_high_of_day_pct=round(near_high_of_day_pct, 2),
            intraday_volume=intraday_volume,
            volume_vs_avg_daily_pct=round(volume_vs_avg_daily_pct, 2)
            if volume_vs_avg_daily_pct is not None and math.isfinite(volume_vs_avg_daily_pct)
            else None,
            score=score,
            reason="",
        )
        candidates.append(candidate)

    ranked: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        ranked.append(
            Candidate(
                **{
                    **asdict(candidate),
                    "reason": _build_reason(candidate),
                }
            )
        )
    return ranked


def _llm_rerank(candidates: list[Candidate], *, top: int, model: str) -> dict[str, Any] | None:
    if not candidates:
        return None
    try:
        from openai import OpenAI
    except Exception as exc:
        print(f"LLM rerank skipped: openai package unavailable ({exc}).")
        return None

    payload = [asdict(candidate) for candidate in candidates[: min(len(candidates), 12)]]
    system = (
        "You are a cautious intraday trading analyst. Rank liquid US equity day-trade "
        "candidates using only the supplied metrics. Prefer clean long candidates with "
        "relative strength, price above VWAP, volume participation, and proximity to high "
        "of day. Avoid hype, avoid unsupported claims, and do not invent market data. "
        "Return only a valid JSON object."
    )
    user = {
        "task": f"Pick the top {top} day-trade candidates for watchlist only.",
        "output_schema": {
            "top": [
                {
                    "symbol": "ticker",
                    "rank": "integer",
                    "confidence": "low|medium|high",
                    "reason": "one concise sentence grounded in supplied metrics",
                    "risk_note": "one concise risk note",
                }
            ],
            "summary": "one sentence",
        },
        "candidates": payload,
    }
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user)},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        print(f"LLM rerank skipped: {exc}")
    return None


def _print_report(candidates: list[Candidate], *, top: int, llm_result: dict[str, Any] | None) -> None:
    print(f"\nTop {top} day-trade candidates")
    print("=" * 32)

    if llm_result and isinstance(llm_result.get("top"), list):
        selected_symbols = [str(row.get("symbol", "")).upper() for row in llm_result["top"][:top]]
        by_symbol = {candidate.symbol: candidate for candidate in candidates}
        for idx, row in enumerate(llm_result["top"][:top], start=1):
            symbol = str(row.get("symbol", "")).upper()
            candidate = by_symbol.get(symbol)
            if not candidate:
                continue
            print(
                f"{idx}. {symbol} score={candidate.score:.2f} price={candidate.last_price:.2f} "
                f"vwap={candidate.vwap:.2f} rs={candidate.relative_strength_pct:+.2f}%"
            )
            print(f"   LLM: {row.get('reason', '')}")
            print(f"   Risk: {row.get('risk_note', '')}")
    else:
        selected_symbols = [candidate.symbol for candidate in candidates[:top]]
        for idx, candidate in enumerate(candidates[:top], start=1):
            print(
                f"{idx}. {candidate.symbol} score={candidate.score:.2f} "
                f"price={candidate.last_price:.2f} vwap={candidate.vwap:.2f} "
                f"rs={candidate.relative_strength_pct:+.2f}%"
            )
            print(f"   {candidate.reason}")

    print("\nPaper trade commands after setup confirms")
    print("=" * 42)
    for symbol in selected_symbols:
        print(
            "python -m ai_day_trade.alpaca_day_trade "
            f"--symbol {symbol} --max-notional 1000 --take-profit-pct 0.004 "
            "--stop-loss-pct 0.002 --sleeptime 30S"
        )


def _write_report(
    path: Path,
    *,
    candidates: list[Candidate],
    top: int,
    llm_result: dict[str, Any] | None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "top": top,
        "llm_result": llm_result,
        "candidates": [asdict(candidate) for candidate in candidates],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m ai_day_trade.find_day_trade_candidates",
        description="Rank same-day Alpaca day-trade candidates without placing orders.",
    )
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS), help="Watchlist symbols to rank")
    parser.add_argument("--top", type=int, default=3, help="Number of candidates to print")
    parser.add_argument("--feed", choices=["iex", "sip", "delayed_sip"], default="iex", help="Alpaca market data feed")
    parser.add_argument("--no-llm", action="store_true", help="Use deterministic scores only")
    parser.add_argument("--model", default="gpt-5.4-mini", help="OpenAI model for optional JSON rerank")
    parser.add_argument(
        "--report",
        default="reports/day_trade_candidates_latest.json",
        help="Path to write the JSON candidate report",
    )
    args = parser.parse_args()

    feed = {
        "iex": DataFeed.IEX,
        "sip": DataFeed.SIP,
        "delayed_sip": DataFeed.DELAYED_SIP,
    }[args.feed]
    top = max(int(args.top), 1)

    candidates = rank_candidates(args.symbols, feed=feed)
    if not candidates:
        raise SystemExit("No candidates had enough real Alpaca bars to rank.")

    llm_result = None
    if not args.no_llm:
        llm_result = _llm_rerank(candidates, top=top, model=args.model)

    _print_report(candidates, top=top, llm_result=llm_result)
    _write_report(Path(args.report), candidates=candidates, top=top, llm_result=llm_result)
    print(f"\nWrote report: {args.report}")


if __name__ == "__main__":
    main()
