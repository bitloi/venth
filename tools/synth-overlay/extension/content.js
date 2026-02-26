(function () {
  "use strict";

  const API_BASE = "http://127.0.0.1:8765";

  function slugFromPage() {
    const path = window.location.pathname || "";
    const segments = path.split("/").filter(Boolean);
    const eventOrMarket = segments[0];
    const slug = segments[1] || segments[0];
    if (eventOrMarket === "event" || eventOrMarket === "market") {
      return slug || null;
    }
    return segments[0] || null;
  }

  function createBadge(data) {
    const edge = data.edge_pct;
    const signal = data.signal;
    const strength = data.strength;
    const label =
      signal === "fair"
        ? `Fair ${edge >= 0 ? "+" : ""}${edge}%`
        : `YES Edge ${edge >= 0 ? "+" : ""}${edge}%`;
    const root = document.createElement("div");
    root.className = "synth-overlay-root";
    root.setAttribute("data-synth-overlay", "badge");
    root.innerHTML = `
      <div class="synth-overlay-badge synth-overlay-${signal}">
        <span class="synth-overlay-label">${escapeHtml(label)}</span>
        <span class="synth-overlay-strength">${escapeHtml(strength)}</span>
      </div>
      <div class="synth-overlay-detail" hidden>
        <div class="synth-overlay-detail-row"><strong>Now (1h)</strong> ${escapeHtml(label)}</div>
        <div class="synth-overlay-detail-row"><strong>By close (24h)</strong> ${escapeHtml(label)}</div>
        <div class="synth-overlay-detail-row">Confidence: ${escapeHtml(strength)}</div>
        <div class="synth-overlay-detail-meta">${escapeHtml(data.current_time || "")}</div>
      </div>
    `;
    const badge = root.querySelector(".synth-overlay-badge");
    const detail = root.querySelector(".synth-overlay-detail");
    if (badge) {
      badge.addEventListener("click", function (e) {
        e.stopPropagation();
        if (detail) detail.hidden = !detail.hidden;
      });
    }
    return root;
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function injectBadge(container, data) {
    const existing = container.querySelector("[data-synth-overlay=badge]");
    if (existing) existing.remove();
    const badge = createBadge(data);
    container.appendChild(badge);
  }

  function findInjectionTarget() {
    const selectors = [
      "[class*='market']",
      "[class*='outcome']",
      "main",
      "[role='main']",
      ".pm-",
    ];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el && el.offsetParent) return el;
    }
    return document.body;
  }

  function fetchEdge(slug) {
    return fetch(`${API_BASE}/api/edge?slug=${encodeURIComponent(slug)}`, {
      method: "GET",
      mode: "cors",
    })
      .then(function (r) {
        if (!r.ok) return null;
        return r.json();
      })
      .catch(function () {
        return null;
      });
  }

  function run() {
    const slug = slugFromPage();
    if (!slug) return;
    fetchEdge(slug).then(function (data) {
      if (!data || data.error) return;
      const target = findInjectionTarget();
      if (target) injectBadge(target, data);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }

  const observer = new MutationObserver(function () {
    if (document.querySelector("[data-synth-overlay=badge]")) return;
    run();
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
