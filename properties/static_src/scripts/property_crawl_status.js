// Polls the crawl/lighthouse status endpoint and updates the monitoring
// panel in-place. When a crawl or lighthouse run is active, polling is
// fast (2s); when idle, it's slow (30s) so older tabs don't hammer the
// server.

const FAST_POLL_MS = 2000;
const SLOW_POLL_MS = 30000;

function $(root, selector) {
  return root.querySelector(selector);
}

function setText(root, field, value) {
  const el = root.querySelector(`[data-field="${field}"]`);
  if (el) el.textContent = value;
}

function show(root, field, visible) {
  const el = root.querySelector(`[data-field="${field}"]`);
  if (!el) return;
  el.classList.toggle("d-none", !visible);
}

function humanDuration(ms) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms} ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  const rs = Math.round(s - m * 60);
  return `${m}m ${rs}s`;
}

function relativeTime(iso, now) {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  const diff = now - then;
  const future = diff < 0;
  const abs = Math.abs(diff);
  const s = Math.round(abs / 1000);
  let text;
  if (s < 45) text = `${s}s`;
  else if (s < 3600) text = `${Math.round(s / 60)}m`;
  else if (s < 86400) text = `${Math.round(s / 3600)}h`;
  else text = `${Math.round(s / 86400)}d`;
  return future ? `in ${text}` : `${text} ago`;
}

function formatAbsolute(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString();
}

function stateBadge(state) {
  switch (state) {
    case "running":
      return { label: "Running", cls: "bg-primary" };
    case "queued":
      return { label: "Queued", cls: "bg-info text-dark" };
    default:
      return { label: "Idle", cls: "bg-secondary" };
  }
}

function renderWhen(root, field, iso, now) {
  const el = root.querySelector(`[data-field="${field}"]`);
  if (!el) return;
  if (!iso) {
    el.textContent = "—";
    el.removeAttribute("title");
    return;
  }
  const rel = relativeTime(iso, now);
  el.textContent = rel;
  el.title = formatAbsolute(iso);
}

function renderCrawler(root, crawler, serverNow) {
  const badge = root.querySelector('[data-field="crawler.state_badge"]');
  const s = stateBadge(crawler.state);
  badge.className = `badge ${s.cls}`;
  badge.textContent = s.label;

  show(root, "crawler.progress_wrap", crawler.state === "running");
  if (crawler.state === "running") {
    const bar = root.querySelector('[data-field="crawler.progress_bar"]');
    const pct = Math.round((crawler.progress || 0) * 100);
    bar.style.width = `${pct}%`;
    bar.setAttribute("aria-valuenow", pct);
  }

  show(root, "crawler.error_box", !!crawler.last_error);
  if (crawler.last_error) {
    setText(root, "crawler.error_text", crawler.last_error);
  }

  renderWhen(root, "crawler.last_success", crawler.last_success_at, serverNow);
  renderWhen(root, "crawler.last_attempt", crawler.last_attempt_at, serverNow);

  const pagesEl = root.querySelector('[data-field="crawler.pages"]');
  if (crawler.state === "running") {
    pagesEl.textContent = `${crawler.pages_count || 0} so far…`;
  } else if (crawler.pages_count != null) {
    pagesEl.textContent = `${crawler.pages_count}`;
  } else {
    pagesEl.textContent = "—";
  }

  setText(root, "crawler.duration", humanDuration(crawler.last_duration_ms));

  const ins = crawler.insights_by_severity || { error: 0, warning: 0, info: 0 };
  const insEl = root.querySelector('[data-field="crawler.insights"]');
  insEl.innerHTML = `
    <span class="badge bg-danger me-1">${ins.error} err</span>
    <span class="badge bg-warning text-dark me-1">${ins.warning} warn</span>
    <span class="badge bg-info text-dark">${ins.info} info</span>
  `;

  const nextEl = root.querySelector('[data-field="crawler.next_run"]');
  if (!crawler.next_run_at) {
    nextEl.textContent = "—";
    nextEl.removeAttribute("title");
  } else if (crawler.state === "running" || crawler.state === "queued") {
    nextEl.textContent = "— (running now)";
    nextEl.title = formatAbsolute(crawler.next_run_at);
  } else if (crawler.is_overdue) {
    nextEl.innerHTML = `<span class="text-warning">due now</span>`;
    nextEl.title = formatAbsolute(crawler.next_run_at);
  } else {
    nextEl.textContent = relativeTime(crawler.next_run_at, serverNow);
    nextEl.title = formatAbsolute(crawler.next_run_at);
  }
}

function renderLighthouse(root, lh, serverNow) {
  const badge = root.querySelector('[data-field="lighthouse.state_badge"]');
  const s = stateBadge(lh.state);
  badge.className = `badge ${s.cls}`;
  badge.textContent = s.label;

  show(root, "lighthouse.error_box", !!lh.last_error);
  if (lh.last_error) {
    setText(root, "lighthouse.error_text", lh.last_error);
  }

  renderWhen(root, "lighthouse.last_success", lh.last_success_at, serverNow);
  renderWhen(root, "lighthouse.last_attempt", lh.last_attempt_at, serverNow);
  setText(root, "lighthouse.duration", humanDuration(lh.last_duration_ms));

  const nextEl = root.querySelector('[data-field="lighthouse.next_run"]');
  if (!lh.next_run_at) {
    nextEl.textContent = "—";
    nextEl.removeAttribute("title");
  } else if (lh.state === "running" || lh.state === "queued") {
    nextEl.textContent = "— (running now)";
    nextEl.title = formatAbsolute(lh.next_run_at);
  } else if (lh.is_overdue) {
    nextEl.innerHTML = `<span class="text-warning">due now</span>`;
    nextEl.title = formatAbsolute(lh.next_run_at);
  } else {
    nextEl.textContent = relativeTime(lh.next_run_at, serverNow);
    nextEl.title = formatAbsolute(lh.next_run_at);
  }
}

