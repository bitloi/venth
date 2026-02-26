"""
Options GPS: Turn a trader's view into one clear options decision.
Uses Synth get_prediction_percentiles, get_option_pricing, get_volatility.
"""

import sys
import os
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from synth_client import SynthClient

from pipeline import (
    run_forecast_fusion,
    generate_strategies,
    rank_strategies,
    select_three_cards,
    should_no_trade,
)
from pipeline import _outcome_prices

SUPPORTED_ASSETS = ["BTC", "ETH", "SOL", "XAU", "SPY", "NVDA", "TSLA", "AAPL", "GOOGL"]


def load_synth_data(client: SynthClient, asset: str) -> tuple[dict, dict, dict, dict, float] | None:
    """Fetch percentiles 1h/24h, option pricing, volatility. Returns (p1h, p24h, options, vol, current_price) or None."""
    try:
        p1h = client.get_prediction_percentiles(asset, horizon="1h")
        p24h = client.get_prediction_percentiles(asset, horizon="24h")
        options = client.get_option_pricing(asset)
        vol = client.get_volatility(asset, horizon="24h")
    except Exception:
        return None
    percentiles_list_1h = (p1h.get("forecast_future") or {}).get("percentiles") or []
    percentiles_list_24h = (p24h.get("forecast_future") or {}).get("percentiles") or []
    if not percentiles_list_1h or not percentiles_list_24h:
        return None
    current = float((options.get("current_price") or p24h.get("current_price") or 0))
    if current <= 0:
        return None
    return (
        percentiles_list_1h[-1],
        percentiles_list_24h[-1],
        options,
        vol,
        current,
    )


def screen_view_setup() -> tuple[str, str, str]:
    """Screen 1: symbol, view, risk. Returns (symbol, view, risk)."""
    print("\n--- Screen 1: View Setup ---")
    print("Symbol:", ", ".join(SUPPORTED_ASSETS))
    symbol = input("Enter symbol [BTC]: ").strip().upper() or "BTC"
    if symbol not in SUPPORTED_ASSETS:
        symbol = "BTC"
    print("Market view: bullish | bearish | neutral")
    view = input("Enter view [bullish]: ").strip().lower() or "bullish"
    if view not in ("bullish", "bearish", "neutral"):
        view = "bullish"
    print("Risk tolerance: low | medium | high")
    risk = input("Enter risk [medium]: ").strip().lower() or "medium"
    if risk not in ("low", "medium", "high"):
        risk = "medium"
    level = "moderately " if view != "neutral" else ""
    print(f"\nYou are {level}{view} with {risk} risk.")
    return symbol, view, risk


def screen_top_plays(best, safer, upside, no_trade: bool):
    """Screen 2: Three strategy cards."""
    print("\n--- Screen 2: Top Plays ---")
    if no_trade:
        print("No trade — uncertainty high or signals conflict.")
        return
    for label, card in [("Best Match", best), ("Safer Alternative", safer), ("Higher Upside", upside)]:
        if card is None:
            continue
        s = card.strategy
        print(f"\n{label}: {s.description}")
        print(f"  Why: {card.rationale}")
        print(f"  Chance of profit: {card.probability_of_profit:.0%}")
        print(f"  Max loss: ${s.max_loss:,.0f}")
        print(f"  Review again at: expiry or if price moves >2% vs entry")


def screen_why_this_works(best, fusion_state: str, current_price: float, no_trade: bool):
    """Screen 3: Why best match works — distribution and explanation."""
    print("\n--- Screen 3: Why This Works ---")
    if no_trade or best is None:
        print("No recommendation; see guardrails.")
        return
    s = best.strategy
    print(f"Strategy: {s.description}")
    print(f"Synth 1h + 24h fusion state: {fusion_state}")
    print(f"Current price: ${current_price:,.2f}")
    print("Required market behavior: price moves in your favor by expiry (Synth distribution supports this view).")


def screen_if_wrong(best, no_trade: bool):
    """Screen 4: If wrong — exit and reassessment rules."""
    print("\n--- Screen 4: If Wrong ---")
    if no_trade or best is None:
        print("N/A")
        return
    print("Exit rule: close or hedge if price moves against you beyond max loss.")
    print("Reassess at: expiry, or 50% of time to expiry.")


def main():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        client = SynthClient()
    symbol, view, risk = screen_view_setup()
    data = load_synth_data(client, symbol)
    if data is None:
        print("Could not load Synth data for", symbol)
        return 1
    p1h_last, p24h_last, options, vol, current_price = data
    fusion_state = run_forecast_fusion(p1h_last, p24h_last, current_price)
    vol_future = (vol.get("forecast_future") or {}).get("average_volatility") or 0
    volatility_high = vol_future > 80 if symbol in ("BTC", "ETH", "SOL") else vol_future > 40
    no_trade = should_no_trade(fusion_state, view, volatility_high)
    candidates = generate_strategies(options, view, risk) if not no_trade else []
    outcome_prices = _outcome_prices(p24h_last)
    scored = rank_strategies(candidates, fusion_state, view, outcome_prices, risk) if candidates else []
    best, safer, upside = select_three_cards(scored)
    screen_top_plays(best, safer, upside, no_trade)
    screen_why_this_works(best, fusion_state, current_price, no_trade)
    screen_if_wrong(best, no_trade)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
