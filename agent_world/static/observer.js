(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const values = object => Object.values(object || {});
  const number = value => Number(value || 0);
  const fmt = value => new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(number(value));
  const pct = value => `${fmt(value)}%`;
  const esc = value => String(value ?? "").replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
  const title = value => String(value || "unknown").replace(/[_-]+/g, " ").replace(/\b\w/g, char => char.toUpperCase());
  const shortRunName = reference => {
    const parts = String(reference || "Untitled run").split("/").filter(Boolean);
    let leaf = parts.pop() || "Untitled run";
    if (leaf === "run-report.json" && parts.length) leaf = parts.pop();
    else leaf = leaf.replace(/-report\.json$/, "").replace(/\.json$/, "");
    return leaf.replace(/^\d{8}-\d{6}-?/, "").replaceAll("-", " ");
  };
  const runKey = run => run?.report || run?.id || "";
  const searchText = value => String(value || "").toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();

  const app = {
    config: null,
    state: null,
    catalog: [],
    catalogPayload: null,
    selectedRun: null,
    selectedDetail: null,
    comparison: new Map(),
    archiveView: false,
    viewTick: null,
    polling: null,
    refreshMs: 1400,
    timelinePlaying: false,
    analyticsTab: "economy",
    layers: { resources: true, structures: true, claims: true, labels: true },
    selection: null,
    hoveredTile: null,
    camera: { zoom: 1, x: 0, y: 0, fitted: false },
    drag: null,
    previousPositions: {},
    stateChangedAt: performance.now(),
    preset: "organic-generalists",
    cohortId: 0,
  };

  const canvas = $("#world-canvas");
  const ctx = canvas.getContext("2d");
  const terrainColors = { water: "#315f69", forest: "#294d36", mountain: "#6b6b60", plains: "#668259" };
  const resourceColors = { food: "#e2bd69", water: "#69b7c2", wood: "#8d6845", fiber: "#d6d1a4", stone: "#a7aaa5", ore: "#7f91a5", coin: "#ebc65e", tool: "#df8b57" };
  const providerColors = { codex: "#a6c973", codex_cli: "#a6c973", claude: "#df9367", claude_cli: "#df9367", llm: "#6fb4bd", openai_compatible: "#6fb4bd", survival: "#c3c8b7" };
  const structureGlyphs = { house: "⌂", well: "◉", farm_plot: "≋", storage: "▣", shelter: "⌃", workshop: "⚒" };
  const eventGlyphs = { say: "◌", whisper: "◌", broadcast: "◎", offer_trade: "⇄", accept_trade: "✓", gift: "◇", build: "⌂", build_started: "⌂", death: "†", invalid_action: "!", move: "→", gather: "◆", consume: "●", mine: "▲", chop: "♣", fish: "≈", create_group: "◉" };
  const resourceValues = { water: 1, food: 2, fiber: 2, wood: 3, stone: 4, ore: 8, coin: 1, tool: 10, advanced_tool: 24, ingot: 14 };

  async function fetchJSON(url, options = {}) {
    const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
    let payload = {};
    try { payload = await response.json(); } catch (_) { /* empty response */ }
    if (!response.ok) throw new Error(payload.error || `${response.status} ${response.statusText}`);
    return payload;
  }

  function toast(headline, message = "", kind = "") {
    const element = document.createElement("div");
    element.className = `toast ${kind}`;
    element.innerHTML = `<b>${esc(headline)}</b>${message ? `<p>${esc(message)}</p>` : ""}`;
    $("#toast-stack").append(element);
    setTimeout(() => element.remove(), 4800);
  }

  function navigate(route, push = true) {
    const normalized = route === "runs" ? "runs" : "world";
    if (push) history.pushState({}, "", normalized === "runs" ? "/runs" : "/");
    $$(".page").forEach(page => page.classList.toggle("active", page.id === `${normalized}-page`));
    $$("[data-route]").forEach(link => link.classList.toggle("active", link.dataset.route === normalized));
    if (normalized === "world") {
      resizeCanvas();
      if (app.state) renderPulse();
      requestAnimationFrame(drawWorld);
    } else {
      if (push) $("#runs-page").scrollTop = 0;
      loadCatalog();
    }
  }

  function setAnalyticsOpen(open) {
    $("#analytics-drawer").classList.toggle("open", open);
    $("#world-page").classList.toggle("analytics-visible", open);
    if (open) renderAnalytics();
  }

  async function boot() {
    bindStaticEvents();
    try {
      app.config = await fetchJSON("/api/config");
      buildRunForm();
    } catch (error) {
      toast("Configuration unavailable", error.message, "error");
    }
    await loadCatalog();
    await pollState();
    schedulePoll();
    navigate(location.pathname === "/runs" ? "runs" : "world", false);
    new ResizeObserver(resizeCanvas).observe($("#world-stage"));
    requestAnimationFrame(drawWorld);
  }

  function bindStaticEvents() {
    document.addEventListener("click", event => {
      const route = event.target.closest("[data-route]");
      if (route) { event.preventDefault(); navigate(route.dataset.route); }
      const tab = event.target.closest("[data-lab-tab]");
      if (tab) switchLabTab(tab.dataset.labTab);
    });
    window.addEventListener("popstate", () => navigate(location.pathname === "/runs" ? "runs" : "world", false));
    $("#header-pause").addEventListener("click", togglePause);
    $("#header-stop").addEventListener("click", stopRun);
    $("#pulse-collapse").addEventListener("click", () => $(".pulse-panel").classList.toggle("collapsed"));
    $("#inspector-close").addEventListener("click", clearSelection);
    $("#chronicle-toggle").addEventListener("click", () => $(".chronicle").classList.toggle("open"));
    $("#analytics-open").addEventListener("click", () => setAnalyticsOpen(true));
    $("#analytics-close").addEventListener("click", () => setAnalyticsOpen(false));
    $$("[data-analytics]").forEach(button => button.addEventListener("click", () => {
      app.analyticsTab = button.dataset.analytics;
      $$("[data-analytics]").forEach(item => item.classList.toggle("active", item === button));
      renderAnalytics();
    }));
    $$(".map-tool[data-layer]").forEach(button => button.addEventListener("click", () => {
      const layer = button.dataset.layer;
      app.layers[layer] = !app.layers[layer];
      button.classList.toggle("active", app.layers[layer]);
    }));
    $("#zoom-in").addEventListener("click", () => app.camera.zoom = clamp(app.camera.zoom * 1.2, .55, 3.5));
    $("#zoom-out").addEventListener("click", () => app.camera.zoom = clamp(app.camera.zoom / 1.2, .55, 3.5));
    $("#zoom-fit").addEventListener("click", fitCamera);
    $("#refresh-speed").addEventListener("change", event => { app.refreshMs = Number(event.target.value); schedulePoll(); });
    $("#tick-live").addEventListener("click", goLive);
    $("#tick-back").addEventListener("click", () => stepTimeline(-1));
    $("#tick-forward").addEventListener("click", () => stepTimeline(1));
    $("#tick-play").addEventListener("click", toggleTimelinePlayback);
    $("#timeline-slider").addEventListener("input", event => setViewTick(Number(event.target.value)));
    ["event-agent-filter", "event-type-filter", "event-search"].forEach(id => $(`#${id}`).addEventListener(id === "event-search" ? "input" : "change", renderEvents));
    bindCanvasEvents();
    $("#archive-refresh").addEventListener("click", loadCatalog);
    ["archive-search", "archive-status", "archive-quality"].forEach(id => $(`#${id}`).addEventListener(id === "archive-search" ? "input" : "change", renderArchive));
  }

  function schedulePoll() {
    clearInterval(app.polling);
    app.polling = setInterval(() => { if (!app.archiveView && app.viewTick == null) pollState(); }, app.refreshMs);
  }

  async function pollState() {
    if (app.archiveView) return;
    const requestedTick = app.viewTick;
    try {
      const state = await fetchJSON(requestedTick == null ? "/api/state" : `/api/state?tick=${requestedTick}`);
      if (app.archiveView || app.viewTick !== requestedTick) return;
      applyState(state);
    } catch (error) {
      console.warn("Observer polling failed", error);
    }
  }

  function applyState(state) {
    app.previousPositions = Object.fromEntries(values(app.state?.snapshot?.agents).map(agent => [agent.id, agent.position]));
    app.state = state;
    app.stateChangedAt = performance.now();
    const snapshot = state.snapshot || {};
    $("#map-empty").classList.toggle("visible", !snapshot.tiles?.length);
    if (!app.camera.fitted && snapshot.tiles?.length) fitCamera();
    renderHeader();
    renderWorldPlate();
    renderPulse();
    renderEvents();
    renderTimeline();
    if (app.selection) renderInspector();
    if ($("#analytics-drawer").classList.contains("open")) renderAnalytics();
  }

  function renderHeader() {
    const run = app.state?.run || {};
    const snapshot = app.state?.snapshot || {};
    const preservedStatus = app.state?.manifest?.status || app.state?.report?.run?.status;
    const state = run.state === "idle" && snapshot.tick != null && preservedStatus ? preservedStatus : (run.state || "idle");
    const active = ["running", "paused"].includes(state);
    const dot = $("#run-state-dot");
    dot.className = `state-dot ${run.paused ? "paused" : state}`;
    $("#run-kicker").textContent = app.archiveView ? "PRESERVED EXPEDITION" : active ? (run.paused ? "EXPEDITION PAUSED" : "EXPEDITION IN MOTION") : state === "completed" ? "EXPEDITION COMPLETE" : "OBSERVATORY READY";
    $("#run-label").textContent = app.archiveView ? shortRunName(run.run_id) : run.run_id ? shortRunName(run.run_id) : app.state?.manifest?.preset ? title(app.state.manifest.preset) : run.model || "Archive ready";
    $("#header-tick").textContent = snapshot.tick ?? run.current_tick ?? "—";
    $("#header-target").textContent = run.target_ticks ? `/ ${run.target_ticks}` : "";
    $("#header-pause").disabled = app.archiveView || !active;
    $("#header-stop").disabled = app.archiveView || !active;
    $("#header-pause").textContent = run.paused ? "▶" : "Ⅱ";
  }

  function renderWorldPlate() {
    const state = app.state || {};
    const snapshot = state.snapshot || {};
    const config = snapshot.config || state.manifest?.config || {};
    $("#world-source-badge").textContent = app.archiveView ? "ARCHIVED WORLD" : (state.run?.state === "running" ? "LIVE WORLD" : "WORLD STATE");
    $("#world-title").textContent = state.run?.run_id ? title(shortRunName(state.run.run_id)) : title(state.manifest?.preset || "The Frontier");
    const pieces = [config.economy_mode, config.geography_mode, config.specialization_mode].filter(Boolean).map(title);
    $("#world-subtitle").textContent = pieces.length ? pieces.join(" · ") : "Awaiting first light";
  }

  function worldMetrics() {
    const state = app.state || {};
    const snapshot = state.snapshot || {};
    const agents = values(snapshot.agents);
    const living = agents.filter(agent => agent.alive !== false);
    const structures = values(snapshot.structures);
    const trades = values(snapshot.trades);
    const inventories = {};
    let wealth = 0;
    living.forEach(agent => Object.entries(agent.inventory || {}).forEach(([item, qty]) => {
      inventories[item] = number(inventories[item]) + number(qty);
      wealth += number(qty) * (resourceValues[item] || 1);
    }));
    const needs = name => living.length ? living.reduce((sum, agent) => sum + number((agent.needs || agent.reserves || {})[name]), 0) / living.length : 0;
    return {
      total: agents.length,
      living: living.length,
      dead: agents.length - living.length,
      meanHealth: living.length ? living.reduce((sum, agent) => sum + number(agent.health), 0) / living.length : 0,
      food: needs("food"), water: needs("water"), energy: needs("energy"),
      completeStructures: structures.filter(item => item.status === "complete").length,
      sites: structures.filter(item => item.status !== "complete").length,
      groups: values(snapshot.groups).length,
      openTrades: trades.filter(trade => trade.status === "open").length,
      acceptedTrades: trades.filter(trade => trade.status === "accepted").length,
      messages: number(state.summary?.events?.say) + number(state.summary?.events?.whisper) + number(state.summary?.events?.broadcast),
      invalid: number(state.summary?.events?.invalid_action),
      inventories, wealth,
    };
  }

  function renderPulse() {
    const metrics = worldMetrics();
    $("#kpi-living").textContent = metrics.total ? `${metrics.living}/${metrics.total}` : "—";
    $("#kpi-living-delta").textContent = metrics.dead ? `${metrics.dead} lost` : "all accounted for";
    $("#kpi-trades").textContent = metrics.acceptedTrades;
    $("#kpi-offers").textContent = `${metrics.openTrades} open offers`;
    $("#kpi-structures").textContent = metrics.completeStructures;
    $("#kpi-builds").textContent = `${metrics.sites} sites active`;
    $("#kpi-groups").textContent = metrics.groups;
    $("#kpi-messages").textContent = `${metrics.messages} messages`;
    drawPulseChart(app.state?.summary?.series || {});
    const alerts = [];
    if (metrics.dead) alerts.push({ kind: "danger", text: `${metrics.dead} agent${metrics.dead === 1 ? "" : "s"} lost` });
    if (metrics.invalid > 20) alerts.push({ kind: "danger", text: `${metrics.invalid} invalid actions recorded` });
    if (metrics.openTrades) alerts.push({ kind: "", text: `${metrics.openTrades} open trade offer${metrics.openTrades === 1 ? "" : "s"}` });
    if (app.state?.summary?.quota_failures) alerts.push({ kind: "danger", text: "Provider quota failure detected" });
    $("#world-alerts").innerHTML = alerts.slice(0, 3).map(alert => `<div class="world-alert ${alert.kind}"><i></i>${esc(alert.text)}</div>`).join("");
  }

  function drawPulseChart(series) {
    const chart = $("#pulse-chart");
    const box = chart.getBoundingClientRect();
    const ratio = devicePixelRatio || 1;
    chart.width = Math.max(1, box.width * ratio); chart.height = Math.max(1, box.height * ratio);
    const c = chart.getContext("2d"); c.scale(ratio, ratio); c.clearRect(0, 0, box.width, box.height);
    const pop = series.population || [];
    const civ = (series.structures || []).map((value, index) => value + number((series.trades || [])[index]));
    drawLine(c, pop, box.width, box.height, "#b8d47d", 2);
    drawLine(c, civ, box.width, box.height, "#dcb867", 1.5);
  }

  function drawLine(context, data, width, height, color, lineWidth = 2) {
    if (!data.length) return;
    const min = Math.min(...data), max = Math.max(...data, min + 1);
    context.beginPath();
    data.forEach((value, index) => {
      const x = data.length === 1 ? 0 : index / (data.length - 1) * width;
      const y = height - 5 - ((value - min) / (max - min)) * (height - 12);
      index ? context.lineTo(x, y) : context.moveTo(x, y);
    });
    context.strokeStyle = color; context.lineWidth = lineWidth; context.lineJoin = "round"; context.stroke();
  }

  function resizeCanvas() {
    const box = canvas.getBoundingClientRect();
    const ratio = devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(box.width * ratio));
    canvas.height = Math.max(1, Math.round(box.height * ratio));
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  }

  function mapGeometry() {
    const tiles = app.state?.snapshot?.tiles || [];
    const rows = tiles.length, columns = tiles[0]?.length || 0;
    const box = canvas.getBoundingClientRect();
    const base = rows && columns ? Math.min((box.width - 110) / columns, (box.height - 85) / rows) : 0;
    const size = base * app.camera.zoom;
    return { rows, columns, size, ox: box.width / 2 - columns * size / 2 + app.camera.x, oy: box.height / 2 - rows * size / 2 + app.camera.y, width: box.width, height: box.height };
  }

  function fitCamera() { app.camera = { zoom: 1, x: 0, y: 0, fitted: true }; }

  function drawWorld(now) {
    const box = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, box.width, box.height);
    const snapshot = app.state?.snapshot || {};
    const tiles = snapshot.tiles || [];
    if (tiles.length) {
      const geo = mapGeometry();
      drawTerrain(tiles, geo, now);
      if (app.layers.structures) drawStructures(snapshot, geo);
      drawPiles(snapshot, geo);
      drawAgents(snapshot, geo, now);
      if (app.hoveredTile) drawHover(geo, app.hoveredTile);
    }
    requestAnimationFrame(drawWorld);
  }

  function drawTerrain(tiles, geo, now) {
    ctx.save();
    ctx.shadowColor = "rgba(0,0,0,.45)"; ctx.shadowBlur = 35;
    ctx.fillStyle = "#10231d"; ctx.fillRect(geo.ox - 8, geo.oy - 8, geo.columns * geo.size + 16, geo.rows * geo.size + 16);
    ctx.shadowBlur = 0;
    tiles.forEach((row, y) => row.forEach((tile, x) => {
      const px = geo.ox + x * geo.size, py = geo.oy + y * geo.size;
      ctx.fillStyle = terrainColors[tile.terrain] || "#63765e";
      ctx.fillRect(px, py, geo.size + .5, geo.size + .5);
      drawTerrainTexture(tile, x, y, px, py, geo.size, now);
      if (app.layers.claims && tile.claimed_by) {
        ctx.strokeStyle = agentColor(tile.claimed_by, .9); ctx.lineWidth = Math.max(1, geo.size * .06); ctx.strokeRect(px + 2, py + 2, geo.size - 4, geo.size - 4);
      }
      if (app.layers.resources) drawResources(tile.resources || {}, px, py, geo.size);
    }));
    ctx.strokeStyle = "rgba(225,235,219,.09)"; ctx.lineWidth = 1;
    for (let x = 0; x <= geo.columns; x++) { ctx.beginPath(); ctx.moveTo(geo.ox + x * geo.size, geo.oy); ctx.lineTo(geo.ox + x * geo.size, geo.oy + geo.rows * geo.size); ctx.stroke(); }
    for (let y = 0; y <= geo.rows; y++) { ctx.beginPath(); ctx.moveTo(geo.ox, geo.oy + y * geo.size); ctx.lineTo(geo.ox + geo.columns * geo.size, geo.oy + y * geo.size); ctx.stroke(); }
    ctx.restore();
  }

  function drawTerrainTexture(tile, x, y, px, py, size, now) {
    const seed = (x * 19 + y * 31) % 7;
    ctx.save(); ctx.globalAlpha = .34;
    if (tile.terrain === "water") {
      ctx.strokeStyle = "#8cc3c7"; ctx.lineWidth = Math.max(.7, size * .025);
      for (let i = 0; i < 2; i++) { const yy = py + size * (.3 + i * .32) + Math.sin(now / 700 + x + y + i) * 1.4; ctx.beginPath(); ctx.moveTo(px + size * .15, yy); ctx.quadraticCurveTo(px + size * .5, yy - 2, px + size * .82, yy); ctx.stroke(); }
    } else if (tile.terrain === "forest") {
      ctx.fillStyle = "#173a2a";
      const wood = number(tile.resources?.wood); const count = clamp(Math.round(wood / 2) + 2, 2, 6);
      for (let i = 0; i < count; i++) { const tx = px + size * (.2 + ((seed + i * 3) % 7) / 10); const ty = py + size * (.25 + ((seed * 2 + i * 5) % 6) / 11); ctx.beginPath(); ctx.moveTo(tx, ty - size * .12); ctx.lineTo(tx - size * .09, ty + size * .08); ctx.lineTo(tx + size * .09, ty + size * .08); ctx.fill(); }
    } else if (tile.terrain === "mountain") {
      ctx.strokeStyle = "#b3afa2"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(px + size * .12, py + size * .75); ctx.lineTo(px + size * .42, py + size * (.23 + seed * .015)); ctx.lineTo(px + size * .59, py + size * .56); ctx.lineTo(px + size * .73, py + size * .32); ctx.lineTo(px + size * .9, py + size * .75); ctx.stroke();
    } else {
      ctx.strokeStyle = "#a2b879"; ctx.lineWidth = .8; for (let i = 0; i < 3; i++) { const gx = px + size * (.22 + i * .23); const gy = py + size * (.58 + ((seed + i) % 3) * .08); ctx.beginPath(); ctx.moveTo(gx, gy); ctx.lineTo(gx - 2, gy - size * .13); ctx.moveTo(gx, gy); ctx.lineTo(gx + 3, gy - size * .1); ctx.stroke(); }
    }
    ctx.restore();
  }

  function drawResources(resources, px, py, size) {
    const entries = Object.entries(resources).filter(([, qty]) => number(qty) > 0).slice(0, 4);
    entries.forEach(([item, qty], index) => {
      const radius = clamp(size * .055 + Math.log1p(number(qty)) * .45, 1.7, 4.3);
      ctx.beginPath(); ctx.arc(px + size * (.16 + index * .15), py + size * .84, radius, 0, Math.PI * 2); ctx.fillStyle = resourceColors[item] || "#d9d3b4"; ctx.fill();
    });
  }

  function drawStructures(snapshot, geo) {
    values(snapshot.structures).forEach(structure => {
      const pos = structure.position || {}; const x = geo.ox + (number(pos.x) + .5) * geo.size, y = geo.oy + (number(pos.y) + .5) * geo.size;
      const radius = clamp(geo.size * .27, 7, 18);
      ctx.save(); ctx.translate(x, y); ctx.fillStyle = structure.status === "complete" ? "#d8c78d" : "rgba(216,199,141,.35)"; ctx.strokeStyle = "#3a3c31"; ctx.lineWidth = 1.4;
      if (structure.status !== "complete") ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.roundRect(-radius, -radius, radius * 2, radius * 2, 3); ctx.fill(); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = "#29352d"; ctx.font = `${Math.max(9, radius)}px Georgia`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(structureGlyphs[structure.type] || "⌂", 0, 1); ctx.restore();
    });
  }

  function drawPiles(snapshot, geo) {
    values(snapshot.item_piles).forEach(pile => {
      const pos = pile.position || {}; const x = geo.ox + (number(pos.x) + .78) * geo.size, y = geo.oy + (number(pos.y) + .75) * geo.size;
      ctx.beginPath(); ctx.arc(x, y, clamp(geo.size * .08, 2, 5), 0, Math.PI * 2); ctx.fillStyle = resourceColors[pile.item] || "#d5d0b8"; ctx.fill(); ctx.strokeStyle = "rgba(0,0,0,.45)"; ctx.stroke();
    });
  }

  function drawAgents(snapshot, geo, now) {
    const elapsed = clamp((now - app.stateChangedAt) / 650, 0, 1);
    const t = 1 - Math.pow(1 - elapsed, 3);
    values(snapshot.agents).forEach(agent => {
      const previous = app.previousPositions[agent.id] || agent.position; const target = agent.position || previous;
      const gx = number(previous.x) + (number(target.x) - number(previous.x)) * t;
      const gy = number(previous.y) + (number(target.y) - number(previous.y)) * t;
      const x = geo.ox + (gx + .5) * geo.size, y = geo.oy + (gy + .47) * geo.size;
      const radius = clamp(geo.size * .16, 4.5, 10);
      ctx.save(); ctx.translate(x, y);
      if (agent.alive === false) { ctx.strokeStyle = "#c5c0ab"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(-radius, radius); ctx.lineTo(radius, -radius); ctx.moveTo(-radius, -radius); ctx.lineTo(radius, radius); ctx.stroke(); ctx.restore(); return; }
      const color = agentColor(agent.id);
      ctx.shadowColor = "rgba(0,0,0,.55)"; ctx.shadowBlur = 7; ctx.beginPath(); ctx.ellipse(0, radius * .95, radius * 1.1, radius * .5, 0, 0, Math.PI * 2); ctx.fillStyle = "rgba(0,0,0,.35)"; ctx.fill(); ctx.shadowBlur = 0;
      ctx.beginPath(); ctx.arc(0, 0, radius, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill(); ctx.strokeStyle = app.selection?.type === "agent" && app.selection.id === agent.id ? "#fff5c6" : "rgba(255,255,255,.65)"; ctx.lineWidth = app.selection?.id === agent.id ? 2.5 : 1; ctx.stroke();
      const health = clamp(number(agent.health) / 100, 0, 1); ctx.beginPath(); ctx.arc(0, 0, radius + 3, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * health); ctx.strokeStyle = health < .35 ? "#e45f55" : "rgba(205,235,190,.65)"; ctx.lineWidth = 1.3; ctx.stroke();
      if (app.layers.labels && geo.size > 27) { ctx.font = `${clamp(geo.size * .18, 8, 11)}px sans-serif`; ctx.fillStyle = "rgba(239,245,231,.92)"; ctx.textAlign = "center"; ctx.fillText(agent.name || agent.id, 0, -radius - 6); }
      ctx.restore();
    });
  }

  function drawHover(geo, tile) {
    ctx.save(); ctx.strokeStyle = "rgba(255,244,190,.9)"; ctx.lineWidth = 2; ctx.strokeRect(geo.ox + tile.x * geo.size + 1, geo.oy + tile.y * geo.size + 1, geo.size - 2, geo.size - 2); ctx.restore();
  }

  function agentGroup(agentId) {
    const population = app.state?.manifest?.population || app.state?.run?.population || {};
    const groupId = population.assignments?.[agentId];
    return (population.groups || []).find(group => group.id === groupId) || null;
  }

  function agentColor(agentId, alpha = 1) {
    const group = agentGroup(agentId); const source = group?.provider || group?.type;
    let color = providerColors[source];
    if (!color) { let hash = 0; for (const char of String(agentId)) hash = ((hash << 5) - hash) + char.charCodeAt(0); color = `hsl(${Math.abs(hash) % 360} 42% 62%)`; }
    if (alpha === 1 || !color.startsWith("#")) return color;
    const r = parseInt(color.slice(1, 3), 16), g = parseInt(color.slice(3, 5), 16), b = parseInt(color.slice(5, 7), 16); return `rgba(${r},${g},${b},${alpha})`;
  }

  function bindCanvasEvents() {
    canvas.addEventListener("wheel", event => { event.preventDefault(); app.camera.zoom = clamp(app.camera.zoom * (event.deltaY > 0 ? .9 : 1.1), .55, 3.5); }, { passive: false });
    canvas.addEventListener("pointerdown", event => { canvas.setPointerCapture(event.pointerId); app.drag = { x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY, cameraX: app.camera.x, cameraY: app.camera.y }; });
    canvas.addEventListener("pointermove", event => {
      if (app.drag) { app.camera.x = app.drag.cameraX + event.clientX - app.drag.x; app.camera.y = app.drag.cameraY + event.clientY - app.drag.y; }
      const tile = tileFromPointer(event); app.hoveredTile = tile;
      renderTooltip(event, tile);
    });
    canvas.addEventListener("pointerup", event => { if (app.drag && Math.hypot(event.clientX - app.drag.startX, event.clientY - app.drag.startY) < 6) selectAtPointer(event); app.drag = null; });
    canvas.addEventListener("pointerleave", () => { app.hoveredTile = null; $("#tooltip").classList.remove("visible"); });
  }

  function tileFromPointer(event) {
    const geo = mapGeometry(), rect = canvas.getBoundingClientRect();
    const x = Math.floor((event.clientX - rect.left - geo.ox) / geo.size), y = Math.floor((event.clientY - rect.top - geo.oy) / geo.size);
    if (x < 0 || y < 0 || x >= geo.columns || y >= geo.rows) return null;
    return { x, y, tile: app.state?.snapshot?.tiles?.[y]?.[x] };
  }

  function renderTooltip(event, hit) {
    const tip = $("#tooltip");
    if (!hit?.tile) { tip.classList.remove("visible"); return; }
    const agents = values(app.state?.snapshot?.agents).filter(agent => agent.position?.x === hit.x && agent.position?.y === hit.y);
    const resources = Object.entries(hit.tile.resources || {}).filter(([, qty]) => number(qty) > 0).map(([item, qty]) => `${item} ${qty}`).join(" · ") || "depleted";
    tip.innerHTML = `<b>${title(hit.tile.terrain)} [${hit.x}, ${hit.y}]</b><br>${esc(resources)}${agents.length ? `<br>${esc(agents.map(agent => agent.name).join(", "))}` : ""}`;
    tip.style.left = `${event.clientX + 14}px`; tip.style.top = `${event.clientY + 14}px`; tip.classList.add("visible");
  }

  function selectAtPointer(event) {
    const hit = tileFromPointer(event); if (!hit) return;
    const snapshot = app.state?.snapshot || {};
    const agent = values(snapshot.agents).find(item => item.position?.x === hit.x && item.position?.y === hit.y);
    const structure = values(snapshot.structures).find(item => item.position?.x === hit.x && item.position?.y === hit.y);
    app.selection = agent ? { type: "agent", id: agent.id } : structure ? { type: "structure", id: structure.id } : { type: "tile", x: hit.x, y: hit.y };
    renderInspector(); $("#inspector").classList.add("open");
  }

  function clearSelection() { app.selection = null; $("#inspector").classList.remove("open"); }

  function renderInspector() {
    const selection = app.selection, snapshot = app.state?.snapshot || {}; if (!selection) return;
    let html = "";
    if (selection.type === "agent") {
      const agent = snapshot.agents?.[selection.id]; if (!agent) return clearSelection();
      const group = agentGroup(agent.id); const needs = agent.needs || agent.reserves || {}; const config = snapshot.config || {};
      $("#inspector-kicker").textContent = "AGENT DOSSIER";
      html = `<div class="inspector-hero"><div class="inspector-identity"><div class="agent-portrait" style="background:${agentColor(agent.id)}">${esc((agent.name || agent.id).replace("Agent ", ""))}</div><div><h3>${esc(agent.name || agent.id)}</h3><p>${esc(group?.model || group?.type || "unknown mind")} · tile ${agent.position?.x},${agent.position?.y}</p></div></div><div class="badge-row"><span class="badge">${esc(agent.specialty || "generalist")}</span><span class="badge">${agent.alive === false ? "deceased" : "living"}</span>${(agent.groups || []).map(item => `<span class="badge">${esc(item)}</span>`).join("")}</div></div>
      <section class="inspector-section"><h4>Condition</h4>${meterRow("Health", agent.health, 100, "health")}${meterRow("Food", needs.food, config.food_reserve_max || 20, "food")}${meterRow("Water", needs.water, config.water_reserve_max || 20, "water")}${meterRow("Energy", needs.energy, config.energy_reserve_max || 30, "")}</section>
      <section class="inspector-section"><h4>Inventory · ${number(agent.carry_weight)}/${number(agent.carry_capacity)} weight</h4><div class="inventory-grid">${inventoryHtml(agent.inventory)}</div></section>
      <section class="inspector-section"><h4>Skills</h4><div class="kv-list">${Object.entries(agent.skills || {}).sort((a,b) => b[1]-a[1]).map(([key,value]) => `<div><span>${esc(title(key))}</span><b>${fmt(value)}</b></div>`).join("") || "<small>No developed skills</small>"}</div></section>
      <section class="inspector-section"><h4>Memory</h4>${(agent.memory || []).slice(-5).reverse().map(note => `<div class="memory-note">${esc(note)}</div>`).join("") || "<small>No retained memories</small>"}</section>`;
    } else if (selection.type === "structure") {
      const structure = snapshot.structures?.[selection.id]; if (!structure) return clearSelection();
      $("#inspector-kicker").textContent = "CIVIL ASSET";
      html = `<div class="inspector-hero"><div class="inspector-identity"><div class="agent-portrait" style="background:#d8c78d">${structureGlyphs[structure.type] || "⌂"}</div><div><h3>${esc(title(structure.type))}</h3><p>${esc(structure.id)} · tile ${structure.position?.x},${structure.position?.y}</p></div></div><div class="badge-row"><span class="badge">${esc(structure.status)}</span><span class="badge">${structure.active === false ? "inactive" : "active"}</span><span class="badge">${esc(structure.owner_id || "unowned")}</span></div></div>
      <section class="inspector-section"><h4>Asset state</h4><div class="kv-list"><div><span>Durability</span><b>${fmt(structure.durability)}%</b></div><div><span>Capacity</span><b>${fmt(structure.capacity)}</b></div><div><span>Stored weight</span><b>${fmt(structure.stored_weight)}</b></div><div><span>Contributors</span><b>${(structure.contributors || []).length}</b></div></div></section>
      <section class="inspector-section"><h4>Stored goods</h4><div class="inventory-grid">${inventoryHtml(structure.inventory)}</div></section>`;
    } else {
      const tile = snapshot.tiles?.[selection.y]?.[selection.x]; if (!tile) return clearSelection();
      $("#inspector-kicker").textContent = "TERRAIN SURVEY";
      const occupants = values(snapshot.agents).filter(agent => agent.position?.x === selection.x && agent.position?.y === selection.y);
      html = `<div class="inspector-hero"><div class="inspector-identity"><div class="agent-portrait" style="background:${terrainColors[tile.terrain] || "#777"}">◆</div><div><h3>${esc(title(tile.terrain))}</h3><p>Coordinates ${selection.x}, ${selection.y}</p></div></div><div class="badge-row">${tile.claimed_by ? `<span class="badge">claimed by ${esc(tile.claimed_by)}</span>` : `<span class="badge">unclaimed</span>`}<span class="badge">${occupants.length} occupants</span></div></div>
      <section class="inspector-section"><h4>Natural resources</h4><div class="inventory-grid">${inventoryHtml(tile.resources)}</div></section>
      <section class="inspector-section"><h4>Present</h4><div class="kv-list">${occupants.map(agent => `<div><span>${esc(agent.name)}</span><b>${fmt(agent.health)} hp</b></div>`).join("") || "<small>No agents on this tile</small>"}</div></section>`;
    }
    $("#inspector-content").innerHTML = html;
  }

  function meterRow(label, value, max, kind) { const percentage = max > 0 ? clamp(number(value) / number(max) * 100, 0, 100) : 0; return `<div class="meter-row"><span>${esc(label)}</span><div class="meter ${kind}"><i style="width:${percentage}%"></i></div><b>${Math.round(percentage)}%</b></div>`; }
  function inventoryHtml(inventory) { const entries = Object.entries(inventory || {}).filter(([, qty]) => number(qty) > 0); return entries.length ? entries.map(([item, qty]) => `<div class="inventory-item"><b style="color:${resourceColors[item] || "inherit"}">${fmt(qty)}</b><small>${esc(item)}</small></div>`).join("") : "<small>Empty</small>"; }

  function eventClass(type) {
    if (["offer_trade", "accept_trade", "reject_trade", "expire_trade", "gift"].includes(type)) return "trade";
    if (["say", "whisper", "broadcast", "create_group", "join_group"].includes(type)) return "social";
    if (["build", "build_started", "contribute_build", "repair"].includes(type)) return "build";
    if (["death", "survival_damage", "consume", "food_spoilage"].includes(type)) return "survival";
    if (type === "invalid_action") return "invalid";
    return "action";
  }

  function renderEvents() {
    const events = app.state?.recent_events || [];
    $("#chronicle-count").textContent = `${events.length} events`;
    const latest = events.at(-1);
    $("#event-ticker").innerHTML = latest ? `<div class="ticker-event"><b>T${latest.tick}</b>${esc(latest.message || title(latest.type))}</div>` : `<div class="ticker-event">The world is quiet.</div>`;
    const agents = values(app.state?.snapshot?.agents);
    const select = $("#event-agent-filter"), current = select.value;
    select.innerHTML = `<option value="all">All agents</option>${agents.map(agent => `<option value="${esc(agent.id)}">${esc(agent.name)}</option>`).join("")}`; select.value = agents.some(agent => agent.id === current) ? current : "all";
    const typeFilter = $("#event-type-filter").value, search = $("#event-search").value.toLowerCase();
    const filtered = events.filter(event => (select.value === "all" || event.actor_id === select.value) && (typeFilter === "all" || eventClass(event.type) === typeFilter) && (!search || `${event.message} ${event.actor_id} ${event.type}`.toLowerCase().includes(search)));
    $("#event-list").innerHTML = filtered.slice().reverse().map(event => `<article class="event-row ${eventClass(event.type)}"><time>T${event.tick}</time><span class="event-symbol">${eventGlyphs[event.type] || "·"}</span><div><strong>${esc(event.actor_id ? (app.state?.snapshot?.agents?.[event.actor_id]?.name || event.actor_id) : title(event.type))}</strong><p>${esc(event.message || title(event.type))}</p></div></article>`).join("") || `<div class="inspector-empty"><p>No events match these filters.</p></div>`;
  }

  function renderTimeline() {
    const history = app.state?.history || {}; const slider = $("#timeline-slider"); const live = number(history.live_tick ?? app.state?.snapshot?.tick);
    slider.min = history.min_tick ?? 0; slider.max = history.max_tick ?? live; slider.value = app.viewTick ?? live; slider.disabled = app.archiveView || !history.count;
    $("#timeline-label").textContent = app.viewTick == null ? (app.archiveView ? "FINAL STATE" : "LIVE") : `TICK ${app.viewTick}`;
    $("#timeline-range").textContent = `tick ${slider.min} — ${slider.max}`;
    $("#tick-live").classList.toggle("active", app.viewTick == null && !app.archiveView);
  }

  async function setViewTick(tick) { if (app.archiveView) return; app.viewTick = tick; try { applyState(await fetchJSON(`/api/state?tick=${tick}`)); } catch (error) { toast("Timeline unavailable", error.message, "error"); } }
  function stepTimeline(delta) { const slider = $("#timeline-slider"); setViewTick(clamp(number(app.viewTick ?? slider.max) + delta, number(slider.min), number(slider.max))); }
  function goLive() { app.archiveView = false; app.viewTick = null; pollState(); }
  function toggleTimelinePlayback() { app.timelinePlaying = !app.timelinePlaying; $("#tick-play").textContent = app.timelinePlaying ? "Ⅱ" : "▶"; if (app.timelinePlaying) playTimelineStep(); }
  function playTimelineStep() { if (!app.timelinePlaying) return; const slider = $("#timeline-slider"); const next = number(app.viewTick ?? slider.min) + 1; if (next > number(slider.max)) { app.timelinePlaying = false; $("#tick-play").textContent = "▶"; return; } setViewTick(next).then(() => setTimeout(playTimelineStep, 520)); }

  async function togglePause() { const paused = Boolean(app.state?.run?.paused); try { const response = await fetchJSON(paused ? "/api/run/resume" : "/api/run/pause", { method: "POST", body: "{}" }); app.state.run = response.run; renderHeader(); toast(paused ? "World resumed" : "World paused"); } catch (error) { toast("Control failed", error.message, "error"); } }
  async function stopRun() { if (!confirm("Stop the active expedition after its current in-flight decision? Artifacts will be preserved.")) return; try { await fetchJSON("/api/run/stop", { method: "POST", body: "{}" }); toast("Stop requested", "The current tick will settle before the run closes."); } catch (error) { toast("Stop failed", error.message, "error"); } }

  function analyticsKpis(items) { return `<div class="analytics-kpis">${items.map(item => `<article><small>${esc(item.label)}</small><strong>${esc(item.value)}</strong>${item.note ? `<small>${esc(item.note)}</small>` : ""}</article>`).join("")}</div>`; }
  function barList(entries, colors = {}) { const max = Math.max(1, ...entries.map(([, value]) => number(value))); return `<div class="bar-list">${entries.map(([label, value]) => `<div class="bar-row"><span>${esc(title(label))}</span><div class="bar-track"><i style="width:${number(value)/max*100}%;background:${colors[label] || resourceColors[label] || "var(--moss)"}"></i></div><b>${fmt(value)}</b></div>`).join("")}</div>`; }
  function analyticsCard(titleText, body, extra = "") { return `<section class="analytics-card ${extra}"><h3>${esc(titleText)}</h3><div class="analytics-card-body">${body}</div></section>`; }

  function renderAnalytics() {
    const report = app.state?.report || {}; const metrics = worldMetrics(); const content = $("#analytics-content");
    if (!app.state) { content.innerHTML = `<div class="inspector-empty"><p>No world data is available.</p></div>`; return; }
    if (app.analyticsTab === "economy") {
      const trades = report.economy?.trades || {}; const economy = report.economy || {};
      const inventoryEntries = Object.entries(metrics.inventories).sort((a,b) => b[1]-a[1]);
      content.innerHTML = analyticsKpis([
        { label: "Open offers", value: metrics.openTrades }, { label: "Accepted trades", value: trades.accepted ?? metrics.acceptedTrades }, { label: "Inventory wealth", value: fmt(metrics.wealth) },
        { label: "Gifts", value: economy.gifts ?? number(app.state?.summary?.events?.gift) }, { label: "Trade value", value: fmt(trades.accepted_value) }, { label: "Wealth Gini", value: report.wealth_gini != null ? fmt(report.wealth_gini) : "—" },
      ]) + analyticsCard("Goods held by living agents", barList(inventoryEntries.length ? inventoryEntries : [["none",0]])) + analyticsCard("Trade funnel", barList([
        ["offers created", trades.funnel?.offers_created || values(app.state?.snapshot?.trades).length], ["counterparties reached", trades.funnel?.offers_observed_by_counterparty || 0], ["accept attempts", trades.accept_attempts || 0], ["completed", trades.accepted || 0],
      ], { "offers created": "#dcb867", "counterparties reached": "#9fbc7d", "accept attempts": "#6fa3aa", completed: "#b8d47d" })) + analyticsCard("Market state", `<div class="kv-list"><div><span>Gift value</span><b>${fmt(economy.gift_value)}</b></div><div><span>Construction assets</span><b>${fmt(economy.construction?.assets?.replacement_cost_value)}</b></div><div><span>Stored asset value</span><b>${fmt(economy.construction?.assets?.stored_inventory_value)}</b></div><div><span>Contracts fulfilled</span><b>${fmt(economy.institutions?.contracts?.fulfilled)}</b></div></div>`);
    } else if (app.analyticsTab === "population") {
      const agents = values(app.state.snapshot?.agents); const healthBands = { critical: 0, strained: 0, stable: 0, strong: 0 };
      agents.forEach(agent => { const health = number(agent.health); healthBands[health <= 25 ? "critical" : health <= 60 ? "strained" : health < 90 ? "stable" : "strong"]++; });
      content.innerHTML = analyticsKpis([{ label: "Living", value: `${metrics.living}/${metrics.total}` }, { label: "Mean health", value: pct(metrics.meanHealth) }, { label: "Deaths", value: metrics.dead }, { label: "Food reserve", value: fmt(metrics.food) }, { label: "Water reserve", value: fmt(metrics.water) }, { label: "Energy reserve", value: fmt(metrics.energy) }]) + analyticsCard("Health distribution", barList(Object.entries(healthBands), { critical: "#e35f56", strained: "#df9367", stable: "#dcb867", strong: "#8eaf6c" })) + analyticsCard("Agent roster", `<table class="model-table"><thead><tr><th>Agent</th><th>Mind</th><th>Health</th><th>Role</th><th>Load</th></tr></thead><tbody>${agents.sort((a,b) => number(b.health)-number(a.health)).map(agent => { const group=agentGroup(agent.id); return `<tr><td>${esc(agent.name)}</td><td>${esc(group?.model || group?.type || "—")}</td><td>${fmt(agent.health)}</td><td>${esc(agent.specialty || "generalist")}</td><td>${fmt(agent.carry_weight)}/${fmt(agent.carry_capacity)}</td></tr>`; }).join("")}</tbody></table>`);
    } else if (app.analyticsTab === "civilization") {
      const series = app.state.summary?.series || {}; const structures = values(app.state.snapshot?.structures); const structureCounts = structures.reduce((memo,item) => { memo[item.type] = number(memo[item.type]) + 1; return memo; }, {});
      content.innerHTML = analyticsKpis([{ label: "Structures", value: metrics.completeStructures }, { label: "Build sites", value: metrics.sites }, { label: "Groups", value: metrics.groups }, { label: "Messages", value: metrics.messages }, { label: "Trades", value: metrics.acceptedTrades }, { label: "Current tick", value: app.state.snapshot?.tick ?? "—" }]) + analyticsCard("Civilization over time", `<canvas id="civilization-chart" class="big-chart"></canvas>`) + analyticsCard("Built environment", barList(Object.entries(structureCounts).length ? Object.entries(structureCounts) : [["no structures",0]])) + analyticsCard("Milestones", milestoneHtml(report.milestone_first_ticks || {}, app.state.recent_events || []));
      requestAnimationFrame(() => drawCivilizationChart($("#civilization-chart"), series));
    } else {
      const cohorts = report.population?.cohorts || {}; const populationGroups = app.state.manifest?.population?.groups || app.state.run?.population?.groups || [];
      const rows = Object.keys(cohorts).length ? Object.values(cohorts) : populationGroups.map(group => ({ model: group.model || group.type, provider: group.provider || group.type, initial_agents: group.count, living: "—", invalid_actions_per_proposed_action_pct: "—", communication: "—", trades_offered: "—", usage: {} }));
      content.innerHTML = analyticsKpis([{ label: "Cohorts", value: rows.length }, { label: "Decision calls", value: fmt(report.usage?.calls) }, { label: "Prompt tokens", value: compactNumber(report.usage?.prompt_tokens) }, { label: "Output tokens", value: compactNumber(report.usage?.completion_tokens) }, { label: "Codex credits", value: fmt(report.usage?.simulation_credits?.credits?.total) }, { label: "Quality", value: report.reliability?.quality_status || "live" }]) + analyticsCard("Cohort outcomes", `<table class="model-table"><thead><tr><th>Model</th><th>Provider</th><th>Agents</th><th>Living</th><th>Invalid</th><th>Speech</th><th>Offers</th></tr></thead><tbody>${rows.map(row => `<tr><td>${esc(row.model || row.brain)}</td><td>${esc(row.provider)}</td><td>${fmt(row.initial_agents || row.count)}</td><td>${fmt(row.living)}</td><td>${row.invalid_actions_per_proposed_action_pct === "—" ? "—" : pct(row.invalid_actions_per_proposed_action_pct)}</td><td>${fmt(row.communication)}</td><td>${fmt(row.trades_offered)}</td></tr>`).join("")}</tbody></table>`) + analyticsCard("Reliability", `<div class="kv-list"><div><span>Decision failure rate</span><b>${report.reliability ? pct(report.reliability.decision_failure_rate_pct) : "—"}</b></div><div><span>Invalid action rate</span><b>${report.reliability ? pct(report.reliability.invalid_action_rate_pct) : "—"}</b></div><div><span>Usage coverage</span><b>${report.reliability?.usage_record_coverage_pct != null ? pct(report.reliability.usage_record_coverage_pct) : "—"}</b></div><div><span>Quota failures</span><b>${fmt(report.reliability?.llm_quota_failure_events)}</b></div></div>`);
    }
  }

  function compactNumber(value) { const n = number(value); return n >= 1e6 ? `${(n/1e6).toFixed(1)}m` : n >= 1e3 ? `${(n/1e3).toFixed(1)}k` : fmt(n); }
  function milestoneHtml(milestones, events) { const entries = Object.entries(milestones); if (!entries.length) { const firsts = {}; events.forEach(event => { if (firsts[event.type] == null) firsts[event.type] = event.tick; }); ["say","offer_trade","accept_trade","build","create_group"].forEach(key => { if (firsts[key] != null) entries.push([key, firsts[key]]); }); } return entries.length ? `<div class="kv-list">${entries.sort((a,b)=>a[1]-b[1]).map(([name,tick]) => `<div><span>${esc(title(name))}</span><b>tick ${tick}</b></div>`).join("")}</div>` : `<small>No civilization milestones yet.</small>`; }

  function drawCivilizationChart(chart, series) {
    if (!chart) return; const box = chart.getBoundingClientRect(), ratio = devicePixelRatio || 1; chart.width = box.width * ratio; chart.height = box.height * ratio; const c = chart.getContext("2d"); c.scale(ratio,ratio); c.clearRect(0,0,box.width,box.height);
    c.strokeStyle = "rgba(220,230,216,.1)"; c.lineWidth = 1; for (let i=1;i<4;i++){c.beginPath();c.moveTo(0,box.height*i/4);c.lineTo(box.width,box.height*i/4);c.stroke();}
    [[series.population,"#b8d47d"],[series.structures,"#dcb867"],[series.trades,"#6fa8b2"],[series.messages,"#df784e"]].forEach(([data,color]) => drawLine(c,data||[],box.width,box.height,color,2));
  }

  function switchLabTab(tab) { $$("[data-lab-tab]").forEach(button => button.classList.toggle("active", button.dataset.labTab === tab)); $$(".lab-panel").forEach(panel => panel.classList.toggle("active", panel.id === `lab-${tab}`)); $("#runs-page").scrollTop = 0; if (tab === "compare") renderComparison(); }

  function buildRunForm() {
    renderPresetCards();
    const observation = $("#observation-mode"); observation.innerHTML = app.config.observation_modes.map(mode => `<option value="${esc(mode)}" ${mode === "compact-v2" ? "selected" : ""}>${esc(mode)}</option>`).join("");
    const turn = $("#turn-mode"); turn.innerHTML = app.config.turn_modes.map(mode => `<option value="${esc(mode)}" ${mode === "simultaneous-v1" ? "selected" : ""}>${esc(mode)}</option>`).join("");
    addCohort({ count: 5, brain: "codex", model: "gpt-5.6-luna", reasoning_effort: "low" });
    addCohort({ count: 5, brain: "claude", model: "claude-sonnet-5", reasoning_effort: "low" });
    $("#add-cohort").addEventListener("click", () => addCohort({ count: 1, brain: "codex", model: "gpt-5.6-luna", reasoning_effort: "low" }));
    $("#random-seed").addEventListener("click", () => { const seed = Math.floor(Math.random() * 2_147_483_647); $("#run-seed").value = seed; $("#assignment-seed").value = seed; });
    $("#run-seed").addEventListener("change", event => $("#assignment-seed").value = event.target.value);
    $("#run-form").addEventListener("input", updateLaunchSummary);
    $("#run-form").addEventListener("change", updateLaunchSummary);
    $("#run-form").addEventListener("submit", launchRun);
    [["resource-multiplier", value => `${Number(value).toFixed(1)}×`],["wild-food", value => `${Math.round(value*100)}%`],["wild-fiber", value => `${Math.round(value*100)}%`]].forEach(([id,format]) => $(`#${id}`).addEventListener("input", event => $(`#${id}-output`).textContent = format(event.target.value)));
    updateLaunchSummary();
  }

  function renderPresetCards() {
    $("#preset-grid").innerHTML = Object.entries(app.config.presets).map(([id,preset]) => `<button type="button" class="preset-card ${id===app.preset?"active":""}" data-preset="${esc(id)}"><i></i><b>${esc(preset.label)}</b><small>${esc(preset.description)}</small></button>`).join("");
    $$("[data-preset]").forEach(button => button.addEventListener("click", () => selectPreset(button.dataset.preset)));
  }

  function selectPreset(id) { app.preset = id; $$("[data-preset]").forEach(button => button.classList.toggle("active", button.dataset.preset === id)); const preset = app.config.presets[id]; ["economy_mode","geography_mode","specialization_mode","objective_mode"].forEach(key => { const input = $(`#${key.replaceAll("_","-")}`); if (input) input.value = preset[key]; }); updateLaunchSummary(); }

  function addCohort(data) {
    app.cohortId += 1; const id = app.cohortId; const row = document.createElement("div"); row.className = "cohort-row"; row.dataset.cohort = id;
    row.innerHTML = `<input class="cohort-count" aria-label="Cohort count" type="number" min="1" max="100" value="${number(data.count)||1}"><select class="cohort-brain" aria-label="Runtime"><option value="codex">Codex plan</option><option value="claude">Claude plan</option><option value="llm">Metered API</option><option value="survival">Deterministic</option></select><select class="cohort-model" aria-label="Model"></select><select class="cohort-effort" aria-label="Reasoning">${app.config.reasoning_efforts.map(effort => `<option value="${effort}">${effort}</option>`).join("")}</select><button type="button" class="cohort-remove" aria-label="Remove cohort">×</button>`;
    $("#cohort-list").append(row); $(".cohort-brain", row).value = data.brain || "codex"; updateCohortModels(row, data.model); $(".cohort-effort",row).value = data.reasoning_effort || "low";
    $(".cohort-brain",row).addEventListener("change", () => updateCohortModels(row)); $(".cohort-remove",row).addEventListener("click", () => { row.remove(); updateLaunchSummary(); }); row.addEventListener("input", updateLaunchSummary); row.addEventListener("change", updateLaunchSummary); updateLaunchSummary();
  }

  function updateCohortModels(row, preferred) { const brain = $(".cohort-brain",row).value; const models = app.config.models[brain] || []; const select = $(".cohort-model",row); select.innerHTML = models.map(model => `<option value="${esc(model)}">${esc(model)}</option>`).join(""); if (preferred && models.includes(preferred)) select.value = preferred; $(".cohort-effort",row).disabled = brain === "survival"; }
  function cohortRows() { return $$(".cohort-row").map(row => ({ count: number($(".cohort-count",row).value), brain: $(".cohort-brain",row).value, model: $(".cohort-model",row).value, reasoning_effort: $(".cohort-effort",row).value, thinking_budget_tokens: $(".cohort-brain",row).value === "claude" ? number($("#claude-thinking").value) : undefined })); }
  function updateLaunchSummary() { const cohorts = cohortRows(), agents = cohorts.reduce((sum,row)=>sum+row.count,0), ticks=number($("#run-ticks")?.value); $("#population-total").textContent = `${agents} agent${agents===1?"":"s"}`; $("#launch-summary").textContent = `${agents} agents · ${ticks} ticks · ${app.config?.presets?.[app.preset]?.label || title(app.preset)}`; const calls=agents*ticks; $("#launch-warning").textContent = `${calls.toLocaleString()} decisions · artifacts preserved under runs/observatory/`; }

  function runPayload() {
    return {
      name: $("#run-name").value.trim(), preset: app.preset, seed: number($("#run-seed").value), ticks: number($("#run-ticks").value), population: cohortRows(), assignment_strategy: $("#assignment-strategy").value, assignment_seed: number($("#assignment-seed").value),
      observation_mode: $("#observation-mode").value, turn_mode: $("#turn-mode").value, decision_mode: $("#decision-mode").value, max_workers: number($("#max-workers").value), codex_max_workers: number($("#codex-workers").value), claude_max_workers: number($("#claude-workers").value), llm_max_workers: number($("#llm-workers").value), log_agent_io: $("#log-agent-io").checked,
      economy_mode: $("#economy-mode").value, geography_mode: $("#geography-mode").value, specialization_mode: $("#specialization-mode").value, objective_mode: $("#objective-mode").value, action_points_per_tick: number($("#action-points").value), default_carry_capacity: number($("#carry-capacity").value), resource_base_multiplier: number($("#resource-multiplier").value), wild_food_density: number($("#wild-food").value), wild_fiber_density: number($("#wild-fiber").value), survival_food_decay: number($("#food-decay").value), survival_water_decay: number($("#water-decay").value), survival_energy_decay: number($("#energy-decay").value),
    };
  }

  async function launchRun(event) {
    event.preventDefault(); const button=$("#launch-run"), payload=runPayload(), agents=payload.population.reduce((sum,row)=>sum+row.count,0); if (!agents) return toast("Population required","Add at least one cohort.","error"); if (agents>100) return toast("Population too large","The observatory currently supports up to 100 agents.","error"); button.disabled=true; button.querySelector("span").textContent="Opening world…";
    try { const response=await fetchJSON("/api/run/start",{method:"POST",body:JSON.stringify(payload)}); app.archiveView=false; app.viewTick=null; app.camera.fitted=false; toast("World launched", `${agents} agents have entered the frontier.`); navigate("world"); app.state={...(app.state||{}),run:response.run}; await pollState(); }
    catch(error){toast("Launch failed",error.message,"error");}
    finally{button.disabled=false;button.querySelector("span").textContent="Launch world";}
  }

  async function loadCatalog() {
    try { const payload=await fetchJSON("/api/runs"); app.catalogPayload=payload; app.catalog=payload.runs||[]; const calls=app.catalog.reduce((sum,run)=>sum+number(run.llm_calls),0), clean=app.catalog.filter(run=>run.quality_status==="clean").length; $("#archive-count").textContent=app.catalog.length; $("#archive-calls").textContent=compactNumber(calls); $("#archive-clean-rate").textContent=app.catalog.length?`${Math.round(clean/app.catalog.length*100)}%`:"—"; renderArchive(); }
    catch(error){toast("Archive unavailable",error.message,"error");}
  }

  function filteredCatalog() { const search=searchText($("#archive-search")?.value), status=$("#archive-status")?.value||"all", quality=$("#archive-quality")?.value||"all"; return app.catalog.filter(run=>{ const haystack=searchText(`${run.id} ${run.report} ${run.preset} ${(run.models||[]).join(" ")} ${run.turn_mode}`); return (!search||haystack.includes(search))&&(status==="all"||run.status===status)&&(quality==="all"||(quality==="clean"?run.quality_status==="clean":run.quality_status!=="clean")); }); }

  function renderArchive() {
    const list=$("#archive-list"); if(!list)return; const runs=filteredCatalog(); list.innerHTML=runs.map(run=>{const key=runKey(run);return `<article class="run-card ${app.selectedRun===key?"active":""}" data-run-id="${esc(key)}"><input type="checkbox" class="compare-check" aria-label="Add to comparison" ${app.comparison.has(key)?"checked":""}><div><h3>${esc(title(shortRunName(key)))}</h3><p>${esc(run.preset||"legacy")} · ${(run.models||[]).map(esc).join(", ")||"unknown model"}</p><span class="status-chip ${esc(run.status)}">${esc(run.status||"unknown")}</span></div><div class="run-stat"><small>Ticks</small><b>${fmt(run.final_tick)}/${fmt(run.target_ticks)}</b></div><div class="run-stat"><small>Invalid</small><b>${run.invalid_actions_per_proposed_action_pct==null?"—":pct(run.invalid_actions_per_proposed_action_pct)}</b></div><div class="run-stat"><small>Credits</small><b>${run.codex_simulation_credits==null?"—":fmt(run.codex_simulation_credits)}</b></div><span class="run-chevron">›</span></article>`;}).join("")||`<div class="compare-empty"><span>⌕</span><h2>No matching runs</h2><p>Try a broader search or launch a new world.</p></div>`;
    $$(".run-card",list).forEach(card=>{ card.addEventListener("click",event=>{ if(event.target.classList.contains("compare-check"))return; selectArchive(card.dataset.runId); }); $(".compare-check",card).addEventListener("change",event=>toggleComparison(card.dataset.runId,event.target.checked)); });
  }

  async function selectArchive(id) { app.selectedRun=id; renderArchive(); $("#archive-preview").innerHTML=`<div class="archive-empty"><span>◌</span><h3>Reading preserved evidence…</h3></div>`; try { app.selectedDetail=await fetchJSON(`/api/runs/detail?id=${encodeURIComponent(id)}`); renderArchivePreview(); } catch(error){$("#archive-preview").innerHTML=`<div class="archive-empty"><h3>Run unavailable</h3><p>${esc(error.message)}</p></div>`;} }

  function renderArchivePreview() {
    const detail=app.selectedDetail||{}, report=detail.report||{}, manifest=detail.manifest||{}, run=report.run||{}, reliability=report.reliability||{}, economy=report.economy||{}, survival=report.survival||{};
    $("#archive-preview").innerHTML=`<div class="preview-head"><span class="eyebrow">${esc(reliability.quality_status||manifest.status||"preserved")}</span><h2>${esc(title(shortRunName(detail.id)))}</h2><p>${esc(manifest.preset||"legacy world")} · ${esc((manifest.population?.groups||[]).map(group=>`${group.count} ${group.model||group.type}`).join(" · "))}</p></div><div class="preview-metrics"><article><small>Final tick</small><strong>${fmt(run.final_tick)}</strong></article><article><small>Living</small><strong>${fmt(survival.living)}</strong></article><article><small>Invalid</small><strong>${reliability.invalid_action_rate_pct==null?"—":pct(reliability.invalid_action_rate_pct)}</strong></article><article><small>Offers</small><strong>${fmt(economy.trades?.offered)}</strong></article><article><small>Trades</small><strong>${fmt(economy.trades?.accepted)}</strong></article><article><small>Structures</small><strong>${fmt(economy.construction?.assets?.complete)}</strong></article></div><div class="preview-body"><div class="kv-list"><div><span>Turn mode</span><b>${esc(manifest.turn_mode||"legacy")}</b></div><div><span>Observation</span><b>${esc(manifest.observation_mode||"legacy")}</b></div><div><span>Decision calls</span><b>${fmt(report.usage?.calls)}</b></div><div><span>Codex credits</span><b>${fmt(report.usage?.simulation_credits?.credits?.total)}</b></div></div><div class="preview-actions"><button id="preview-open" class="primary">Open world</button><button id="preview-compare">${app.comparison.has(detail.id)?"Remove comparison":"Add comparison"}</button><button id="preview-clone">Clone setup</button><button id="preview-report">Open analytics</button></div></div>`;
    $("#preview-open").addEventListener("click",()=>openArchivedRun(detail.id)); $("#preview-compare").addEventListener("click",()=>toggleComparison(detail.id,!app.comparison.has(detail.id),detail)); $("#preview-clone").addEventListener("click",()=>cloneRun(detail)); $("#preview-report").addEventListener("click",async()=>{await openArchivedRun(detail.id);setAnalyticsOpen(true);});
  }

  async function openArchivedRun(id) { try { const state=await fetchJSON(`/api/runs/state?id=${encodeURIComponent(id)}`); app.archiveView=true; app.viewTick=null; app.camera.fitted=false; applyState(state); navigate("world"); if(!state.snapshot?.tiles?.length) { setAnalyticsOpen(true); toast("Map evidence unavailable","The compact report is present, but this run has no local raw snapshot."); } } catch(error){toast("Could not open run",error.message,"error");} }

  function cloneRun(detail) { const manifest=detail.manifest||{}, config=manifest.config||{}, groups=manifest.population?.groups||[]; app.preset=manifest.preset&&app.config.presets[manifest.preset]?manifest.preset:"organic-generalists"; renderPresetCards(); $("#run-name").value=`${title(shortRunName(detail.id))} copy`; $("#run-seed").value=config.seed??11; $("#assignment-seed").value=manifest.population?.assignment_seed??config.seed??11; $("#run-ticks").value=manifest.target_ticks??30; $("#cohort-list").innerHTML=""; groups.forEach(group=>addCohort({count:group.count,brain:group.type,model:group.model,reasoning_effort:group.reasoning_effort})); const fields={"economy-mode":config.economy_mode,"geography-mode":config.geography_mode,"specialization-mode":config.specialization_mode,"objective-mode":config.objective_mode,"action-points":config.action_points_per_tick,"carry-capacity":config.default_carry_capacity,"resource-multiplier":config.resource_base_multiplier,"wild-food":config.wild_food_density,"wild-fiber":config.wild_fiber_density,"observation-mode":manifest.observation_mode,"turn-mode":manifest.turn_mode,"decision-mode":manifest.decision_mode,"max-workers":manifest.concurrency?.global,"codex-workers":manifest.concurrency?.providers?.codex_cli,"claude-workers":manifest.concurrency?.providers?.claude_cli,"llm-workers":manifest.concurrency?.providers?.openai_compatible}; Object.entries(fields).forEach(([id,value])=>{if(value!=null&&$(`#${id}`))$(`#${id}`).value=value;}); updateLaunchSummary(); switchLabTab("launch"); toast("Configuration cloned","Review the setup and launch it as a new preserved run."); }

  async function toggleComparison(id, enabled, detail=null) { if(enabled&&app.comparison.size>=4)return toast("Comparison full","Remove a run before adding another.","error"); if(enabled){ try{const payload=detail||await fetchJSON(`/api/runs/detail?id=${encodeURIComponent(id)}`);app.comparison.set(id,payload);}catch(error){return toast("Could not add comparison",error.message,"error");} }else app.comparison.delete(id); $("#compare-count").textContent=app.comparison.size; renderArchive(); if(app.selectedRun===id&&app.selectedDetail)renderArchivePreview(); renderComparison(); }

  function renderComparison() { const empty=$("#compare-empty"),view=$("#compare-view"); if(!app.comparison.size){empty.style.display="grid";view.innerHTML="";return;} empty.style.display="none"; const entries=[...app.comparison.entries()]; const metrics=[ ["Status",d=>d.manifest?.status||d.report?.run?.status], ["Ticks",d=>`${fmt(d.report?.run?.final_tick)}/${fmt(d.report?.run?.target_ticks)}`], ["Population",d=>fmt(d.report?.population?.total_agents)], ["Living",d=>fmt(d.report?.survival?.living)], ["Mean health",d=>{const agents=values(d.report?.survival?.agents);return agents.length?pct(agents.reduce((sum,a)=>sum+number(a.health),0)/agents.length):"—";}], ["Invalid rate",d=>d.report?.reliability?.invalid_action_rate_pct==null?"—":pct(d.report.reliability.invalid_action_rate_pct)], ["Speech",d=>fmt(d.report?.communication?.says_total)], ["Trade offers",d=>fmt(d.report?.economy?.trades?.offered)], ["Accepted trades",d=>fmt(d.report?.economy?.trades?.accepted)], ["Trade value",d=>fmt(d.report?.economy?.trades?.accepted_value)], ["Gifts",d=>fmt(d.report?.economy?.gifts)], ["Structures",d=>fmt(d.report?.economy?.construction?.assets?.complete)], ["Wealth Gini",d=>fmt(d.report?.wealth_gini)], ["Decision calls",d=>fmt(d.report?.usage?.calls)], ["Prompt tokens",d=>compactNumber(d.report?.usage?.prompt_tokens)], ["Codex credits",d=>fmt(d.report?.usage?.simulation_credits?.credits?.total)] ]; view.innerHTML=`<table class="comparison-table"><thead><tr><th>Measure</th>${entries.map(([id])=>`<th>${esc(title(shortRunName(id)))}</th>`).join("")}</tr></thead><tbody>${metrics.map(([label,get])=>`<tr><td>${esc(label)}</td>${entries.map(([,detail])=>`<td>${esc(get(detail))}</td>`).join("")}</tr>`).join("")}</tbody></table>`; }

  boot();
})();