function updateRecrawlButton(data) {
  const btn = document.getElementById("recrawl-btn");
  if (!btn) return;
  const state = data.crawler.state;
  // "overdue + idle" means the user already requested a recrawl but the
  // scheduler hasn't picked it up yet (up to ~30s).
  const waitingForScheduler = state === "idle" && data.crawler.is_overdue;
  const busy =
    state === "queued" || state === "running" || waitingForScheduler;
  btn.disabled = busy;
  const label = btn.querySelector(".recrawl-btn-label");
  const spinner = btn.querySelector(".recrawl-btn-spinner");
  if (busy) {
    spinner.classList.remove("d-none");
    if (state === "running") {
      const n = data.crawler.pages_count || 0;
      label.textContent = n > 0 ? `Crawling (${n})` : "Crawling…";
    } else if (state === "queued") {
      label.textContent = "Queued…";
    } else {
      label.textContent = "Waiting for scheduler…";
    }
  } else {
    spinner.classList.add("d-none");
    label.textContent = "Recrawl";
  }
}

function updateRerunLighthouseButton(data) {
  const btn = document.getElementById("rerun-lighthouse-btn");
  if (!btn) return;
  const state = data.lighthouse.state;
  const waitingForScheduler = state === "idle" && data.lighthouse.is_overdue;
  const busy =
    state === "queued" || state === "running" || waitingForScheduler;
  btn.disabled = busy;
  const label = btn.querySelector(".rerun-lh-label");
  const spinner = btn.querySelector(".rerun-lh-spinner");
  if (busy) {
    spinner.classList.remove("d-none");
    if (state === "running") label.textContent = "Running";
    else if (state === "queued") label.textContent = "Queued";
    else label.textContent = "Waiting…";
  } else {
    spinner.classList.add("d-none");
    label.textContent = "Rerun";
  }
}

function getCsrfToken() {
  const input = document.querySelector("input[name=csrfmiddlewaretoken]");
  return input ? input.value : "";
}

async function triggerPost(url, onDone) {
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        "Accept": "application/json",
      },
      credentials: "same-origin",
    });
    if (!res.ok) {
      console.error("POST failed", url, res.status);
      return;
    }
    const data = await res.json();
    if (onDone) onDone(data);
  } catch (err) {
    console.error("POST error", url, err);
  }
}

document.addEventListener("DOMContentLoaded", function () {
  const root = document.getElementById("monitoring-status");
  if (!root) return;

  const statusUrl = root.dataset.statusUrl;
  const recrawlUrl = root.dataset.recrawlUrl;
  const rerunLighthouseUrl = root.dataset.rerunLighthouseUrl;

  let prevCrawlState = null;
  let prevLhState = null;
  let timer = null;

  function schedule(data) {
    const active =
      data.crawler.state !== "idle" ||
      data.lighthouse.state !== "idle" ||
      data.crawler.is_overdue ||
      data.lighthouse.is_overdue;
    const delay = active ? FAST_POLL_MS : SLOW_POLL_MS;
    clearTimeout(timer);
    timer = setTimeout(poll, delay);
  }

  function applyData(data) {
    const serverNow = data.server_time ? new Date(data.server_time).getTime() : Date.now();
    renderCrawler(root, data.crawler, serverNow);
    renderLighthouse(root, data.lighthouse, serverNow);
    updateRecrawlButton(data);
    updateRerunLighthouseButton(data);

    // If either subsystem just went idle after being active, refresh the
    // page once so server-rendered charts/insights update.
    const crawlerFinished =
      prevCrawlState && prevCrawlState !== "idle" && data.crawler.state === "idle";
    const lhFinished =
      prevLhState && prevLhState !== "idle" && data.lighthouse.state === "idle";
    prevCrawlState = data.crawler.state;
    prevLhState = data.lighthouse.state;
    if (crawlerFinished || lhFinished) {
      window.location.reload();
      return;
    }
    schedule(data);
  }

  async function poll() {
    try {
      const res = await fetch(statusUrl, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        timer = setTimeout(poll, SLOW_POLL_MS);
        return;
      }
      const data = await res.json();
      applyData(data);
    } catch (err) {
      console.error("status poll failed", err);
      timer = setTimeout(poll, SLOW_POLL_MS);
    }
  }

  const recrawlBtn = document.getElementById("recrawl-btn");
  if (recrawlBtn && recrawlUrl) {
    recrawlBtn.addEventListener("click", function () {
      recrawlBtn.disabled = true;
      triggerPost(recrawlUrl, function (data) {
        applyData(data);
      });
    });
  }

  const rerunLhBtn = document.getElementById("rerun-lighthouse-btn");
  if (rerunLhBtn && rerunLighthouseUrl) {
    rerunLhBtn.addEventListener("click", function () {
      rerunLhBtn.disabled = true;
      triggerPost(rerunLighthouseUrl, function (data) {
        applyData(data);
      });
    });
  }

  poll();
});
