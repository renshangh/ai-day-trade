"""Isolated frozen-0.2 SOL/USD and ETH/USD historical comparison."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.crypto_transfer import run
if __name__=='__main__':run()
