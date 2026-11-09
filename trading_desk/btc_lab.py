"""Local BTC research views and explicitly started, read-only background jobs."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import date, datetime
from zoneinfo import ZoneInfo

from trading_desk import btc_data, btc_engine

APPROVED_CASES=btc_data.ROOT/'reports/btc_structure_2026_11_08/entry_examples/oct12_direction_filtered_exits/REVIEW.json'
STRUCTURE_CASE=btc_data.ROOT/'reports/btc_structure_2026_11_08/entry_examples/oct12_structure_exit/REVIEW.json'
GIVEBACK_STUDY=btc_data.ROOT/'reports/btc_structure_2026_11_08/entry_examples/oct12_giveback_comparison/REVIEW.json'
PROFIT_GUARD_CASES=btc_data.ROOT/'reports/btc_structure_2026_11_08/entry_examples/oct12_approved_profit_guard/REVIEW.json'
TURNING_CASES=btc_data.ROOT/'reports/btc_structure_2026_11_08/entry_examples/oct12_approved_turning_exit/REVIEW.json'

class Lab:
    def __init__(self, store=btc_data.STORE):
        self.store = store
        self.lock = threading.Lock()
        self.job = {'status': 'idle'}
        self.cache = {}
        self.quality_cache = (None, {'count': 0})

    def result(self, run_id):
        if not isinstance(run_id, str) or not re.fullmatch(r'\d{8}T\d{6}Z?-?(?:30|90|365|all)(?:-ab)?', run_id):
            raise ValueError('Invalid research run identifier')
        path = self.store / 'runs' / run_id / 'result.json'
        if not path.exists():
            raise ValueError('Research run not found or still running')
        stamp = path.stat().st_mtime_ns
        if run_id not in self.cache or self.cache[run_id][0] != stamp:
            self.cache[run_id] = (stamp, btc_data.read(path))
        return self.cache[run_id][1]

    def releases(self):
        return btc_data.read(self.store/'releases'/'INDEX.json',{})

    def release_for(self,run_id):
        return next((r for r in self.releases().values() if r.get('run_id')==run_id),None)

    def review_release(self):
        current=btc_data.read(self.store/'releases/CURRENT_REVIEW.json',{})
        return self.releases().get(current.get('version'))

    def active_release(self):
        active=btc_data.read(self.store/'releases'/'ACTIVE.json',{})
        release=self.releases().get(active.get('version'))
        return release if release and (self.store/'runs'/release['run_id']/'result.json').is_file() else None

    def current_study(self):
        active=btc_data.read(self.store/'studies/ACTIVE.json',{})
        ident=active.get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-E1-E2-sequential',ident):return None
        return btc_data.read(self.store/'studies'/ident/'STUDY.json',None)

    def status(self):
        db = self.store / 'minutes.sqlite'
        wal = self.store / 'minutes.sqlite-wal'
        stamp = tuple((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None for p in (db, wal))
        if stamp != self.quality_cache[0]:
            self.quality_cache = (stamp, btc_data.quality(self.store))
        study=self.current_study()
        visible=set(study['run_ids'].values()) if study else None
        runs = []
        for path in sorted((self.store / 'runs').glob('*/result.json'), reverse=True):
            if visible is not None and path.parent.name not in visible:continue
            result = self.result(path.parent.name)
            if result['status'] != 'complete':
                continue
            runs.append({k: result.get(k) for k in ('run_id', 'status', 'days', 'start', 'end', 'metrics',
                'gap_free_metrics', 'gap_exposed_trades', 'partial_context_trades', 'strategy_version', 'expanded_b', 'exit_policy', 'b1_independent_hold', 'sequential_exit_policy')})
            runs[-1]['release']=self.release_for(result['run_id'])
        with self.lock:
            job = dict(self.job)
        return dict(archive=self.quality_cache[1], runs=runs,current_study=study,review_release=self.review_release(),
            latest=btc_data.read(self.store / 'latest_run.json', {}), job=job,
            active_release=self.active_release(),default_run=self.active_release()['run_id'] if self.active_release() else None,
            downloads={k: {field: value for field, value in btc_data.read(self.store / f'sync_{k}.json', {}).items()
                if field in ('status', 'pages', 'last_observed', 'updated_at')} for k in ('recent', 'all')},
            releases=self.releases(),read_only=True, orders_enabled=False)

    def detail(self, run_id, day=None, trade_id=None):
        result = self.result(run_id)
        if day is None:
            day = datetime.fromisoformat(result['end'].replace('Z', '+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat()
        if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
            raise ValueError('Use YYYY-MM-DD for the New York date')
        date.fromisoformat(day)
        if trade_id is not None:
            try:
                trade_id = int(trade_id)
            except (ValueError, TypeError):
                raise ValueError('Invalid trade identifier') from None
        ledger = self.store / 'runs' / run_id / 'ledger.sqlite'
        with sqlite3.connect(ledger.as_uri() + '?mode=ro', uri=True) as db:
            rows = [json.loads(x[0]) for x in db.execute('SELECT body FROM ledger WHERE day=? ORDER BY t LIMIT 101', (day,))]
        ny = ZoneInfo('America/New_York')
        def local_day(value):
            return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(ny).date().isoformat()
        trades = [p for p in result['trades'] if p['id'] == trade_id or
            (local_day(p['entry_time']) <= day and (p['status'] == 'open' or local_day(p['exit_time']) >= day))]
        files=[name for name in ('BTC_STRUCTURE_RELEASE_0.1.zip','B1_CONFIRMATION_REVIEW.csv','RESEARCH.xlsx','LARGE_LOSS_REVIEW.csv','LOSS_REVIEW.csv','SIGNALS.csv','TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv')
            if (self.store/'runs'/run_id/name).is_file()]
        if self.release_for(run_id) and self.release_for(run_id)['version']=='0.1' and (self.store/'investigations/E1_E2_FIXED38.xlsx').is_file():
            files.append('E1_E2_FIXED38.xlsx')
        study=self.current_study()
        selected_study=study if study and run_id in study['run_ids'].values() else None
        if selected_study:
            files=[name for name in ('SIGNALS.csv','TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv') if (self.store/'runs'/run_id/name).is_file()]
            if (self.store/'studies'/study['study_id']/'E1_E2_SEQUENTIAL_30D.xlsx').is_file():files.insert(0,'E1_E2_SEQUENTIAL_30D.xlsx')
            review=self.review_release()
            if review and (self.store/'releases'/review['version']/review['archive']).is_file():
                files.append(review['archive'])
        run={k: v for k, v in result.items() if k not in ('trades', 'gaps','signals')}
        run['closed_net']=sum(p['net'] for p in result['trades'] if p['status']=='closed')
        run['realized_leg_net']=sum(l['net'] for p in result['trades'] for l in p['legs'])
        return dict(run=run,release=self.release_for(run_id),current_study=selected_study,review_release=self.review_release(),
            early_failure_fixed38=(btc_data.read(self.store/'investigations'/'RELEASE_0_1_E1_E2_FIXED38.json',None) if self.release_for(run_id) and self.release_for(run_id)['version']=='0.1' else None),
            early_failure_review=(btc_data.read(self.store/'investigations'/'RELEASE_0_1_EARLY_FAILURE.json',None) if self.release_for(run_id) and self.release_for(run_id)['version']=='0.1' else None),
            pullback_review=(btc_data.read(self.store/'investigations'/'RELEASE_0_1_PULLBACK_CASES.json',None) if self.release_for(run_id) and self.release_for(run_id)['version']=='0.1' else None),
            performance_review=(btc_data.read(self.store/'investigations'/'RELEASE_0_1_PERFORMANCE.json',None) if self.release_for(run_id) and self.release_for(run_id)['version']=='0.1' else None),
            b1_confirmation_review=btc_data.read(self.store/'runs'/run_id/'B1_CONFIRMATION_REVIEW.json',None),
            day=day, rows=rows, trades=trades,signals=result.get('signals',[]),exports=files,
            comparison=None if selected_study else btc_data.read(self.store/'runs'/run_id/'COMPARISON.json',None),
            entry_audit=btc_data.read(self.store/'runs'/run_id/'ENTRY_AUDIT.json',None),
            loss_review=btc_data.read(self.store/'runs'/run_id/'LOSS_REVIEW.json',None),
            large_loss_review=btc_data.read(self.store/'runs'/run_id/'LARGE_LOSS_REVIEW.json',None),
            trade_index=[dict(id=p['id'], entry_time=p['entry_time'], entry=p['entry'], status=p['status'],
                entry_rule=p.get('entry_rule','legacy'),signal_id=p.get('signal_id'),
                net_r=p.get('net_r'), gap_exposed=p['gap_exposed'], context_partial=p['context_partial']) for p in result['trades']])

    def export(self,run_id,name):
        self.result(run_id)
        if name=='BTC_STRUCTURE_RELEASE_0.2.zip':
            study=self.current_study();release=self.review_release()
            if not study or run_id not in study['run_ids'].values() or not release or release['version']!='0.2':
                raise ValueError('Current review release unavailable')
            target=self.store/'releases/0.2'/name
            if not target.is_file():raise ValueError('Release archive unavailable')
            return target
        if name=='E1_E2_SEQUENTIAL_30D.xlsx':
            study=self.current_study()
            if not study or run_id not in study['run_ids'].values():raise ValueError('Current study export unavailable')
            target=self.store/'studies'/study['study_id']/name
            if not target.is_file():raise ValueError('Current workbook not ready')
            return target
        if name=='E1_E2_FIXED38.xlsx':
            release=self.release_for(run_id)
            target=self.store/'investigations/E1_E2_FIXED38.xlsx'
            if not release or release['version']!='0.1' or not target.is_file():raise ValueError('Fixed-entry comparison not available')
            return target
        if name not in ('BTC_STRUCTURE_RELEASE_0.1.zip','B1_CONFIRMATION_REVIEW.csv','RESEARCH.xlsx','LARGE_LOSS_REVIEW.csv','LOSS_REVIEW.csv','SIGNALS.csv','TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv'):
            raise ValueError('Unknown research export')
        path=self.store/'runs'/run_id/name
        if not path.is_file():
            raise ValueError('Research export not available')
        return path

    def approved_cases(self):
        # This GET view reads saved two-case results only; it must never replay
        # or replace the latest monthly study while the user opens the page.
        if not APPROVED_CASES.is_file():
            return dict(available=False,cases=[],read_only=True,orders_enabled=False)
        result=btc_data.read(APPROVED_CASES)
        return dict(available=True,policy=result['policy'],cases=result['cases'],
            costs=result['costs'],month_rerun=False,read_only=True,orders_enabled=False)

    def structure_case(self):
        # A saved single-case review is not a new monthly run or a live trade.
        if not STRUCTURE_CASE.is_file():
            return dict(available=False,read_only=True,orders_enabled=False)
        return dict(available=True,review=btc_data.read(STRUCTURE_CASE),
            giveback_study=btc_data.read(GIVEBACK_STUDY) if GIVEBACK_STUDY.is_file() else None,
            approved_guard=btc_data.read(PROFIT_GUARD_CASES) if PROFIT_GUARD_CASES.is_file() else None,
            current_exit_review=btc_data.read(TURNING_CASES) if TURNING_CASES.is_file() else None,
            read_only=True,orders_enabled=False)

    def start(self, operation, days=30):
        if operation not in ('sync_recent', 'sync_all', 'backtest'):
            raise ValueError('Choose sync_recent, sync_all or backtest')
        if isinstance(days, bool) or days not in (30, 90, 365, 'all'):
            raise ValueError('Choose 30, 90, 365 or all')
        with self.lock:
            if self.job['status'] == 'running':
                return dict(self.job)
            self.job = dict(status='running', operation=operation, days=days)
        def progress(value):
            # Pagination tokens stay on disk; the page only sees progress.
            safe = {k: v for k, v in value.items() if k in ('processed', 'time', 'run_id', 'pages', 'last_observed')}
            with self.lock:
                self.job.update(safe)
        def work():
            try:
                if operation == 'backtest':
                    result = btc_engine.run(days, self.store, progress,research_policy='release_0_1')
                    final = dict(status='complete', run_id=result['run_id'], processed=result['minute_count'], time=result['last_observed'])
                else:
                    result = btc_data.sync(operation.removeprefix('sync_'), self.store, progress)
                    final = dict(status=result['status'])
            except (Exception, SystemExit) as exc:
                # Never return exception text from a credential/provider helper.
                final = dict(status='error', error=f'{type(exc).__name__}: research job stopped; check paper credentials, source availability or archive conflicts locally. No order attempted.')
            with self.lock:
                self.job.update(final)
        threading.Thread(target=work, daemon=True, name='btc-research').start()
        with self.lock:
            return dict(self.job)


LAB = Lab()
