"""Page-only human paper review; no model mutation, market fetch or orders."""
import re
from trading_desk.sol_live import OUTBOX


def review(payload):
    if not isinstance(payload,dict) or set(payload)!={'id','decision'}:
        raise ValueError('Only a proposal ID and paper-review decision are accepted')
    ident=payload['id'];decision=payload['decision']
    if not isinstance(ident,str) or not re.fullmatch(r'[0-9a-f]{24}',ident):
        raise ValueError('Choose an existing paper proposal')
    if decision not in ('approved','rejected'):raise ValueError('Choose approved or rejected for paper review')
    OUTBOX.decide(ident,decision)
    return dict(id=ident,decision=decision,recorded=True,fill_created=False,orders_enabled=False,
        effect='Paper review only; model positions and benchmark P/L unchanged')
