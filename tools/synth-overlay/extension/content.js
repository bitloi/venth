(function () {
  "use strict";

  // Track last known prices to detect changes
  var lastPrices = { upPrice: null, downPrice: null };

  function slugFromPage() {
    var host = window.location.hostname || "";
    var path = window.location.pathname || "";
    var segments = path.split("/").filter(Boolean);

    if (host.indexOf("polymarket.com") !== -1) {
      var first = segments[0];
      var second = segments[1] || segments[0];
      if (first === "event" || first === "market") return second || null;
      return first || null;
    }

    return segments[segments.length - 1] || null;
  }

  /**
   * Scrape live Polymarket prices from the DOM.
   * Returns { upPrice: 0.XX, downPrice: 0.XX } or null if not found.
   */
  function scrapeLivePrices() {
    var upPrice = null;
    var downPrice = null;
    var bodyText = document.body ? document.body.innerText : "";
    
    // Strategy 1: Look for outcome elements with "Up/Down" and cent values
    var allElements = document.querySelectorAll("div, span, button, a, p");
    
    for (var i = 0; i < allElements.length; i++) {
      var el = allElements[i];
      var text = (el.innerText || el.textContent || "").trim();
      
      if (text.length > 50) continue;
      
      var upMatch = text.match(/\b(Up|Yes)\b[\s\n]*(\d{1,2})\s*[¢c¢]/i);
      var downMatch = text.match(/\b(Down|No)\b[\s\n]*(\d{1,2})\s*[¢c¢]/i);
      
      if (upMatch && upMatch[2] && upPrice === null) {
        upPrice = parseInt(upMatch[2], 10) / 100;
      }
      if (downMatch && downMatch[2] && downPrice === null) {
        downPrice = parseInt(downMatch[2], 10) / 100;
      }
      
      if (upPrice === null) {
        var upDecMatch = text.match(/\b(Up|Yes)\b[\s\n]*(0\.\d+)/i);
        if (upDecMatch && upDecMatch[2]) upPrice = parseFloat(upDecMatch[2]);
      }
      if (downPrice === null) {
        var downDecMatch = text.match(/\b(Down|No)\b[\s\n]*(0\.\d+)/i);
        if (downDecMatch && downDecMatch[2]) downPrice = parseFloat(downDecMatch[2]);
      }
      
      if (upPrice !== null && downPrice !== null) break;
    }

    // Strategy 2: Container-based search
    if (upPrice === null || downPrice === null) {
      var containers = document.querySelectorAll("[class*='market'], [class*='outcome'], [class*='option'], [class*='card']");
      for (var j = 0; j < containers.length; j++) {
        var container = containers[j];
        var containerText = (container.innerText || "").toLowerCase();
        var priceMatch = containerText.match(/(\d{1,2})\s*[¢c¢]/);
        if (!priceMatch) continue;
        var price = parseInt(priceMatch[1], 10) / 100;
        if ((containerText.indexOf("up") !== -1 || containerText.indexOf("yes") !== -1) && upPrice === null) {
          upPrice = price;
        } else if ((containerText.indexOf("down") !== -1 || containerText.indexOf("no") !== -1) && downPrice === null) {
          downPrice = price;
        }
      }
    }

    // Strategy 3: Full body text search
    if (upPrice === null || downPrice === null) {
      var upBodyMatch = bodyText.match(/\bUp\b[^\d]*?(\d{1,2})\s*[¢c¢]/i);
      var downBodyMatch = bodyText.match(/\bDown\b[^\d]*?(\d{1,2})\s*[¢c¢]/i);
      if (upBodyMatch && upBodyMatch[1] && upPrice === null) upPrice = parseInt(upBodyMatch[1], 10) / 100;
      if (downBodyMatch && downBodyMatch[1] && downPrice === null) downPrice = parseInt(downBodyMatch[1], 10) / 100;
    }

    if (upPrice !== null && downPrice !== null) {
      return { upPrice: upPrice, downPrice: downPrice };
    }
    if (upPrice !== null && downPrice === null) {
      return { upPrice: upPrice, downPrice: 1 - upPrice };
    }
    if (downPrice !== null && upPrice === null) {
      return { upPrice: 1 - downPrice, downPrice: downPrice };
    }
    return null;
  }

  function getContext() {
    var livePrices = scrapeLivePrices();
    return {
      slug: slugFromPage(),
      url: window.location.href,
      host: window.location.hostname,
      pageUpdatedAt: Date.now(),
      livePrices: livePrices,
    };
  }

  // Broadcast price update to extension
  function broadcastPriceUpdate(prices) {
    if (!prices) return;
    chrome.runtime.sendMessage({
      type: "synth:priceUpdate",
      prices: prices,
      slug: slugFromPage(),
      timestamp: Date.now()
    }).catch(function() {});
  }

  // Check if prices changed and broadcast if so
  function checkAndBroadcastPrices() {
    var prices = scrapeLivePrices();
    if (!prices) return;
    
    if (prices.upPrice !== lastPrices.upPrice || prices.downPrice !== lastPrices.downPrice) {
      lastPrices = { upPrice: prices.upPrice, downPrice: prices.downPrice };
      broadcastPriceUpdate(prices);
    }
  }

  // Set up MutationObserver for instant price detection
  var observer = new MutationObserver(function(mutations) {
    // Debounce: only check every 100ms max
    if (observer._pending) return;
    observer._pending = true;
    setTimeout(function() {
      observer._pending = false;
      checkAndBroadcastPrices();
    }, 100);
  });

  // Start observing DOM changes
  if (document.body) {
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }

  // Also poll every 500ms as backup for any missed mutations
  setInterval(checkAndBroadcastPrices, 500);

  // Initial broadcast
  setTimeout(checkAndBroadcastPrices, 500);

  // Handle requests from sidepanel
  chrome.runtime.onMessage.addListener(function (message, _sender, sendResponse) {
    if (!message || typeof message !== "object") return;
    if (message.type === "synth:getContext") {
      sendResponse({ ok: true, context: getContext() });
    }
  });
})();
