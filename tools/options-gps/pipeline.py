"""
Options GPS decision pipeline: forecast fusion, strategy generation,
payoff/probability engine, ranking, and guardrails.
Uses Synth get_prediction_percentiles, get_option_pricing, get_volatility.
"""

from dataclasses import dataclass
from typing import Literal

ViewBias = Literal["bullish", "bearish", "neutral"]
RiskLevel = Literal["low", "medium", "high"]
FusionState = Literal["aligned_bullish", "aligned_bearish", "countermove", "unclear"]


@dataclass
class StrategyCandidate:
    strategy_type: str
    direction: Literal["bullish", "bearish", "neutral"]
    description: str
    strikes: list[float]
    cost: float
    max_loss: float


@dataclass
class ScoredStrategy:
    strategy: StrategyCandidate
    probability_of_profit: float
    expected_value: float
    score: float
    rationale: str


def run_forecast_fusion(percentiles_1h: dict, percentiles_24h: dict, current_price: float) -> FusionState:
    """Classify market state from 1h and 24h forecast percentiles (last-step dict). Uses median vs current."""
    if not percentiles_1h or not percentiles_24h:
        return "unclear"
    p1h = percentiles_1h.get("0.5")
    p24h = percentiles_24h.get("0.5")
    if p1h is None or p24h is None:
        return "unclear"
    thresh = current_price * 0.002
    up_1h = p1h > current_price + thresh
    down_1h = p1h < current_price - thresh
    up_24h = p24h > current_price + thresh
    down_24h = p24h < current_price - thresh
    if up_1h and up_24h:
        return "aligned_bullish"
    if down_1h and down_24h:
        return "aligned_bearish"
    if (up_1h and down_24h) or (down_1h and up_24h):
        return "countermove"
    return "unclear"


def _parse_strikes(option_data: dict) -> list[float]:
    calls = option_data.get("call_options") or {}
    return sorted([float(k) for k in calls.keys()])


def generate_strategies(
    option_data: dict,
    view: ViewBias,
    risk: RiskLevel,
) -> list[StrategyCandidate]:
    """Build candidate strategies from option pricing and user view/risk."""
    current = float(option_data.get("current_price", 0))
    if current <= 0:
        return []
    strikes = _parse_strikes(option_data)
    if len(strikes) < 3:
        return []
    calls = {float(k): v for k, v in (option_data.get("call_options") or {}).items()}
    puts = {float(k): v for k, v in (option_data.get("put_options") or {}).items()}
    candidates: list[StrategyCandidate] = []
    atm = min(strikes, key=lambda s: abs(s - current))
    idx_atm = strikes.index(atm)
    otm_call = strikes[min(idx_atm + 2, len(strikes) - 1)] if idx_atm + 2 < len(strikes) else strikes[-1]
    otm_put = strikes[max(idx_atm - 2, 0)] if idx_atm >= 2 else strikes[0]
    if view == "bullish":
        if atm in calls:
            candidates.append(StrategyCandidate(
                "long_call", "bullish", "Long call (ATM)", [atm], float(calls[atm]), float(calls[atm])
            ))
        if otm_call in calls and otm_call != atm:
            candidates.append(StrategyCandidate(
                "long_call", "bullish", "Long call (OTM)", [otm_call], float(calls[otm_call]), float(calls[otm_call])
            ))
        if atm in calls and otm_call in calls:
            debit = float(calls[atm]) - float(calls[otm_call])
            if debit > 0:
                candidates.append(StrategyCandidate(
                    "call_debit_spread", "bullish", "Call debit spread", [atm, otm_call], debit, debit
                ))
    if view == "bearish":
        if atm in puts:
            candidates.append(StrategyCandidate(
                "long_put", "bearish", "Long put (ATM)", [atm], float(puts[atm]), float(puts[atm])
            ))
        if otm_put in puts and otm_put != atm:
            candidates.append(StrategyCandidate(
                "long_put", "bearish", "Long put (OTM)", [otm_put], float(puts[otm_put]), float(puts[otm_put])
            ))
        if atm in puts and otm_put in puts:
            debit = float(puts[atm]) - float(puts[otm_put])
            if debit > 0:
                candidates.append(StrategyCandidate(
                    "put_debit_spread", "bearish", "Put debit spread", [otm_put, atm], debit, debit
                ))
    if view == "neutral" or (view == "bullish" and risk == "low") or (view == "bearish" and risk == "low"):
        low_put = strikes[max(0, idx_atm - 3)]
        high_call = strikes[min(len(strikes) - 1, idx_atm + 3)]
        put_short = strikes[max(0, idx_atm - 1)]
        call_short = strikes[min(len(strikes) - 1, idx_atm + 1)]
        if low_put in puts and high_call in calls and put_short in puts and call_short in calls and low_put < current < high_call:
            credit_put = float(puts[put_short]) - float(puts[low_put])
            credit_call = float(calls[call_short]) - float(calls[high_call])
            credit = credit_put + credit_call
            if credit > 0:
                max_loss = (put_short - low_put) + (high_call - call_short) - credit
                candidates.append(StrategyCandidate(
                    "iron_condor", "neutral", "Iron condor (defined risk)", [put_short, call_short],
                    -credit, max_loss
                ))
    if not candidates and view == "neutral":
        if atm in calls:
            candidates.append(StrategyCandidate("long_call", "bullish", "Long call (ATM)", [atm], float(calls[atm]), float(calls[atm])))
        if atm in puts:
            candidates.append(StrategyCandidate("long_put", "bearish", "Long put (ATM)", [atm], float(puts[atm]), float(puts[atm])))
    return candidates


