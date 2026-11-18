"""Refresh the measurable paper scan universe, never a brokerage order."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.pattern_universe import run

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
 r=run(a.apply)
 print(json.dumps({k:r[k] for k in ('session','universe_size','qualified','suggested_watchlist')},indent=2))
 print(json.dumps([{k:x[k] for k in ('symbol','kind','beta63','atr14','atr_pct','avg_dollar_volume_20','avg_shares_20','leverage_daily')} for x in r['rows'] if x['selected']],indent=2))
