"""Authorized same-thirty-day historical pattern transfer, independent of live."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.pattern_backtest import run
if __name__=='__main__':run()
