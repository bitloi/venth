"""Edge calculation: Synth vs Polymarket probability difference and signal classification."""

from typing import Literal

FAIR_THRESHOLD_PCT = 0.5
STRONG_EDGE_PCT = 3.0
MODERATE_EDGE_PCT = 1.0


def compute_edge_pct(synth_prob: float, market_prob: float) -> float:
    """YES-edge in percentage points: positive = Synth higher than market (underpriced YES)."""
    if not 0 <= synth_prob <= 1 or not 0 <= market_prob <= 1:
        raise ValueError("Probabilities must be in [0, 1]")
    return round((synth_prob - market_prob) * 100, 1)


def signal_from_edge(edge_pct: float, fair_threshold: float = FAIR_THRESHOLD_PCT) -> str:
    """Classify edge into underpriced / fair / overpriced (for YES)."""
    if edge_pct >= fair_threshold:
        return "underpriced"
    if edge_pct <= -fair_threshold:
        return "overpriced"
    return "fair"


def strength_from_edge(
    edge_pct: float,
    strong_threshold: float = STRONG_EDGE_PCT,
    moderate_threshold: float = MODERATE_EDGE_PCT,
) -> Literal["strong", "moderate", "none"]:
    """Classify edge strength for display (Strong / Moderate / No Edge)."""
    abs_edge = abs(edge_pct)
    if abs_edge >= strong_threshold:
        return "strong"
    if abs_edge >= moderate_threshold:
        return "moderate"
    return "none"


def edge_from_daily_or_hourly(data: dict) -> tuple[float, str, str]:
    """From up/down daily or hourly payload: (edge_pct, signal, strength)."""
    synth = data.get("synth_probability_up")
    market = data.get("polymarket_probability_up")
    if synth is None or market is None:
        raise ValueError("Missing synth_probability_up or polymarket_probability_up")
    edge_pct = compute_edge_pct(float(synth), float(market))
    return edge_pct, signal_from_edge(edge_pct), strength_from_edge(edge_pct)


def edge_from_range_bracket(bracket: dict) -> tuple[float, str, str]:
    """From one range bracket: (edge_pct, signal, strength)."""
    synth = bracket.get("synth_probability")
    market = bracket.get("polymarket_probability")
    if synth is None or market is None:
        raise ValueError("Missing synth_probability or polymarket_probability")
    edge_pct = compute_edge_pct(float(synth), float(market))
    return edge_pct, signal_from_edge(edge_pct), strength_from_edge(edge_pct)
