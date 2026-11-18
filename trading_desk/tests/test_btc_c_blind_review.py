"""Read-only real-case checks for the locked diagnostic, not trading rules."""
import copy
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts
from scripts.audit_btc_c_blind_review import classify,OUT,locked


@pytest.fixture(scope='module')
def controls():
    p=ROOT/'reports/btc_parent_hl_loss_audit_2026_11_09/AUDIT.json'
    if not p.exists():pytest.skip('Requires the explicitly authorized local archived case audit')
    a=read(p);out={}
    for x in [a['cases'][0],a['cases'][-1],a['benchmark']]:
        context=copy.deepcopy(x['context'])
        out[x['label']]=dict(label=x['label'],entry_time=x['entry_time'],context=context,
            signal=dict(entry_reference=(x.get('record') or {}).get('entry') or x['signal']['entry_reference']),
            minutes=[b for b in x['minutes'] if b['t']<ts(x['entry_time'])])
    return out,a


def test_prior_controls_keep_same_causal_difference_without_rejecting_normal_pullback(controls):
    rows,_=controls
    a=classify(rows['baseline-C-13']);b=classify(rows['Nov09-0317-prefix']);c=classify(rows['baseline-C-90'])
    assert a['parent_flag'] and a['trigger_flag']
    # The locked conservative confidence policy sends historical outside-turn
    # contexts for manual review; it does not erase their positive evidence.
    assert a['category']=='evidence_insufficient' and not a['screen_candidate']
    assert b['category']=='parent_support_retest_probe' and not b['screen_candidate']
    assert c['category']=='normal_continuation_candidate' and not c['screen_candidate']
    assert not c['evidence']['selected_peak_has_hourly_confirmation']


def test_missing_real_minute_remains_unknown_and_is_never_a_screen_pass(controls):
    rows,_=controls;case=copy.deepcopy(rows['baseline-C-13'])
    case['minutes'].pop(len(case['minutes'])//2)
    review=classify(case)
    assert review['missing_minutes']==1
    assert review['category']=='evidence_insufficient' and not review['screen_candidate']


def test_actual_post_entry_observation_and_outcome_fields_are_rejected(controls):
    rows,a=controls;case=copy.deepcopy(rows['baseline-C-90'])
    post=next(b for b in a['cases'][0]['minutes'] if b['t']==ts(case['entry_time']))
    case['minutes'].append(post)
    with pytest.raises(AssertionError,match='future'):classify(case)
    case=copy.deepcopy(rows['baseline-C-90']);case['net']=100
    with pytest.raises(AssertionError,match='Outcome'):classify(case)


def test_saved_twenty_labels_match_frozen_outcome_free_inputs():
    if not (OUT/'CLASSIFICATIONS.json').exists():pytest.skip('Requires the authorized local twenty-case review')
    locked();saved=read(OUT/'CLASSIFICATIONS.json')
    for case in read(OUT/'BLIND_CASES.json'):
        assert classify(case)==saved[case['label']]