def _outcome_prices(percentiles_last: dict) -> list[float]:
    """Ordered outcome prices from percentile dict (e.g. 0.05, 0.2, ..., 0.95)."""
    keys = ["0.05", "0.2", "0.35", "0.5", "0.65", "0.8", "0.95"]
    out = []
    for k in keys:
        if k in percentiles_last:
            out.append(float(percentiles_last[k]))
    return out if out else [float(percentiles_last.get("0.5", 0))]


def _payoff_long_call(s: float, strike: float) -> float:
    return max(0.0, s - strike)


def _payoff_long_put(s: float, strike: float) -> float:
    return max(0.0, strike - s)


def _payoff_call_spread(s: float, k1: float, k2: float) -> float:
    return max(0.0, min(s - k1, k2 - k1))


def _payoff_put_spread(s: float, k1: float, k2: float) -> float:
    return max(0.0, min(k2 - s, k2 - k1))


def compute_payoff_metrics(
    strategy: StrategyCandidate,
    outcome_prices: list[float],
) -> tuple[float, float]:
    """Return (probability_of_profit, expected_value) for strategy under outcome distribution."""
    n = len(outcome_prices)
    if n == 0:
        return 0.0, 0.0
    cost = strategy.cost
    payoffs: list[float] = []
    for s in outcome_prices:
        if strategy.strategy_type == "long_call":
            payoffs.append(_payoff_long_call(s, strategy.strikes[0]))
        elif strategy.strategy_type == "long_put":
            payoffs.append(_payoff_long_put(s, strategy.strikes[0]))
        elif strategy.strategy_type == "call_debit_spread":
            payoffs.append(_payoff_call_spread(s, strategy.strikes[0], strategy.strikes[1]))
        elif strategy.strategy_type == "put_debit_spread":
            payoffs.append(_payoff_put_spread(s, strategy.strikes[0], strategy.strikes[1]))
        elif strategy.strategy_type == "iron_condor":
            k_put_short, k_call_short = strategy.strikes[0], strategy.strikes[1]
            p_put = max(0.0, k_put_short - s) if s < k_put_short else 0.0
            p_call = max(0.0, s - k_call_short) if s > k_call_short else 0.0
            credit = -strategy.cost
            payoffs.append(credit - (p_put + p_call))
        else:
            payoffs.append(0.0)
    ev = sum(payoffs) / n
    if strategy.strategy_type == "iron_condor":
        pop = sum(1 for x in payoffs if x > 0) / n
    else:
        pop = sum(1 for p in payoffs if p > cost) / n
    return pop, ev


def rank_strategies(
    candidates: list[StrategyCandidate],
    fusion_state: FusionState,
    view: ViewBias,
    outcome_prices: list[float],
    risk: RiskLevel,
) -> list[ScoredStrategy]:
    """Score and sort strategies. Returns list of ScoredStrategy sorted by score desc."""
    scored: list[ScoredStrategy] = []
    for c in candidates:
        pop, ev = compute_payoff_metrics(c, outcome_prices)
        fit = 0.0
        if fusion_state == "aligned_bullish" and c.direction == "bullish":
            fit = 1.0
        elif fusion_state == "aligned_bearish" and c.direction == "bearish":
            fit = 1.0
        elif fusion_state in ("countermove", "unclear") and c.direction == "neutral":
            fit = 0.5
        elif fusion_state in ("countermove", "unclear"):
            fit = 0.2
        elif fusion_state == "unclear" and view == "neutral":
            fit = 0.6
        w_pop = 0.4 if risk == "low" else (0.3 if risk == "medium" else 0.2)
        w_ev = 0.2 if risk == "low" else (0.3 if risk == "medium" else 0.4)
        score = fit * 0.4 + pop * w_pop + max(0, ev) * w_ev * 0.01
        tail_penalty = (1 - pop) * 0.1
        score -= tail_penalty
        rationale = f"Fit {fit:.0%}, PoP {pop:.0%}, EV ${ev:.0f}"
        scored.append(ScoredStrategy(strategy=c, probability_of_profit=pop, expected_value=ev, score=max(0, score), rationale=rationale))
    return sorted(scored, key=lambda x: -x.score)


def select_three_cards(scored: list[ScoredStrategy]) -> tuple[ScoredStrategy | None, ScoredStrategy | None, ScoredStrategy | None]:
    """Pick Best Match, Safer Alternative (higher PoP), Higher Upside (higher EV)."""
    if not scored:
        return None, None, None
    best = scored[0]
    safer = max(scored[1:] or [scored[0]], key=lambda x: x.probability_of_profit)
    upside = max(scored[1:] or [scored[0]], key=lambda x: x.expected_value)
    return best, safer, upside


def should_no_trade(fusion_state: FusionState, view: ViewBias, volatility_high: bool) -> bool:
    """Guardrail: no trade when confidence low or signals conflict."""
    if volatility_high:
        return True
    if fusion_state == "countermove" and view != "neutral":
        return True
    if fusion_state == "unclear" and view != "neutral":
        return True
    return False
