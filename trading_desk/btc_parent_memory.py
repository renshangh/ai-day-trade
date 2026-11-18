"""Independent PH5 lifecycle comparison; no edits to frozen or PH5 controls."""
from __future__ import annotations

import copy

from trading_desk.btc_data import iso
from trading_desk.btc_parent_five import (
    PH5_RULE, ParentFiveDetector, ParentFiveMixin, ParentFiveBaseline, ParentFiveEarly,
)

MEMORY_RULE = dict(copy.deepcopy(PH5_RULE), version='research-memory-1',
    name='PH5_RETAIN_PARENT_CONSUME_ENTRY_EPISODE',
    only_change='Separate still-valid parent context from consumed D/HL entry episodes; no new thresholds.',
    consumption='First crossing still consumes each D/HL token, including warmup/held/rejected. Every actual A/B or PH5 entry advances the actionable-HL floor to the next full 15m candle, without deleting parent D, confirmed peaks or observed turn context.',
    parent_lifetime='Same parent selection and invalidation as PH5; retained D is invalidated at/below D, or context clears on an observation gap. No added expiry, tuning or parent replacement by a higher internal low.',
    hl_reentry='Latest confirmed intact HL must begin at/after the most recent entry floor and have an unconsumed D/HL token. It need not exceed the previous traded HL; original comparison-to-parent-D tolerance remains unchanged.')


class RetainedParentDetector(ParentFiveDetector):
    def __init__(self):
        self.action_floor = None
        super().__init__()

    def reset(self, floor=None):
        # Existing minute/aggregate gap paths call reset. Unknown prices still
        # erase the background; keeping memory never bridges absent observations.
        old_floor = self.action_floor
        super().reset(None)
        self.action_floor = max(x for x in (old_floor, floor) if x is not None) if (
            old_floor is not None or floor is not None) else None

    def consume_entry(self, floor):
        self.action_floor = floor

    def ready(self, atr):
        setup = super().ready(atr)
        if setup and self.action_floor is not None and setup['hl']['bar_time'] < self.action_floor:
            return None
        return setup


class RetainedParentMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ph5 = RetainedParentDetector()

    def open_signal(self, b, s):
        # Invoke the SAME inherited position/exit initialization that PH5 calls,
        # skipping only ParentFiveMixin's unconditional parent.reset(). Frozen
        # A/B consumed-entry history and all exit/risk initialization still run.
        super(ParentFiveMixin, self).open_signal(b, s)
        self.ph5.consume_entry(self.entry_history_start)
        if self.position and s['route'] == 'PH5':
            self.position['parent_five'] = dict(setup=copy.deepcopy(s['setup_evidence']),
                hold=copy.deepcopy(s['hold_bar']), trigger_known_no_earlier_than=s['interval_end'])
        p = self.ph5.parent
        self.event('ph5_parent_context_retained', b['t'], trade_id=self.position_id,
            parent_price=p['price'] if p else None, parent_time=iso(p['time']) if p else None,
            parent_intact=bool(p and not p['broken']),
            fresh_actionable_HL_from=iso(self.ph5.action_floor),
            reason='Consumed entry opportunity; retained observed parent background. No order.')

    def complete(self):
        had = bool(self.minutes)
        super().complete()
        if had and self.ph5_trace_enabled and self.ph5_trace:
            self.ph5_trace[-1]['action_floor'] = self.ph5.action_floor

    def finish(self):
        result = super().finish()
        result['ph5_rule'] = copy.deepcopy(MEMORY_RULE)
        result['parent_memory_comparison'] = True
        return result


class ParentMemoryBaseline(RetainedParentMixin, ParentFiveBaseline):
    pass


class ParentMemoryEarly(RetainedParentMixin, ParentFiveEarly):
    pass
