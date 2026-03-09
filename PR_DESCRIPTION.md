## Summary

Add edge alert notifications to the Synth Overlay extension. Users can watch markets and get browser notifications when the edge crosses their threshold — turning the overlay from a passive viewer into an active opportunity scanner.

Closes #17

## Demo Video

<!-- Replace with your video link after recording -->
📹 [Demo video](https://www.loom.com/share/394241ca1de84babab79e2224ed7ec02?t=87)

## Key Changes

| Component | Changes |
|-----------|---------|
| `extension/alerts.js` (new) | `SynthAlerts` module — watchlist CRUD, threshold validation, cooldown management, notification history, auto-dismiss setting, shared `chrome.storage.local` schema |
| `extension/background.js` | Alert polling engine using `chrome.alarms` (60s), immediate poll on tab switch, notification dispatch with 5-min cooldown, suppression logic, click-to-navigate handler, badge count, notification history persistence |
| `extension/sidepanel.js` | Alerts UI wiring — `renderWatchlist`, `updateWatchBtnState`, `renderHistory`, `initAlertsUI`, auto-dismiss toggle, live history updates via `chrome.storage.onChanged` |
| `extension/sidepanel.html` | Alerts card: toggle switch, threshold input, auto-dismiss toggle, watch button, watchlist display, recent alerts history panel with clear button |
| `extension/sidepanel.css` | Alert styles: toggle (+ small variant), threshold input, watch button, watchlist items, notification history panel |
| `extension/manifest.json` | Added `notifications`, `storage`, `alarms` permissions; version 1.3.0; registered all icon sizes with `default_icon` |
| `extension/icon{16,48,128}.png` (new) | Branded icon set with "S" lettermark at all Chrome-required sizes |
| `tests/test_alerts.py` (new) | 50 tests covering threshold, cooldown, watchlist, notification formatting, history CRUD, auto-dismiss, badge count, end-to-end pipeline |
| `README.md` | Documented alerts feature in How It Works section |

## Related Issues

Closes #17

## How It Works

1. User toggles **Alerts** on in the side panel and sets an edge threshold (default 3.0pp)
2. User clicks **+ Watch this market** to add the current market to the watchlist
3. **Badge count** appears on the extension icon showing number of watched markets
4. Background service worker polls all watched markets every 60 seconds via `chrome.alarms`
5. When user switches away from a Polymarket tab, an **immediate poll** is triggered — notification fires within seconds
6. When edge exceeds threshold → fires a browser notification with asset, edge size, signal direction, strength, and confidence
7. Clicking the notification focuses the existing Polymarket tab or opens a new one
8. **Notification history**: Last 10 alerts are saved and displayed in the side panel's "Recent Alerts" section, live-updating as new alerts fire
9. **Auto-dismiss toggle**: User can choose whether notifications stay until clicked (default) or auto-dismiss
10. **Suppression**: No notification fires if user is already viewing that market page
11. **Cooldown**: 5-minute cooldown per market prevents notification spam
12. **Persistence**: All state stored in `chrome.storage.local` — survives service worker restarts

## Edge Cases Handled

- `iconUrl` required for `chrome.notifications.create` on all platforms
- Duplicate notification suppression (checks if notification with same ID is already showing)
- Cooldown per market persisted in storage (survives MV3 service worker kills)
- Suppressed when user is already on the specific market page
- Watchlist capacity limit (20 markets max)
- Threshold validation and clamping (0.1–50 pp range)
- Graceful API error handling (server down, HTTP errors, missing data)
- Stale cooldown entry cleanup
- Watch button state updates after market data loads

## Type of Change

- [x] Improvement to existing tool
- [x] Documentation

## Testing

- [x] Tested against Synth API
- [x] Manually tested
- [x] Tests added/updated

```bash
python3 -m pytest tools/synth-overlay/tests/ -v  # 132 passed (82 existing + 50 new)
```

### Test Guide

#### 1. Start the server
```bash
cd tools/synth-overlay
python3 server.py
```
You should see `Running on http://127.0.0.1:8765`. Keep this terminal open.

#### 2. Load the extension
1. Open Chrome and go to `chrome://extensions/`
2. Turn on Developer mode (top right toggle)
3. Click Load unpacked
4. Select the `tools/synth-overlay/extension` folder

#### 3. Open a Polymarket page
Go to any supported market, for example:
```
https://polymarket.com/event/btc-updown-5m-1773049500
```
Click the Synth Panel extension icon to open the side panel. Edge data should load.

#### 4. Set up alerts
In the side panel (scroll down to the Alerts section):
1. Toggle Alerts **on**
2. Set Edge threshold to `0.5` (low value so notification fires easily)
3. Click **+ Watch this market**
4. Market appears in the watchlist

#### 5. Trigger a notification
1. Switch to a different tab (Google, new tab, anything not Polymarket)
2. A browser notification should appear within seconds
3. Shows: market name, edge data, signal direction, confidence, explanation

#### 6. Click the notification
- If Polymarket tab is open → it should focus that tab
- If closed → it should open a new tab to the market page

#### 7. Verify suppression
- Go back to the Polymarket page for the watched market
- Wait 60 seconds — no notification should fire (suppressed)

#### 8. Remove a market
- Click the **×** button next to the watched market in the side panel
- Market is removed from the watchlist

## Checklist

- [x] Code follows project style guidelines
- [x] Self-review completed
- [x] Changes are documented (if applicable)
