"""Shared measured range geometry; no fetching or invented observations."""
import math
from decimal import Decimal, ROUND_CEILING

def completed_swings(closes, support, resistance):
    """Count observed, non-overlapping full trips between the outer 20% zones.

    Adjacent closes in the same zone are one visit. Intrabar highs/lows cannot
    establish visit order, so only completed closes establish an alternating leg.
    Occasional overshoots still count as boundary visits; containment and the
    latest-close gate independently reject breaks and excessively unstable boxes.
    """
    width = resistance - support
    visits = []
    for close in closes:
        zone = ('support' if close <= support + .2 * width else
                'resistance' if close >= resistance - .2 * width else None)
        if zone and (not visits or visits[-1] != zone):
            visits.append(zone)
    return max(0, (len(visits) - 1) // 2), visits


def ratio(support, resistance):
    if not all(isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)
               for x in (support, resistance)) or not 0 < support < resistance:
        raise ValueError('support and resistance are unavailable or invalid')
    lo, hi = Decimal(str(support)), Decimal(str(resistance))
    raw = (hi - lo) / lo * 100
    return float(raw), int(raw.to_integral_value(rounding=ROUND_CEILING))

