"""C5 Confluence Score model (0–100).

This is the existing C5 scoring model — it is NOT a new invention.

Positive components (max points):
    Setup trigger quality ............ 25
    Relative volume / RVOL ........... 20
    Location / VWAP-trend alignment .. 20
    Risk/reward acceptability ........ 15
    Catalyst presence and quality .... 12
    Market regime alignment .......... 8
    ----------------------------------- 100

Warnings (subtract from the score):
    Wide spread / illiquidity ........ -10
    Regime or sector against setup ... -10
    Elevated volatility / ATR% extreme -8
    Imminent event risk .............. -15   (critical)
    Low float / gap-risk profile ..... -8
    Delayed or stale data ............ -20   (critical; also removes the "live" label)

Score bands:   High 75–100 | Medium 55–74 | Low 0–54
Alert:         score >= 70 AND no critical warning

Every score surfaces: total, component breakdown, reasons, warnings, and the
label "Confluence Score — not history validated".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from . import indicators as ind
from .setup_detection import Setup

SCORE_LABEL = "Confluence Score — not history validated"

# Score bands.
BAND_HIGH = "High"
BAND_MEDIUM = "Medium"
BAND_LOW = "Low"

ALERT_THRESHOLD = 70

# Component maximums.
MAX_SETUP = 25
MAX_RVOL = 20
MAX_LOCATION = 20
MAX_RR = 15
MAX_CATALYST = 12
MAX_REGIME = 8

# Warning definitions: code -> (label, penalty, critical).
WARNING_DEFS = {
    "wide_spread": ("Wide spread / illiquidity", -10, False),
    "regime_against": ("Regime or sector against setup", -10, False),
    "atr_extreme": ("Elevated volatility / ATR% extreme", -8, False),
    "event_risk": ("Imminent event risk", -15, True),
    "low_float": ("Low float / gap-risk profile", -8, False),
    "stale_data": ("Delayed or stale data", -20, True),
}


@dataclass
class ScoreComponent:
    name: str
    score: float
    max_points: int
    detail: str = ""


@dataclass
class Warning_:
    code: str
    label: str
    penalty: int
    critical: bool
    detail: str = ""


@dataclass
class ConfluenceResult:
    total: int
    positive_subtotal: int
    components: List[ScoreComponent]
    warnings: List[Warning_]
    reasons: List[str]
    band: str
    is_live: bool
    alert: bool
    label: str = SCORE_LABEL

    @property
    def has_critical_warning(self) -> bool:
        return any(w.critical for w in self.warnings)

    def warnings_text(self) -> List[str]:
        return [f"{w.label} ({w.penalty})" for w in self.warnings]


@dataclass
class ScoreInputs:
    """Everything the scorer needs, bundled for clarity and testability."""

    setup: Setup
    candles: pd.DataFrame
    rvol: Optional[float] = None
    spread_pct: Optional[float] = None
    catalyst_quality: float = 0.0       # 0..1
    regime: str = "neutral"             # "with" | "against" | "neutral"
    atr_pct: Optional[float] = None
    quote_age: Optional[float] = None
    stale_after: float = 60.0
    feed_is_live: bool = True
    event_risk: bool = False
    low_float: bool = False
    # Spread above this %% of price is "wide".
    wide_spread_pct: float = 0.4
    # ATR%% above this is "extreme".
    atr_extreme_pct: float = 6.0


def _band(total: int) -> str:
    if total >= 75:
        return BAND_HIGH
    if total >= 55:
        return BAND_MEDIUM
    return BAND_LOW


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def score_confluence(inp: ScoreInputs) -> ConfluenceResult:
    components: List[ScoreComponent] = []
    reasons: List[str] = []
    setup = inp.setup
    df = inp.candles

    # 1) Setup trigger quality (25) --------------------------------------
    setup_score = round(_clamp(setup.trigger_quality) * MAX_SETUP, 1) if setup.detected else 0.0
    detail = f"{setup.kind} ({setup.direction})" if setup.detected else "no setup"
    components.append(ScoreComponent("Setup trigger quality", setup_score, MAX_SETUP, detail))
    if setup.detected and setup_score >= MAX_SETUP * 0.5:
        reasons.append(f"Qualified {setup.kind} setup detected ({setup.direction}).")
        reasons.extend(setup.notes)

    # 2) Relative volume / RVOL (20) -------------------------------------
    if inp.rvol is None:
        rvol_score = 0.0
        rvol_detail = "RVOL unavailable"
    else:
        rvol_score = round(_clamp(inp.rvol / 2.0) * MAX_RVOL, 1)
        rvol_detail = f"RVOL {inp.rvol:.2f}x"
        if inp.rvol >= 1.5:
            reasons.append(f"Relative volume elevated ({inp.rvol:.2f}x average).")
    components.append(ScoreComponent("Relative volume (RVOL)", rvol_score, MAX_RVOL, rvol_detail))

    # 3) Location / VWAP-trend alignment (20) ----------------------------
    loc_score, loc_detail, loc_reason = _location_score(df, setup)
    components.append(ScoreComponent("Location / VWAP alignment", loc_score, MAX_LOCATION, loc_detail))
    if loc_reason:
        reasons.append(loc_reason)

    # 4) Risk/reward acceptability (15) ----------------------------------
    rr = setup.rr
    if rr is None:
        rr_score = 0.0
        rr_detail = "R:R unavailable"
    else:
        rr_score = round(_clamp(rr / 2.0) * MAX_RR, 1)
        rr_detail = f"R:R {rr:.2f}"
        if rr >= 1.8:
            reasons.append(f"Favorable risk/reward ({rr:.2f}:1).")
    components.append(ScoreComponent("Risk/reward acceptability", rr_score, MAX_RR, rr_detail))

    # 5) Catalyst presence and quality (12) ------------------------------
    cat_score = round(_clamp(inp.catalyst_quality) * MAX_CATALYST, 1)
    components.append(
        ScoreComponent("Catalyst presence/quality", cat_score, MAX_CATALYST,
                       f"catalyst {inp.catalyst_quality:.2f}")
    )
    if inp.catalyst_quality >= 0.5:
        reasons.append("Supportive catalyst present.")

    # 6) Market regime alignment (8) -------------------------------------
    regime_map = {"with": 1.0, "neutral": 0.5, "against": 0.0}
    regime_score = round(regime_map.get(inp.regime, 0.5) * MAX_REGIME, 1)
    components.append(ScoreComponent("Market regime alignment", regime_score, MAX_REGIME, inp.regime))
    if inp.regime == "with":
        reasons.append("Broad market regime aligns with the setup.")

    positive_subtotal = round(sum(c.score for c in components))

    # --- Warnings -------------------------------------------------------
    warnings: List[Warning_] = []

    if inp.spread_pct is not None and inp.spread_pct > inp.wide_spread_pct:
        warnings.append(_mk("wide_spread", f"spread {inp.spread_pct:.2f}% of price"))

    if inp.regime == "against":
        warnings.append(_mk("regime_against", "market regime opposes the setup"))

    if inp.atr_pct is not None and inp.atr_pct > inp.atr_extreme_pct:
        warnings.append(_mk("atr_extreme", f"ATR {inp.atr_pct:.2f}% of price"))

    if inp.event_risk:
        warnings.append(_mk("event_risk", "imminent scheduled event"))

    if inp.low_float:
        warnings.append(_mk("low_float", "low float / gap-risk profile"))

    # Stale-data check: too old, or the feed itself reports not-live.
    is_stale = (inp.quote_age is not None and inp.quote_age > inp.stale_after) or (not inp.feed_is_live)
    if is_stale:
        age_txt = f"{inp.quote_age:.0f}s old" if inp.quote_age is not None else "feed not live"
        warnings.append(_mk("stale_data", age_txt))

    # is_live label is removed on stale data (per spec).
    is_live = inp.feed_is_live and not is_stale

    penalty = sum(w.penalty for w in warnings)
    total = int(max(0, min(100, positive_subtotal + penalty)))

    band = _band(total)
    has_critical = any(w.critical for w in warnings)
    alert = (total >= ALERT_THRESHOLD) and not has_critical

    return ConfluenceResult(
        total=total,
        positive_subtotal=positive_subtotal,
        components=components,
        warnings=warnings,
        reasons=reasons,
        band=band,
        is_live=is_live,
        alert=alert,
    )


def _mk(code: str, detail: str) -> Warning_:
    label, penalty, critical = WARNING_DEFS[code]
    return Warning_(code=code, label=label, penalty=penalty, critical=critical, detail=detail)


def _location_score(df: pd.DataFrame, setup: Setup):
    """Score price location vs VWAP and trend alignment (max 20)."""
    if df is None or len(df) < 5:
        return 0.0, "insufficient data", None

    price = float(df["close"].iloc[-1])
    vwap_series = ind.vwap(df)
    vwap_now = float(vwap_series.iloc[-1])
    slope_up = bool(vwap_series.iloc[-1] >= vwap_series.iloc[-5])

    above = price > vwap_now
    direction = setup.direction if setup.detected else "long"

    aligned = (direction == "long" and above) or (direction == "short" and not above)
    base = 12.0 if aligned else 4.0
    trend_bonus = 8.0 if ((direction == "long" and slope_up) or (direction == "short" and not slope_up)) else 0.0
    score = round(_clamp((base + trend_bonus) / MAX_LOCATION) * MAX_LOCATION, 1)

    side = "above" if above else "below"
    detail = f"price {side} VWAP, VWAP {'rising' if slope_up else 'falling'}"
    reason = None
    if aligned and trend_bonus:
        reason = f"Price {side} VWAP with VWAP trend supporting the {direction} setup."
    return score, detail, reason
