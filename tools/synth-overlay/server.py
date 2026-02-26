"""
Local API server for the Synth Overlay extension.
Serves edge data from SynthClient; extension calls this from Polymarket pages.
"""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, "../.."))
if _here not in sys.path:
    sys.path.insert(0, _here)

from flask import Flask, jsonify, request

from synth_client import SynthClient

from edge import edge_from_daily_or_hourly, edge_from_range_bracket
from matcher import get_market_type, normalize_slug

app = Flask(__name__)
_client: SynthClient | None = None


def get_client() -> SynthClient:
    global _client
    if _client is None:
        _client = SynthClient()
    return _client


@app.after_request
def cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/api/health", methods=["GET", "OPTIONS"])
def health():
    if request.method == "OPTIONS":
        return "", 204
    return jsonify({"status": "ok", "mock": get_client().mock_mode})


@app.route("/api/edge", methods=["GET", "OPTIONS"])
def edge():
    if request.method == "OPTIONS":
        return "", 204
    raw = request.args.get("slug") or request.args.get("url") or ""
    slug = normalize_slug(raw)
    if not slug:
        return jsonify({"error": "Missing or invalid slug/url"}), 400
    market_type = get_market_type(slug)
    if not market_type:
        return jsonify({"error": "Unsupported market", "slug": slug}), 404
    try:
        client = get_client()
        if market_type == "daily":
            data = client.get_polymarket_daily()
            edge_pct, signal, strength = edge_from_daily_or_hourly(data)
            return jsonify({
                "slug": data.get("slug"),
                "horizon": "24h",
                "edge_pct": edge_pct,
                "signal": signal,
                "strength": strength,
                "synth_probability_up": data.get("synth_probability_up"),
                "polymarket_probability_up": data.get("polymarket_probability_up"),
                "current_time": data.get("current_time"),
            })
        if market_type == "hourly":
            data = client.get_polymarket_hourly()
            edge_pct, signal, strength = edge_from_daily_or_hourly(data)
            return jsonify({
                "slug": data.get("slug"),
                "horizon": "1h",
                "edge_pct": edge_pct,
                "signal": signal,
                "strength": strength,
                "synth_probability_up": data.get("synth_probability_up"),
                "polymarket_probability_up": data.get("polymarket_probability_up"),
                "current_time": data.get("current_time"),
            })
        # range
        data = client.get_polymarket_range()
        if not isinstance(data, list):
            return jsonify({"error": "Invalid range data"}), 500
        bracket_title = request.args.get("bracket_title")
        brackets = [b for b in data if b.get("slug") == slug]
        if not brackets and data:
            brackets = [b for b in data if slug in (b.get("slug") or "")]
        if not brackets and data:
            brackets = data
        if not brackets:
            return jsonify({"error": "No brackets for slug", "slug": slug}), 404
        if bracket_title:
            matched = [b for b in brackets if (b.get("title") or "").strip() == bracket_title.strip()]
            if matched:
                brackets = matched
        first = brackets[0]
        edge_pct, signal, strength = edge_from_range_bracket(first)
        return jsonify({
            "slug": first.get("slug"),
            "horizon": "24h",
            "bracket_title": first.get("title"),
            "edge_pct": edge_pct,
            "signal": signal,
            "strength": strength,
            "synth_probability": first.get("synth_probability"),
            "polymarket_probability": first.get("polymarket_probability"),
            "current_time": first.get("current_time"),
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Server error", "detail": str(e)}), 500


def main():
    import warnings
    warnings.filterwarnings("ignore", message="No SYNTH_API_KEY")
    app.run(host="127.0.0.1", port=8765, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
