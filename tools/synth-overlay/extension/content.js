(function () {
  "use strict";

  function slugFromPage() {
    var host = window.location.hostname || "";
    var path = window.location.pathname || "";
    var segments = path.split("/").filter(Boolean);

    // Polymarket: /event/<slug> or /market/<slug> or /<slug>
    if (host.indexOf("polymarket.com") !== -1) {
      var first = segments[0];
      var second = segments[1] || segments[0];
      if (first === "event" || first === "market") return second || null;
      return first || null;
    }

    // Generic fallback: use the last meaningful path segment
    return segments[segments.length - 1] || null;
  }

  /**
   * Scrape live Polymarket prices from the DOM.
   * Polymarket uses React with dynamic rendering - prices appear in various formats.
   * Returns { upPrice: 0.XX, downPrice: 0.XX } or null if not found.
   */
  function scrapeLivePrices() {
    var upPrice = null;
    var downPrice = null;

    // Get all text content from the page body
    var bodyText = document.body ? document.body.innerText : "";
    
    // Strategy 1: Look for outcome cards/sections containing "Up" or "Down" with prices
    // Polymarket shows prices like "Up\n52¢" or "Down\n48¢" in card layouts
    var allElements = document.querySelectorAll("div, span, button, a, p");
    
    for (var i = 0; i < allElements.length; i++) {
      var el = allElements[i];
      var text = (el.innerText || el.textContent || "").trim();
      
      // Skip very long text blocks (we want small outcome elements)
      if (text.length > 50) continue;
      
      // Match patterns: "Up 52¢", "Up\n52¢", "Up52¢", "Up 0.52"
      var upMatch = text.match(/\b(Up|Yes)\b[\s\n]*(\d{1,2})\s*[¢c¢]/i);
      var downMatch = text.match(/\b(Down|No)\b[\s\n]*(\d{1,2})\s*[¢c¢]/i);
      
      if (upMatch && upMatch[2] && upPrice === null) {
        upPrice = parseInt(upMatch[2], 10) / 100;
      }
      if (downMatch && downMatch[2] && downPrice === null) {
        downPrice = parseInt(downMatch[2], 10) / 100;
      }
      
      // Also try decimal format: "Up 0.52" or "Yes 0.48"
      if (upPrice === null) {
        var upDecMatch = text.match(/\b(Up|Yes)\b[\s\n]*(0\.\d+)/i);
        if (upDecMatch && upDecMatch[2]) {
          upPrice = parseFloat(upDecMatch[2]);
        }
      }
      if (downPrice === null) {
        var downDecMatch = text.match(/\b(Down|No)\b[\s\n]*(0\.\d+)/i);
        if (downDecMatch && downDecMatch[2]) {
          downPrice = parseFloat(downDecMatch[2]);
        }
      }
      
      if (upPrice !== null && downPrice !== null) break;
    }

    // Strategy 2: Look for adjacent elements (label + price in sibling/child)
    if (upPrice === null || downPrice === null) {
      var containers = document.querySelectorAll("[class*='market'], [class*='outcome'], [class*='option'], [class*='card']");
      for (var j = 0; j < containers.length; j++) {
        var container = containers[j];
        var containerText = (container.innerText || "").toLowerCase();
        
        // Find price pattern anywhere in container
        var priceMatch = containerText.match(/(\d{1,2})\s*[¢c¢]/);
        if (!priceMatch) continue;
        
        var price = parseInt(priceMatch[1], 10) / 100;
        
        // Determine if this is Up or Down based on text
        if ((containerText.indexOf("up") !== -1 || containerText.indexOf("yes") !== -1) && upPrice === null) {
          upPrice = price;
        } else if ((containerText.indexOf("down") !== -1 || containerText.indexOf("no") !== -1) && downPrice === null) {
          downPrice = price;
        }
      }
    }

    // Strategy 3: Search entire page for the pattern
    if (upPrice === null || downPrice === null) {
      // Look for "Up" followed by cents anywhere in body
      var upBodyMatch = bodyText.match(/\bUp\b[^\d]*?(\d{1,2})\s*[¢c¢]/i);
      var downBodyMatch = bodyText.match(/\bDown\b[^\d]*?(\d{1,2})\s*[¢c¢]/i);
      
      if (upBodyMatch && upBodyMatch[1] && upPrice === null) {
        upPrice = parseInt(upBodyMatch[1], 10) / 100;
      }
      if (downBodyMatch && downBodyMatch[1] && downPrice === null) {
        downPrice = parseInt(downBodyMatch[1], 10) / 100;
      }
    }

    // Log for debugging (visible in browser console)
    console.log("[Synth-Overlay] DOM scrape result:", { upPrice: upPrice, downPrice: downPrice });

    if (upPrice !== null && downPrice !== null) {
      return { upPrice: upPrice, downPrice: downPrice };
    }
    
    // Fallback: if we only have one, derive the other (prices should sum to ~1)
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

  chrome.runtime.onMessage.addListener(function (message, _sender, sendResponse) {
    if (!message || typeof message !== "object") return;
    if (message.type === "synth:getContext") {
      sendResponse({ ok: true, context: getContext() });
    }
  });
})();
