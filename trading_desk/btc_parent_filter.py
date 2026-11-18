"""Isolated sequential C parent-failure experiment; frozen engines untouched."""
from __future__ import annotations
import copy

from trading_desk.btc_data import iso
from trading_desk.btc_parent_hl import ContinuationBaselineReplay,ContinuationEarlyReplay
from scripts.audit_btc_c_blind_review import blind_case,classify

POLICY=dict(name='C_PARENT_FAILURE_ONLY_SEQUENTIAL_V1',
    decision='block C only when locked parent_flag is true and uncertainty is empty',
    uncertainty='retain all locked outside/gap/reclaim uncertainty; no manual #13 override',
    trigger_lowering='diagnostic only; never blocks an entry',
    scope='qualified C which would open after unchanged A/B priority; no held-position or exit-minute reentry',
    consumed='original first C crossing still consumes HL; rejected C does not consume A/B history as a fill',
    risk='inherit original entries, larger-D stops, target fractions, exits and costs',
    orders_enabled=False,live_promoted=False)


def blocks_parent(review):
    return bool(review['parent_flag'] and not review['uncertainty'])


class ParentFilterMixin:
    def __init__(self,*args,parent_filter_enabled=True,**kwargs):
        super().__init__(*args,**kwargs)
        self.parent_filter_enabled=parent_filter_enabled
        self.filter_minutes=[];self.filter_times=[];self.parent_filter_audits=[]

    def minute(self,b):
        # open_signal runs inside super.minute. Append only afterwards so the
        # classifier cannot observe entry-minute ranges or later prices.
        super().minute(b)
        self.filter_minutes.append(copy.deepcopy(b));self.filter_times.append(b['t'])

    def open_signal(self,b,s):
        if s['route']!='C':return super().open_signal(b,s)
        p=dict(entry_time=iso(b['t']),entry=s['entry_reference'],continuation=s['setup_evidence'])
        case=blind_case(p,self.filter_minutes,self.filter_times,'C-signal-'+str(s['id']))
        review=classify(case)
        block=self.parent_filter_enabled and blocks_parent(review)
        audit=dict(signal_id=s['id'],time_utc=iso(b['t']),entry_reference=s['entry_reference'],
            parent_flag=review['parent_flag'],uncertainty=review['uncertainty'],
            trigger_flag_ignored=review['trigger_flag'],category=review['category'],
            would_block=blocks_parent(review),blocked=block,filter_enabled=self.parent_filter_enabled,
            context=copy.deepcopy(s['setup_evidence']),failed_parent_chain=review['failed_parent_chain'],
            prefix_last_minute=review['evidence']['last_structure_minute'],
            prefix_sha256=review['evidence']['source_prefix_sha256'],input_sha256=review['input_sha256'],
            trade_id=None)
        self.parent_filter_audits.append(audit)
        s['parent_filter']=copy.deepcopy(audit)
        if block:
            # ContinuationMixin.scan already consumed the first-crossing HL.
            # No fill means no position ID, no A/B reset and no new floor.
            s['decision']='parent_filter_rejected';s['trade_id']=None
            self.counter['rejected']+=1;self.counter['parent_filter_rejected']+=1
            self.event('parent_filter_rejected',b['t'],signal_id=s['id'],entry_rule='C',
                price=s['entry_reference'],reason=POLICY['decision'],
                parent_failure=copy.deepcopy(review['failed_parent_chain']))
            return
        super().open_signal(b,s)
        audit['trade_id']=s['trade_id'];s['parent_filter']['trade_id']=s['trade_id']

    def finish(self):
        r=super().finish();r['parent_filter_policy']=copy.deepcopy(POLICY)
        r['parent_filter_enabled']=self.parent_filter_enabled
        r['parent_filter_audits']=copy.deepcopy(self.parent_filter_audits)
        return r


class ParentFilteredBaselineReplay(ParentFilterMixin,ContinuationBaselineReplay):
    pass


class ParentFilteredEarlyReplay(ParentFilterMixin,ContinuationEarlyReplay):
    pass
