"""Independent market-data-only discovery worker; no brokerage order client."""
from pathlib import Path
import argparse,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.pattern_discovery import Agent,snapshot
from trading_desk.pattern_library import HOME,create_library
from trading_desk.btc_data import save,iso

def main():
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--once',action='store_true')
    p.add_argument('--library',action='store_true');p.add_argument('--status',action='store_true');a=p.parse_args()
    if a.library:
        library=create_library();print(json.dumps(dict(winners=len(library['examples']),losers=len(library['counterexamples']))));return
    if a.status:
        s=snapshot();print(json.dumps({k:v for k,v in s.items() if k not in ('library','symbols')},indent=2));return
    if not(a.worker or a.once):p.error('Use --library, --status, --once or --worker')
    # A lifetime lock prevents an older in-memory engine overwriting a newer
    # process's results between polling cycles.
    import fcntl
    HOME.mkdir(parents=True,exist_ok=True)
    with (HOME/'PROCESS.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('Discovery worker already running')
        agent=Agent()
        try:
            while True:
                try:agent.cycle()
                except Exception as e:
                    save(HOME/'ERROR.json',dict(at=iso(time.time()),error=str(e) if isinstance(e,ValueError) else type(e).__name__,pid=os.getpid()))
                    raise
                if a.once:break
                time.sleep(60)
        finally:agent.close()

if __name__=='__main__':main()
