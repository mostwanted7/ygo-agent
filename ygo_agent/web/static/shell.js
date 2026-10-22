"use strict";
// The web app around the board viewer (`ygo-agent web` only; a play/selfplay/teach/coach --web panel is just the
// viewer). Hash routes: #/ home, #/decks, #/decks/NAME, #/new (and #/new/NAME: the train wizard), #/games (the
// viewer in app.js), #/jobs, #/jobs/ID, #/setup. Everything here runs the CLI through /api/jobs (docs/web.md).

(() => {
  if (!app.appMode) return;

  const S = {
    info: null,          // /api/app
    decks: null,         // /api/decks rows
    jobs: [],            // /api/jobs, refreshed by the poll
    seenGames: new Set(),// game ids already announced
    page: null,          // the current page's {alive, timers}
    route: null,
  };

  // ---------------------------------------------------------------- helpers

  async function api(path, body) {
    const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    const r = await fetch(path, opts);
    let data = null;
    try { data = await r.json(); } catch { /* not JSON */ }
    if (!r.ok) throw new Error((data && data.error) || `${r.status} ${r.statusText}`);
    return data;
  }
  const page = () => $("#page");
  const alive = (p) => p && p.alive && S.page === p;
  function every(p, ms, fn) { const t = setInterval(() => { if (alive(p)) fn(); }, ms); p.timers.push(t); }
  const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
  function when(ts) {
    if (!ts) return "";
    const d = typeof ts === "number" ? new Date(ts * 1000) : new Date(String(ts).replace(" ", "T"));
    if (isNaN(d)) return esc(String(ts));
    const today = new Date().toDateString() === d.toDateString();
    return today ? d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
      : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  function dur(s) {
    s = Math.max(0, Math.round(s || 0));
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    return m < 60 ? `${m}m${String(s % 60).padStart(2, "0")}s` : `${Math.floor(m / 60)}h${String(m % 60).padStart(2, "0")}m`;
  }
  function notify(title, sub, actions = [], kind = "good") {
    const t = el("div", `toast act ${kind}`, `${esc(title)}${sub ? `<small>${esc(sub)}</small>` : ""}`);
    if (actions.length) {
      const row = el("div", "toast-actions");
      for (const a of actions) {
        const b = el("button", `btn ${a.primary ? "primary" : ""}`, esc(a.label));
        b.onclick = () => { t.remove(); a.run(); };
        row.append(b);
      }
      t.append(row);
    }
    $("#toasts").append(t);
    setTimeout(() => t.remove(), actions.length ? 12000 : 4500);
  }
  const KIND_LABEL = { play: "duel", selfplay: "AI vs AI", teach: "lesson", coach: "coach", "train-interview": "interview", train: "training", learn: "learn", doctor: "setup check" };
  const statusChip = (j) => `<span class="jchip ${j.status}">${j.status === "running" && j.waiting ? "waiting" : esc(j.status)}</span>`;
  const resultChip = (r) => (r ? `<span class="res ${esc(r)}">${esc(String(r).toUpperCase())}</span>` : "");

  const ICONS = {
    duel: '<svg viewBox="0 0 24 24"><path d="M4 4l9 9M13 13l-2.2 2.2M13 13l2.2-2.2M20 4l-9 9M11 13l2.2 2.2M11 13 8.8 10.8M5.5 17.5 3.8 19.2M18.5 17.5l1.7 1.7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    watch: '<svg viewBox="0 0 24 24"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><circle cx="12" cy="12" r="3" fill="currentColor"/></svg>',
    teach: '<svg viewBox="0 0 24 24"><path d="M3 5.5h7a2 2 0 0 1 2 2V19a1.6 1.6 0 0 0-1.6-1.6H3zM21 5.5h-7a2 2 0 0 0-2 2V19a1.6 1.6 0 0 1 1.6-1.6H21z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
    coach: '<svg viewBox="0 0 24 24"><path d="M2 9l10-4.5L22 9l-10 4.5z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M6 11v4.6c2 2 10 2 12 0V11M22 9v5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    plus: '<svg viewBox="0 0 20 20"><path d="M10 4v12M4 10h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    stop: '<svg viewBox="0 0 20 20"><rect x="5" y="5" width="10" height="10" rx="2" fill="currentColor"/></svg>',
    room: '<svg viewBox="0 0 24 24"><rect x="3" y="4.5" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 20h8M12 16.5V20" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  };

  // ---------------------------------------------------------------- Markdown (playbooks, tips, reports)

  function inline(s) {
    return esc(s).split(/(`[^`]+`)/).map((part, i) => (i % 2 ? `<code>${part.slice(1, -1)}</code>` : part
      .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
      .replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s.,;:)!?]|$)/g, "$1<i>$2</i>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>'))).join("");
  }
  function mdDoc(text) {
    const out = [];
    const lines = String(text || "").replace(/\r\n/g, "\n").split("\n");
    let para = [], list = null, pre = null;
    const flushPara = () => { if (para.length) { out.push(`<p>${inline(para.join(" "))}</p>`); para = []; } };
    const flushList = () => { if (list) { out.push(`<${list.tag}>${list.items.map((x) => `<li class="${x.sub ? "sub" : ""}">${inline(x.text)}</li>`).join("")}</${list.tag}>`); list = null; } };
    const flush = () => { flushPara(); flushList(); };
    for (let i = 0; i < lines.length; i++) {
      const raw = lines[i], line = raw.replace(/\s+$/, "");
      let m;
      if (/^```/.test(line)) { if (pre) { out.push(`<pre>${esc(pre.join("\n"))}</pre>`); pre = null; } else { flush(); pre = []; } continue; }
      if (pre) { pre.push(raw); continue; }
      if (!line.trim()) { flush(); continue; }
      if (/^\s*\|.*\|\s*$/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || "")) {
        flush();
        const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const head = cells(line);
        const rows = [];
        i += 2;
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
        i--;
        out.push(`<div class="md-table"><table><thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
        continue;
      }
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flush(); const n = Math.min(4, m[1].length + 1); out.push(`<h${n}>${inline(m[2])}</h${n}>`); continue; }
      if (/^(-{3,}|\*{3,})$/.test(line.trim())) { flush(); out.push("<hr>"); continue; }
      if ((m = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/))) {
        flushPara();
        const tag = /\d/.test(m[2]) ? "ol" : "ul";
        if (!list || (list.tag !== tag && m[1].length < 2)) { flushList(); list = { tag, items: [] }; }
        list.items.push({ text: m[3], sub: m[1].length >= 2 });
        continue;
      }
      if ((m = line.match(/^>\s?(.*)$/))) { flush(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); continue; }
      if (list && /^\s{2,}\S/.test(raw)) { list.items[list.items.length - 1].text += " " + line.trim(); continue; }
      flushList();
      para.push(line.trim());
    }
    flush();
    if (pre) out.push(`<pre>${esc(pre.join("\n"))}</pre>`);
    return out.join("");
  }

  // ---------------------------------------------------------------- shared data

  async function loadInfo() {
    if (!S.info) S.info = await api("/api/app");
    return S.info;
  }
  async function loadDecks(force) {
    if (!S.decks || force) S.decks = (await api("/api/decks")).decks;
    return S.decks;
  }
  const playable = () => (S.decks || []).filter((d) => !d.training_only);

  function deckOptions(selected, { blank } = {}) {
    const rows = playable();
    const sel = selected || (S.info && S.info.default_deck);
    return (blank ? `<option value="">${esc(blank)}</option>` : "") + rows.map((d) =>
      `<option value="${esc(d.key)}" ${d.key.toLowerCase() === String(sel || "").toLowerCase() && !blank ? "selected" : ""} ${d.ydk_ok ? "" : "disabled"}>${esc(d.name)}${d.name.toLowerCase() !== d.key.toLowerCase() ? ` (${esc(d.key)})` : ""}${d.ydk_ok ? "" : " (no .ydk)"}</option>`).join("");
  }
  function backendOptions(selected, { llmOnly } = {}) {
    const sel = selected || S.info.default_backend;
    return S.info.backends.filter((b) => !llmOnly || !["heuristic", "random"].includes(b.type)).map((b) =>
      `<option value="${esc(b.name)}" ${b.name === sel ? "selected" : ""} ${b.ok ? "" : "disabled"} title="${esc(b.problem || b.label)}">${esc(b.name)}${b.label !== b.name ? ` · ${esc(b.label.replace(b.name + " ", ""))}` : ""}${b.ok ? "" : " (not set up)"}</option>`).join("");
  }
  function windbotOptions(selected) {
    return S.info.windbots.map((w) => `<option value="${esc(w.name)}" ${w.name === selected ? "selected" : ""}>${esc(w.name)}</option>`).join("");
  }
  const hasWindbots = () => S.info.windbots.length > 0;
  const field = (label, control, cls = "") => `<label class="field ${cls}"><span>${label}</span>${control}</label>`;
  const seg = (name, values, selected) => `<div class="seg mini" data-seg="${name}">${values.map((v) => `<button type="button" data-v="${v}" class="${String(v) === String(selected) ? "on" : ""}">${v}</button>`).join("")}</div>`;

  // A seat: an AI deck with a backend, or a WindBot deck AI.
  function seatEditor(name, init = {}) {
    const kind = init.kind === "windbot" && hasWindbots() ? "windbot" : "agent";
    return `<div class="seat" data-seat="${name}">
      ${field("Who", `<select data-k="kind"><option value="agent" ${kind === "agent" ? "selected" : ""}>AI deck</option><option value="windbot" ${kind === "windbot" ? "selected" : ""} ${hasWindbots() ? "" : "disabled"}>WindBot deck AI${hasWindbots() ? "" : " (none here)"}</option></select>`)}
      ${field("Deck", `<select data-k="deck">${deckOptions(init.deck)}</select>`, "for-agent")}
      ${field("Backend", `<select data-k="backend">${backendOptions(init.backend)}</select>`, "for-agent")}
      ${field("Deck AI", `<select data-k="name">${windbotOptions(init.name || "Blue-Eyes")}</select>`, "for-windbot")}
    </div>`;
  }
  function wireSeats(root) {
    for (const s of $$(".seat", root)) {
      const sync = () => { const k = $("[data-k=kind]", s).value; s.dataset.kind = k; };
      $("[data-k=kind]", s).onchange = sync;
      sync();
    }
    for (const g of $$(".seg.mini", root)) {
      g.onclick = (e) => { const b = e.target.closest("button"); if (!b) return; for (const x of $$("button", g)) x.classList.toggle("on", x === b); };
    }
  }
  function readSeat(root, name) {
    const s = $(`.seat[data-seat="${name}"]`, root);
    const v = (k) => $(`[data-k="${k}"]`, s).value;
    return v("kind") === "windbot" ? { kind: "windbot", name: v("name") } : { kind: "agent", deck: v("deck"), backend: v("backend") };
  }
  const segValue = (root, name) => { const b = $(`.seg[data-seg="${name}"] button.on`, root); return b ? b.dataset.v : null; };
  const val = (root, sel) => { const e = $(sel, root); return e ? (e.type === "checkbox" ? e.checked : e.value.trim()) : null; };
  const num = (root, sel) => { const v = val(root, sel); return v === "" || v == null ? null : Number(v); };

  async function startJob(kind, params, button) {
    if (button) button.disabled = true;
    try {
      const { job } = await api("/api/jobs", { kind, params });
      S.jobs = [job, ...S.jobs.filter((j) => j.id !== job.id)];
      renderNavCount();
      return job;
    } catch (e) {
      notify("Couldn't start it", e.message, [], "bad");
      return null;
    } finally {
      if (button) button.disabled = false;
    }
  }

  // ---------------------------------------------------------------- the router

  function parseRoute() {
    const h = location.hash.replace(/^#\/?/, "");
    const [name, ...rest] = h.split("/");
    const arg = rest.length ? decodeURIComponent(rest.join("/")) : null;
    if (!name) return { name: app.params.get("game") && !location.hash ? "games" : "home" };
    if (name === "decks") return arg ? { name: "deck", arg } : { name: "decks" };
    if (name === "jobs") return arg ? { name: "job", arg } : { name: "jobs" };
    if (["new", "games", "setup"].includes(name)) return { name, arg };
    return { name: "home" };
  }

  const PAGES = {};
  function go() {
    const r = parseRoute();
    S.route = r;
    if (S.page) { S.page.alive = false; for (const t of S.page.timers) clearInterval(t); }
    const p = { alive: true, timers: [] };
    S.page = p;
    const viewer = r.name === "games";
    app.viewer = viewer;
    document.body.classList.toggle("route-page", !viewer);
    page().classList.toggle("hidden", viewer);
    const navName = { deck: "decks", job: "jobs", new: "decks" }[r.name] || r.name;
    for (const a of $$("#nav a")) a.classList.toggle("on", a.dataset.route === navName);
    if (viewer) {
      if (typeof hidePreview === "function") hidePreview();
      document.title = app.game ? `${$("#game-title").textContent} · ygo-agent` : "Games · ygo-agent";
      requestAnimationFrame(() => { fit(); if (!app.game) openSomething(); });
      return;
    }
    closeModal();
    hidePreview();
    page().scrollTop = 0;
    page().innerHTML = `<div class="pg"><div class="loading">Loading…</div></div>`;
    (PAGES[r.name] || PAGES.home)(p, r.arg).catch((e) => {
      if (alive(p)) page().innerHTML = `<div class="pg"><div class="box error-box"><h2>Something went wrong</h2><p>${esc(e.message || e)}</p></div></div>`;
    });
  }
  function openSomething() {
    const live = app.live.find((x) => x.live);
    if (live) openLive(live.game_id);
    else showGames();
  }
  function openGame(gameId, recorded, decision) {
    location.hash = "#/games";
    const onBus = app.live.find((x) => x.game_id === gameId);
    if (gameId && (onBus || !recorded)) openLive(gameId);
    else if (recorded) openRecorded(recorded, decision);
  }

  // ---------------------------------------------------------------- Home

  PAGES.home = async (p) => {
    await Promise.all([loadInfo(), loadDecks(true)]);
    if (!alive(p)) return;
    const I = S.info;
    const room = I.room;
    const firstBot = I.windbots.find((w) => w.name === "Blue-Eyes") || I.windbots[0];
    const oppInit = firstBot ? { kind: "windbot", name: firstBot.name } : { kind: "agent", deck: I.default_deck, backend: "heuristic" };
    page().innerHTML = `<div class="pg home">
      <div class="hero">
        <div><h1>What do you want to do?</h1>
        <p class="sub">Each of these runs a <code>ygo-agent</code> command for you; its games show live here, on the board under <a href="#/games">Games</a>. Rules ${esc(I.rules)} · default backend <b>${esc(I.default_backend)}</b> · rooms on port ${room.port}.</p></div>
      </div>
      <div id="home-running"></div>
      <div class="starts">
        <form class="box start" data-start="play">
          <div class="start-head"><span class="sico duel">${ICONS.duel}</span><div><h2>Duel the agent</h2><p class="lead">It hosts a room; you join from EDOPro and play. Its reasoning shows here move by move.</p></div></div>
          <div class="row">${field("Its deck", `<select name="deck">${deckOptions()}</select>`)}${field("Backend", `<select name="backend">${backendOptions()}</select>`)}${field("Best of", seg("best_of", [1, 3, 5], 1), "narrow")}</div>
          <details class="moreopts"><summary>More options</summary>
            <div class="row">${field("Room password", `<input name="password" maxlength="20" placeholder="none">`)}${field("Your seconds per turn", `<input name="time_limit" type="number" min="0" max="7200" placeholder="${room.time_limit}">`)}</div>
            <label class="check"><input type="checkbox" name="join" ${I.join_available ? "" : "disabled"}> Legacy: I host the room in EDOPro and the agent's bot (the WindBot fork) joins it${I.join_available ? "" : " — needs <code>./build.sh</code>"}</label>
          </details>
          <ul class="howto"><li>Open the room, then join it from EDOPro with your own deck.</li><li>Its reasoning and plan for the turn show on the board as it plays.</li><li>A bad move? Leave a note (the board's note box, or <code>!note</code> in the duel chat): <b>Learn</b> on the deck's page turns notes into playbook fixes.</li></ul>
          <div class="start-foot"><button class="btn primary" type="submit">Open the room</button><span class="hint">Then in EDOPro: LAN Mode → host <b>127.0.0.1</b>, port <b>${room.port}</b> → Join.</span></div>
        </form>
        <form class="box start" data-start="selfplay">
          <div class="start-head"><span class="sico watch">${ICONS.watch}</span><div><h2>Watch AI vs AI</h2><p class="lead">Two seats play each other: AI decks on any backend, or a WindBot deck AI.</p></div></div>
          <div class="seats"><div class="seat-l">A</div>${seatEditor("a", { kind: "agent", deck: I.default_deck, backend: I.default_backend })}<div class="seat-l">B</div>${seatEditor("b", oppInit)}</div>
          <div class="row">${field("Games", `<input name="games" type="number" min="1" max="50" value="1">`, "narrow")}${field("Pace (seconds)", `<input name="pace" type="number" min="0" max="30" step="0.5" placeholder="0">`, "narrow")}</div>
          <label class="check"><input type="checkbox" name="spectate"> Also watch in EDOPro (it waits for you to join as a spectator)</label>
          <div class="start-foot"><button class="btn primary" type="submit">Start</button><span class="hint">heuristic and random seats cost nothing.</span></div>
        </form>
        <form class="box start" data-start="teach">
          <div class="start-head"><span class="sico teach">${ICONS.teach}</span><div><h2>Watch it teach</h2><p class="lead">It plays a deck and explains every play and its plan for the turn, for someone learning the deck.</p></div></div>
          <div class="row">${field("Deck", `<select name="deck">${deckOptions()}</select>`)}${field("Backend", `<select name="backend">${backendOptions(null, { llmOnly: true })}</select>`)}</div>
          <div class="seats one"><div class="seat-l">vs</div>${seatEditor("opponent", oppInit)}</div>
          <div class="row">${field("Pace (seconds)", `<input name="pace" type="number" min="0" max="30" step="0.5" value="2">`, "narrow")}</div>
          <div class="start-foot"><button class="btn primary" type="submit">Start the lesson</button><span class="hint">Watch here, or join as a spectator in EDOPro (port ${room.port}).</span></div>
        </form>
        <form class="box start" data-start="coach">
          <div class="start-head"><span class="sico coach">${ICONS.coach}</span><div><h2>Get coached</h2><p class="lead">You play your deck in EDOPro; the coach advises every move here and reviews the game after.</p></div></div>
          <div class="row">${field("Your deck", `<select name="deck" title="The deck you submit in EDOPro is recognised; pick one to name it">${deckOptions(null, { blank: "Recognise it" })}</select>`)}${field("Coach", `<select name="backend">${backendOptions(null, { llmOnly: true })}</select>`)}${field("Advice", `<select name="level" title="beginner: the idea behind each move; intermediate: terse"><option value="beginner" ${I.coach.level === "beginner" ? "selected" : ""}>beginner</option><option value="intermediate" ${I.coach.level === "intermediate" ? "selected" : ""}>intermediate</option></select>`)}</div>
          <div class="seats one"><div class="seat-l">vs</div>${seatEditor("opponent", oppInit)}</div>
          <div class="start-foot"><button class="btn primary" type="submit">Open the room</button><span class="hint">${I.coach.time_limit}s per turn: reading the advice takes time.</span></div>
        </form>
      </div>
      <div class="cols2">
        <div class="box"><div class="box-head"><h2>Recent games</h2><a href="#/games" class="lnk" data-games>All games</a></div><div id="home-games" class="list"></div></div>
        <div class="box"><div class="box-head"><h2>Decks</h2><a href="#/new" class="lnk">${ICONS.plus} New deck</a></div><div id="home-decks" class="list"></div></div>
      </div>
    </div>`;
    const root = page();
    wireSeats(root);
    $("[data-games]", root).onclick = (e) => { e.preventDefault(); location.hash = "#/games"; setTimeout(showGames, 50); };
    for (const form of $$("form[data-start]", root)) form.onsubmit = (e) => { e.preventDefault(); submitStart(form); };
    renderHomeRunning();
    renderHomeDecks();
    loadHomeGames(p);
    every(p, 3000, renderHomeRunning);
  };

  async function submitStart(form) {
    const kind = form.dataset.start;
    const btn = $("button[type=submit]", form);
    let params;
    if (kind === "play") {
      params = { deck: val(form, "[name=deck]"), backend: val(form, "[name=backend]"), best_of: Number(segValue(form, "best_of") || 1),
        password: val(form, "[name=password]"), time_limit: num(form, "[name=time_limit]"), join: val(form, "[name=join]") };
    } else if (kind === "selfplay") {
      params = { a: readSeat(form, "a"), b: readSeat(form, "b"), games: num(form, "[name=games]") || 1, pace: num(form, "[name=pace]"), spectate: val(form, "[name=spectate]") };
    } else if (kind === "teach") {
      params = { deck: val(form, "[name=deck]"), backend: val(form, "[name=backend]"), opponent: readSeat(form, "opponent"), pace: num(form, "[name=pace]") };
    } else {
      params = { deck: val(form, "[name=deck]") || null, backend: val(form, "[name=backend]"), level: val(form, "[name=level]"), opponent: readSeat(form, "opponent") };
    }
    const job = await startJob(kind, params, btn);
    if (job) location.hash = `#/jobs/${job.id}`;
  }

  function jobRow(j) {
    const live = (j.games || []).filter((g) => g.live);
    return `<a class="jrow" href="#/jobs/${esc(j.id)}">
      <span class="jdot ${j.status}${j.waiting ? " waiting" : ""}"></span>
      <span class="jt"><b>${esc(j.title)}</b><small>${esc(KIND_LABEL[j.kind] || j.kind)} · ${j.running ? `running for ${dur(Date.now() / 1000 - j.started)}` : `${esc(j.status)}${j.code != null && j.code !== 0 ? ` (exit ${j.code})` : ""} · ${when(j.ended || j.started)}`}${j.waiting ? ` · <span class="warn-t">${esc(j.waiting.text)}</span>` : ""}</small></span>
      ${live.length ? `<span class="chip livechip">LIVE</span>` : ""}${statusChip(j)}</a>`;
  }
  function renderHomeRunning() {
    const box = $("#home-running");
    if (!box) return;
    const running = S.jobs.filter((j) => j.running);
    box.innerHTML = running.length ? `<div class="box running-box"><div class="box-head"><h2>Running now</h2><a class="lnk" href="#/jobs">All jobs</a></div><div class="list">${running.map(jobRow).join("")}</div></div>` : "";
  }
  function renderHomeDecks() {
    const box = $("#home-decks");
    if (!box) return;
    box.innerHTML = (S.decks || []).slice(0, 8).map(deckRow).join("") || `<div class="empty-note">No decks.</div>`;
  }
  async function loadHomeGames(p) {
    let data;
    try { data = await api("/api/games"); } catch { return; }
    if (!alive(p)) return;
    const live = (data.live || []).filter((g) => g.live).map((g) => `<button class="grow" data-live="${esc(g.game_id)}"><span class="gname">${esc(g.title)}</span><span class="gmeta">turn ${g.turn} · ${g.decisions} decisions</span><span class="chip livechip">LIVE</span></button>`);
    const rec = (data.recorded || []).slice(0, 7 - live.length).map((g) => `<button class="grow" data-rec="${esc(g.name)}"><span class="gname">${esc(g.deck_name || g.deck || "?")} <span class="vs">vs</span> ${esc(g.opponent || "?")}</span><span class="gmeta">${when(g.started) || esc(g.name)}${g.mode && g.mode !== "play" ? ` · ${esc(g.mode)}` : ""}${g.notes ? ` · ${plural(g.notes, "note")}` : ""}</span>${resultChip(g.result || "unfinished")}</button>`);
    const box = $("#home-games");
    box.innerHTML = [...live, ...rec].join("") || `<div class="empty-note">No games yet.</div>`;
    box.onclick = (e) => {
      const l = e.target.closest("[data-live]"), r = e.target.closest("[data-rec]");
      if (l) openGame(l.dataset.live);
      else if (r) openGame(null, r.dataset.rec);
    };
  }

  // ---------------------------------------------------------------- Decks

  function deckRow(d) {
    const train = d.train && d.train.status;
    return `<a class="drow" href="#/${d.training_only ? "new" : "decks"}/${encodeURIComponent(d.key)}">
      <span class="dname"><b>${esc(d.name)}</b>${d.name.toLowerCase() !== d.key.toLowerCase() ? `<small>${esc(d.key)}</small>` : ""}</span>
      <span class="dmeta">${d.training_only ? "being set up for training" : `${d.playbook_bytes ? `playbook ${(d.playbook_bytes / 1024).toFixed(1)} KB` : "no playbook"} · ${plural(d.tests, "case")}${d.tips ? ` · ${plural(d.tips, "tip")}` : ""}`}</span>
      ${d.pending_notes ? `<span class="chip notechip" title="Notes waiting for Learn">${plural(d.pending_notes, "note")}</span>` : ""}
      ${train ? `<span class="chip">${train === "done" ? "trained" : esc(train)}</span>` : ""}
      <span class="chip loc">${esc(d.location || "")}</span></a>`;
  }

  PAGES.decks = async (p) => {
    await Promise.all([loadInfo(), loadDecks(true)]);
    if (!alive(p)) return;
    const rows = S.decks;
    page().innerHTML = `<div class="pg">
      <div class="pg-head"><h1>Decks</h1><span class="sub" title="${esc(S.info.decks_dirs.repo)} and ${esc(S.info.decks_dirs.user)}">${rows.filter((d) => d.location === "repo").length} in the repo, ${rows.filter((d) => d.location !== "repo").length} of your own</span><div class="spacer"></div><a class="btn primary" href="#/new">${ICONS.plus}<span>New deck</span></a></div>
      <div class="deckgrid">${rows.map((d) => `<a class="box dcard" href="#/${d.training_only ? "new" : "decks"}/${encodeURIComponent(d.key)}">
        <div class="dc-top"><h2>${esc(d.name)}</h2><span class="chip loc">${esc(d.location || "")}</span></div>
        <div class="dc-stats">
          <span><b>${d.playbook_bytes ? (d.playbook_bytes / 1024).toFixed(1) + " KB" : "–"}</b>playbook</span>
          <span><b>${d.tests}</b>cases</span><span><b>${d.rules == null ? "?" : d.rules}</b>rules</span><span><b>${d.tips}</b>tips</span><span><b>${d.games}</b>games</span>
        </div>
        <div class="dc-foot">${d.pending_notes ? `<span class="chip notechip">${plural(d.pending_notes, "note")} to learn</span>` : `<span class="dim">no pending notes</span>`}
          ${d.train ? `<span class="chip">${d.train.status === "done" ? "trained" : esc(d.train.status || "training")}</span>` : ""}
          ${d.last_game ? `<span class="dim">last game ${when(d.last_game.started)} ${resultChip(d.last_game.result)}</span>` : ""}
          ${d.training_only ? `<span class="chip">being set up for training</span>` : ""}${!d.ydk_ok && !d.training_only ? `<span class="chip badchip">.ydk missing</span>` : ""}</div>
      </a>`).join("")}
      <a class="box dcard newcard" href="#/new"><span class="sico">${ICONS.plus}</span><h2>Train a new deck</h2><p class="lead">Give it a .ydk: it reads the cards, asks you a few questions, writes a playbook and practises.</p></a></div>
    </div>`;
  };

  PAGES.deck = async (p, name) => {
    await loadInfo();
    const d = await api(`/api/decks/${encodeURIComponent(name)}`);
    if (!alive(p)) return;
    if (d.training_only && !d.playbook) { location.hash = `#/new/${encodeURIComponent(d.key)}`; return; }
    S.deck = d;
    const pendingGames = new Set(d.pending.map((n) => n.game)).size;
    const learnJob = d.jobs.find((j) => j.kind === "learn" && j.running);
    page().innerHTML = `<div class="pg deckpage">
      <div class="pg-head"><a class="backlink" href="#/decks">Decks</a><h1>${esc(d.name || d.key)}</h1><span class="chip loc">${esc(d.location || "")}</span><span class="sub mono">${esc(d.dir)}</span>
        <div class="spacer"></div><button class="btn" data-duel>Duel it</button></div>
      <div class="deckcols">
        <div class="deckmain">
          <div class="box playbook-box"><div class="box-head"><h2>Playbook</h2><span class="dim">${d.playbook ? `${(new Blob([d.playbook]).size / 1024).toFixed(1)} KB · read by the play model on every decision` : "none yet"}</span><div class="spacer"></div><button class="btn" data-edit ${d.busy ? "disabled title='A job is changing this deck'" : ""}>Edit</button></div>
            <div id="pb-view" class="mdoc">${d.playbook ? mdDoc(d.playbook) : `<p class="dim">No playbook.md yet. Train the deck, or write one with Edit.</p>`}</div>
            <div id="pb-edit" class="hidden"><textarea id="pb-text" spellcheck="false"></textarea>
              <div class="edit-foot"><span class="dim">The previous version is kept in <code>train/history/</code>. Keep it tight (≤ 8 KB): principles first, Known pitfalls at the bottom.</span><div class="spacer"></div><button class="btn" data-cancel>Cancel</button><button class="btn primary" data-save>Save</button></div></div>
          </div>
          ${d.report ? `<div class="box"><details class="report"><summary><h2>Training report</h2><span class="dim">${esc(d.report.path)}</span></summary><div class="mdoc">${mdDoc(d.report.markdown)}</div></details></div>` : ""}
        </div>
        <div class="deckside">
          <div class="box learnbox"><div class="box-head"><h2>Learn from your notes</h2></div>
            <p class="lead">Notes you leave on this deck's games (the note box on the board, or <code>!note</code> in EDOPro's chat) wait here. <b>Learn</b> reads each one with the decision it follows, the playbook, your tips and the card scripts; fixes the playbook (a principle, or a Known pitfall), saves a regression case, and marks the note learned (or says why it disagrees). It never plays games.</p>
            <div class="learn-row"><div class="big">${d.pending.length}<small>${d.pending.length === 1 ? "note" : "notes"} in ${plural(pendingGames, "game")}</small></div>
              ${learnJob ? `<a class="btn" href="#/jobs/${esc(learnJob.id)}">Learning… (open)</a>` : `<button class="btn primary" data-learn ${d.pending.length || d.tips_changed ? "" : "disabled"}>Learn</button>`}</div>
            ${d.tips_changed ? `<p class="hint">Your tips changed since the last Learn; it folds them in too.</p>` : ""}
            <p class="hint">Roughly $1 of API-price usage and 2–4 minutes per game with notes (Opus reviewer; a Claude Code login isn't billed per call).${d.other_pending ? ` ${plural(d.other_pending, "note")} from spectators or AI opponents ${d.other_pending === 1 ? "is" : "are"} left out.` : ""}</p>
            <div class="notes">${d.pending.map((n) => `<div class="noteitem"><div>${esc(n.text)}</div><small>${esc(n.context)} · ${esc(n.author)} · <a href="#" data-note="${esc(n.key)}">${n.decision ? `open at decision #${n.decision}` : "open the game"}</a></small></div>`).join("")}</div>
          </div>
          <div class="box"><div class="box-head"><h2>Your tips</h2><span class="dim">${plural(d.tips_entries.length, "tip")}</span></div>
            <p class="lead">Your own advice about the deck, kept word for word in <code>tips.md</code>. Training writes the playbook from it; Learn folds in new ones.</p>
            <div class="tips">${d.tips_entries.map((t) => `<div class="tip"><b>${esc(t.title)}</b>${t.date ? `<small>${esc(t.date)}</small>` : ""}<div class="mdoc small">${mdDoc(t.text)}</div></div>`).join("") || `<div class="dim">No tips yet.</div>`}</div>
            <form class="addtip"><textarea name="text" rows="3" maxlength="4000" placeholder="Add a tip, e.g. “Keep Gold Gadget for a turn you can Xyz”"></textarea><div class="edit-foot"><div class="spacer"></div><button class="btn" type="submit">Add the tip</button></div></form>
          </div>
          <div class="box"><div class="box-head"><h2>Games</h2><span class="dim">${plural(d.games_list.length, "recent game")}</span></div><div class="list">${d.games_list.map((g) => `<button class="grow" data-rec="${esc(g.name)}"><span class="gname">vs ${esc(g.opponent || "?")}</span><span class="gmeta">${when(g.started)} · ${esc(g.mode || "play")}${g.backend ? ` · ${esc(g.backend)}` : ""}${g.notes ? ` · ${plural(g.notes, "note")}` : ""}</span>${resultChip(g.result || "unfinished")}</button>`).join("") || `<div class="dim">No games in ${esc(S.info.games_dir)} yet.</div>`}</div></div>
          ${d.jobs.length ? `<div class="box"><div class="box-head"><h2>Jobs on this deck</h2></div><div class="list">${d.jobs.map(jobRow).join("")}</div></div>` : ""}
          ${d.learn_log ? `<div class="box"><details><summary><h2>Learn log</h2></summary><div class="mdoc small">${mdDoc(d.learn_log)}</div></details></div>` : ""}
        </div>
      </div></div>`;
    const root = page();
    $("[data-duel]", root).onclick = () => { S.homeDeck = d.key; location.hash = "#/"; };
    const edit = $("[data-edit]", root);
    edit.onclick = () => { $("#pb-text").value = d.playbook || ""; $("#pb-view").classList.add("hidden"); $("#pb-edit").classList.remove("hidden"); edit.classList.add("hidden"); $("#pb-text").focus(); };
    $("[data-cancel]", root).onclick = () => { $("#pb-view").classList.remove("hidden"); $("#pb-edit").classList.add("hidden"); edit.classList.remove("hidden"); };
    $("[data-save]", root).onclick = async (e) => {
      e.target.disabled = true;
      try {
        const out = await api(`/api/decks/${encodeURIComponent(d.key)}/playbook`, { text: $("#pb-text").value, base: d.playbook_sha });
        notify(out.same ? "No changes" : "Playbook saved", out.history ? `The old one: ${out.history.split("/").slice(-3).join("/")}` : "");
        go();
      } catch (err) { notify("Not saved", err.message, [], "bad"); e.target.disabled = false; }
    };
    const learn = $("[data-learn]", root);
    if (learn) learn.onclick = async () => { const job = await startJob("learn", { deck: d.key }, learn); if (job) location.hash = `#/jobs/${job.id}`; };
    $("form.addtip", root).onsubmit = async (e) => {
      e.preventDefault();
      const text = e.target.text.value.trim();
      if (!text) return;
      try { await api(`/api/decks/${encodeURIComponent(d.key)}/tips`, { text }); notify("Tip added", "Learn folds it into the playbook."); go(); }
      catch (err) { notify("Not added", err.message, [], "bad"); }
    };
    root.onclick = (e) => {
      const r = e.target.closest("[data-rec]");
      if (r) return openGame(null, r.dataset.rec);
      const n = e.target.closest("[data-note]");
      if (n) {
        e.preventDefault();
        const note = d.pending.find((x) => x.key === n.dataset.note);
        if (note && note.recorded) openGame(null, note.recorded, note.decision);
        else notify("That game isn't in the games folder", note ? note.game_dir : "", [], "bad");
      }
    };
    if (d.busy) every(p, 4000, async () => { try { const n = await api(`/api/decks/${encodeURIComponent(name)}`); if (alive(p) && !n.busy) go(); } catch { /* next time */ } });
  };

  // ---------------------------------------------------------------- New deck: the train wizard

  // Measured per step on a Geargia training run with Opus (train/state.json's ledger, 2026-10-21): dollars at API
  // prices, seconds. A smaller player model costs less in the lab and the games.
  const STEP = { study: [1.2, 260], hand: [0.18, 45], labReview: [0.65, 105], game: [1.6, 280], review: [0.8, 160], condense: [0.3, 65], tests: [0.3, 95] };
  function modelScale(name) {
    const b = (S.info.backends.find((x) => x.name === name) || {});
    if (["heuristic", "random"].includes(b.type)) return 0;
    const m = String(b.model || name).toLowerCase();
    if (b.type === "openai") return 0;
    return m.includes("haiku") ? 0.08 : m.includes("sonnet") ? 0.5 : 1;
  }
  function trainEstimate(o) {
    const R = modelScale(o.backend), P = modelScale(o.player);
    const round = (hands, games) => ({
      cost: hands * STEP.hand[0] * P + (hands ? STEP.labReview[0] * R : 0) + games * (STEP.game[0] * P + STEP.review[0] * R) + STEP.condense[0] * R,
      secs: Math.ceil(hands / 3) * STEP.hand[1] + (hands ? STEP.labReview[1] : 0) + Math.ceil(games / 2) * STEP.game[1] + games * STEP.review[1] + STEP.condense[1],
    });
    const one = round(o.lab_hands, o.games), later = round(Math.ceil(o.lab_hands / 2), o.games);
    const base = { cost: STEP.study[0] * R + STEP.tests[0] * P, secs: STEP.study[1] + STEP.tests[1] };
    const lo = { cost: base.cost + one.cost, secs: base.secs + one.secs };
    const hi = { cost: lo.cost + (o.max_rounds - 1) * later.cost, secs: lo.secs + (o.max_rounds - 1) * later.secs };
    return { lo, hi, free: R === 0 && P === 0 };
  }
  const money = (x) => (x < 1 ? `$${x.toFixed(2)}` : `$${Math.round(x)}`);

  PAGES.new = async (p, name) => {
    await Promise.all([loadInfo(), loadDecks()]);
    if (!alive(p)) return;
    if (!name) return wizardStart(p);
    return wizardDeck(p, name);
  };

  function steps(at) {
    const names = ["The deck file", "Your answers", "Training", "The report"];
    return `<ol class="steps">${names.map((n, i) => `<li class="${i < at ? "done" : i === at ? "on" : ""}"><span>${i + 1}</span>${n}</li>`).join("")}</ol>`;
  }

  function wizardStart(p) {
    const I = S.info;
    page().innerHTML = `<div class="pg wizard">
      <div class="pg-head"><a class="backlink" href="#/decks">Decks</a><h1>Train a new deck</h1></div>
      ${steps(0)}
      <form class="box" id="wz1">
        <h2>Which deck?</h2>
        <p class="lead">A trained deck is a guidebook: <code>playbook.md</code>, the strategy the agent reads on every decision. First it reads every card and its script and asks you a few questions about how the deck plays; your answers become <code>tips.md</code>, and the playbook follows them.</p>
        <div class="row">${field("A deck from EDOPro's deck folder", `<select name="pick"><option value="">—</option>${I.edopro_decks.map((d) => `<option value="${esc(d.path)}">${esc(d.name)}</option>`).join("")}</select>`)}</div>
        <div class="row">${field("…or the path of a .ydk file", `<input name="ydk" placeholder="~/Games/ProjectIgnis/deck/My deck.ydk" spellcheck="false">`)}</div>
        <div class="row">${field("Name (its folder)", `<input name="name" maxlength="40" placeholder="e.g. chaos" spellcheck="false">`)}${field("Display name (optional)", `<input name="display" maxlength="60" placeholder="as the agent calls it">`)}</div>
        <p class="hint">It goes to your decks folder, <code>${esc(I.decks_dirs.user)}</code>. Reading the deck takes a minute or two and one reviewer call (${esc(I.trainer.backend)}).</p>
        <div class="start-foot"><button class="btn primary" type="submit">Read the deck</button></div>
      </form></div>`;
    const f = $("#wz1");
    const slug = (s) => s.replace(/\.ydk$/i, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
    const fill = (path) => {
      const base = path.split("/").pop();
      if (!f.name.value || f.name.dataset.auto) { f.name.value = slug(base); f.name.dataset.auto = "1"; }
      if (!f.display.value || f.display.dataset.auto) { f.display.value = base.replace(/\.ydk$/i, ""); f.display.dataset.auto = "1"; }
    };
    f.pick.onchange = () => { if (f.pick.value) { f.ydk.value = f.pick.value; fill(f.pick.value); } };
    f.ydk.oninput = () => { if (f.ydk.value.trim()) fill(f.ydk.value.trim()); };
    f.name.oninput = () => { delete f.name.dataset.auto; };
    f.display.oninput = () => { delete f.display.dataset.auto; };
    f.onsubmit = async (e) => {
      e.preventDefault();
      const name = f.name.value.trim();
      const job = await startJob("train-interview", { ydk: f.ydk.value.trim(), name, display_name: f.display.value.trim() || null }, $("button[type=submit]", f));
      if (job) location.hash = `#/new/${encodeURIComponent(name)}`;
    };
  }

  async function wizardDeck(p, name) {
    let d;
    await refreshJobs();  // a job that just ended must not show as running
    try { d = await api(`/api/decks/${encodeURIComponent(name)}`); }
    catch (e) {
      const job = S.jobs.find((j) => j.deck === name && j.kind === "train-interview");
      d = { key: name, jobs: job ? [job] : [], interview: null, train: null };
    }
    if (!alive(p)) return;
    const jobs = (d.jobs || []).slice().sort((a, b) => b.started - a.started);
    const interviewJob = jobs.find((j) => j.kind === "train-interview");
    const trainJob = jobs.find((j) => j.kind === "train");
    const head = `<div class="pg-head"><a class="backlink" href="#/decks">Decks</a><h1>Train ${esc(d.name || name)}</h1>${d.dir ? `<span class="sub mono">${esc(d.dir)}</span>` : ""}</div>`;
    const done = d.train && d.train.status === "done";
    if (trainJob && (trainJob.running || !done)) return wizardProgress(p, d, trainJob, head);
    if (done || (d.report && !trainJob)) return wizardReport(p, d, head);
    if (d.interview && !(interviewJob && interviewJob.running)) return wizardQuestions(p, d, head);
    if (interviewJob) {
      page().innerHTML = `<div class="pg wizard">${head}${steps(0)}
        <div class="box"><div class="box-head"><h2>${interviewJob.running ? "Reading the deck…" : interviewJob.status === "done" ? "Read" : "It stopped"}</h2>${statusChip(interviewJob)}<div class="spacer"></div><a class="lnk" href="#/jobs/${esc(interviewJob.id)}">the job</a></div>
        <p class="lead">${interviewJob.running ? "Every card and its script, then a few questions about how you play it. A minute or two." : interviewJob.status === "done" ? "No questions were written (train/interview.json is missing). The job's output says why." : "The job's output says why. Fix it and start again."}</p>
        <pre class="joblog short" id="wz-log"></pre>
        ${interviewJob.running ? "" : `<div class="start-foot"><a class="btn" href="#/new">Start again</a></div>`}</div></div>`;
      const log = logView($("#wz-log"), interviewJob.id, p);
      every(p, 1200, async () => {
        const j = await log.poll();
        if (j && !j.running && alive(p)) setTimeout(() => alive(p) && go(), 600);
      });
      return;
    }
    page().innerHTML = `<div class="pg wizard">${head}${steps(0)}<div class="box"><p>Nothing started for <b>${esc(name)}</b> yet.</p><a class="btn primary" href="#/new">Start</a></div></div>`;
  }

  function trainingOptions(I, prev = {}) {
    return `<div class="row">${field("Reviewer (writes and corrects the playbook)", `<select name="backend">${backendOptions(prev.backend || I.trainer.backend, { llmOnly: true })}</select>`)}${field("Player (plays the lab and the games)", `<select name="player_backend">${backendOptions(prev.player_backend || I.trainer.player_backend, { llmOnly: true })}</select>`)}</div>
      <div class="row">${field("Lab hands", `<input name="lab_hands" type="number" min="0" max="30" value="${prev.lab_hands ?? 6}">`, "narrow")}${field("Games per round", `<input name="games" type="number" min="0" max="10" value="${prev.games ?? 2}">`, "narrow")}${field("Rounds (at most)", `<input name="max_rounds" type="number" min="1" max="5" value="${prev.max_rounds ?? 1}">`, "narrow")}${field("Budget, USD", `<input name="budget_usd" type="number" min="0.5" max="500" step="0.5" value="${prev.budget_usd ?? ""}" placeholder="no cap">`, "narrow")}</div>
      <p class="hint" id="estimate"></p>`;
  }
  function readTraining(f) {
    return { backend: val(f, "[name=backend]"), player_backend: val(f, "[name=player_backend]"), lab_hands: num(f, "[name=lab_hands]") ?? 6,
      games: num(f, "[name=games]") ?? 2, max_rounds: num(f, "[name=max_rounds]") ?? 1, budget_usd: num(f, "[name=budget_usd]") };
  }
  function wireEstimate(f) {
    const upd = () => {
      const o = readTraining(f);
      o.player = o.player_backend;
      const e = trainEstimate(o);
      const range = (a, b, fmt) => (fmt(a) === fmt(b) ? fmt(a) : `${fmt(a)}–${fmt(b)}`);
      const mins = (a, b) => { const x = Math.max(1, Math.round(a / 60)), y = Math.max(1, Math.round(b / 60)); return x === y ? `${x} min` : `${x}–${y} min`; };
      $("#estimate", f).innerHTML = e.free ? `No API cost with these backends; about ${mins(e.lo.secs * 0.6, e.hi.secs)}.`
        : `About <b>${range(e.lo.cost * 0.8, e.hi.cost * 1.25, money)}</b> of API-price usage and <b>${mins(e.lo.secs * 0.8, e.hi.secs * 1.3)}</b> (an estimate from the steps of a Geargia run; a later round is skipped when the games show no significant mistakes). A budget, say $${Math.ceil(e.hi.cost * 1.5)}, stops it cleanly before going over. A Claude Code login isn't billed per call.`;
    };
    f.oninput = upd;
    f.onchange = upd;
    upd();
  }

  function wizardQuestions(p, d, head) {
    const I = S.info;
    const qs = (d.interview && d.interview.questions) || [];
    page().innerHTML = `<div class="pg wizard">${head}${steps(1)}
      <form class="box" id="wz2">
        <h2>A few questions about ${esc(d.name || d.key)}</h2>
        <p class="lead">Answer what you know, skip the rest. Your answers are saved word for word in <code>tips.md</code>; the playbook follows them unless a card's script says otherwise (then it lists the conflict as an open question for you).</p>
        <div class="qs">${qs.map((q, i) => `<label class="q"><span class="qt">${esc(q.question)}</span>${q.why ? `<small>${esc(q.why)}</small>` : ""}<textarea name="q${i}" rows="3" maxlength="4000"></textarea></label>`).join("")}</div>
        ${d.tips_entries && d.tips_entries.length ? `<p class="hint">tips.md already has ${plural(d.tips_entries.length, "tip")}; new answers are added to them.</p>` : ""}
        <h2 class="sp">Training</h2>
        <p class="lead">It writes the playbook from the cards and your answers, tests lines with stacked hands in a lab, plays a couple of games against WindBot deck AIs, reviews them and corrects the playbook. Light by default; more lab hands, games and rounds go deeper.</p>
        ${trainingOptions(I)}
        <div class="start-foot"><button class="btn primary" type="submit">Start training</button><span class="hint">You can stop it any time; it continues where it stopped.</span></div>
      </form></div>`;
    const f = $("#wz2");
    wireEstimate(f);
    f.onsubmit = async (e) => {
      e.preventDefault();
      const btn = $("button[type=submit]", f);
      const answers = qs.map((q, i) => ({ question: q.question, answer: f[`q${i}`].value.trim() })).filter((a) => a.answer);
      btn.disabled = true;
      try {
        if (answers.length) await api(`/api/decks/${encodeURIComponent(d.key)}/interview`, { answers });
      } catch (err) { notify("Your answers weren't saved", err.message, [], "bad"); btn.disabled = false; return; }
      const job = await startJob("train", { name: d.key, ...readTraining(f) }, btn);
      if (job && alive(p)) go();
    };
  }

  function wizardProgress(p, d, job, head) {
    const I = S.info;
    page().innerHTML = `<div class="pg wizard">${head}${steps(2)}
      <div class="box"><div class="box-head"><h2 id="wz-title"></h2><span id="wz-chip"></span><div class="spacer"></div><a class="lnk" href="#/jobs/${esc(job.id)}">the job</a><button class="btn danger" id="wz-stop">${ICONS.stop}<span>Stop</span></button></div>
        <p class="lead" id="wz-lead"></p>
        <div id="wz-games" class="gamechips"></div>
        <pre class="joblog" id="wz-log"></pre>
        <form id="wz-resume" class="hidden"><h2 class="sp">Continue training</h2>${trainingOptions(I, job.params)}<div class="start-foot"><button class="btn primary" type="submit">Resume</button></div></form>
      </div></div>`;
    const log = logView($("#wz-log"), job.id, p);
    const f = $("#wz-resume");
    wireEstimate(f);
    f.onsubmit = async (e) => { e.preventDefault(); const j = await startJob("train", { name: d.key, ...readTraining(f) }, $("button", f)); if (j && alive(p)) go(); };
    $("#wz-stop").onclick = async (e) => { e.currentTarget.disabled = true; try { await api(`/api/jobs/${job.id}/stop`, {}); } catch (err) { notify("Couldn't stop it", err.message, [], "bad"); } };
    const show = (j) => {
      $("#wz-title").textContent = j.running ? "Training…" : j.status === "done" ? "Trained" : "Training stopped";
      $("#wz-chip").innerHTML = statusChip(j);
      $("#wz-lead").textContent = j.running ? "The trainer's output below. Lab hands and games appear as live games you can open on the board." : j.status === "done" ? "Done: the report follows." : "It stopped before the end. Resume continues where it stopped (state.json keeps every finished step).";
      $("#wz-stop").classList.toggle("hidden", !j.running);
      f.classList.toggle("hidden", j.running || j.status === "done");
      $("#wz-games").innerHTML = gameChips(j);
    };
    show(job);
    $("#wz-games").onclick = gameChipClick;
    every(p, 1200, async () => {
      const j = await log.poll();
      if (!j || !alive(p)) return;
      show(j);
      if (!j.running && j.status === "done") setTimeout(() => alive(p) && go(), 800);
    });
  }
  function gameChips(j) {
    const seen = new Set();
    const games = (j.games || []).filter((g) => !seen.has(g.game_id) && seen.add(g.game_id));  // one per game, not per seat
    if (!games.length) return "";
    return `<span class="dim">Games:</span> ${games.map((g) => `<button class="gchip ${g.live ? "live" : ""}" data-game="${esc(g.game_id)}" data-recorded="${esc(g.recorded || "")}" ${g.on_bus || g.recorded ? "" : "disabled"}>${g.live ? '<span class="dot"></span>' : ""}${esc(g.title || g.name || g.game_id)}</button>`).join("")}`;
  }
  function gameChipClick(e) {
    const b = e.target.closest("[data-game]");
    if (b) openGame(b.dataset.game, b.dataset.recorded || null);
  }

  function wizardReport(p, d, head) {
    page().innerHTML = `<div class="pg wizard">${head}${steps(3)}
      <div class="box"><div class="box-head"><h2>Trained</h2>${d.train && d.train.cost ? `<span class="dim">${money(d.train.cost)} at API prices</span>` : ""}<div class="spacer"></div><a class="btn" href="#/decks/${encodeURIComponent(d.key)}">Open the deck</a><button class="btn primary" data-duel>Duel it</button></div>
        <p class="lead">What the run did and what to look at is below. Play it, and leave a note on any obvious mistake: <b>Learn</b> on the deck's page turns notes into playbook fixes.</p>
        <div class="mdoc">${d.report ? mdDoc(d.report.markdown) : `<p class="dim">No train-report.md was written.</p>`}</div></div></div>`;
    $("[data-duel]").onclick = () => { S.homeDeck = d.key; location.hash = "#/"; };
  }

  // ---------------------------------------------------------------- Jobs

  // A job's output, polled from where it left off. Starts at the last 64 KiB of a long log.
  function logView(pre, id, p) {
    let next = -1, last = null, busy = false;
    const v = {
      async poll() {
        if (busy) return last;
        busy = true;
        let data;
        try { data = await api(`/api/jobs/${encodeURIComponent(id)}?offset=${next}`); } catch { return last; } finally { busy = false; }
        if (!alive(p)) return null;
        const o = data.output;
        if (next === -1 && o.offset > 0) pre.append(el("span", "dim", `… the first ${Math.round(o.offset / 1024)} KB are in the log file\n`));
        if (o.text) {
          const stick = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 30;
          pre.append(document.createTextNode(o.text));
          if (stick) pre.scrollTop = pre.scrollHeight;
        }
        next = o.next;
        last = data.job;
        return last;
      },
    };
    v.poll();
    return v;
  }

  PAGES.jobs = async (p) => {
    await refreshJobs();
    if (!alive(p)) return;
    const render = () => {
      const running = S.jobs.filter((j) => j.running), past = S.jobs.filter((j) => !j.running);
      page().innerHTML = `<div class="pg">
        <div class="pg-head"><h1>Jobs</h1><span class="sub">The commands the app runs for you; output in <code>${esc((S.info && S.info.jobs_dir) || "")}</code></span></div>
        <div class="box"><div class="box-head"><h2>Running</h2></div><div class="list">${running.map(jobRow).join("") || `<div class="dim">Nothing running. Start something from <a href="#/">Home</a>.</div>`}</div></div>
        <div class="box"><div class="box-head"><h2>Recent</h2></div><div class="list">${past.map(jobRow).join("") || `<div class="dim">None yet.</div>`}</div></div></div>`;
    };
    await loadInfo();
    render();
    every(p, 2500, async () => { await refreshJobs(); if (alive(p)) render(); });
  };

  function joinBox(j) {
    const r = j.room;
    if (!r || !j.running) return "";
    if (r.kind === "join") {
      return `<div class="joinbox"><span class="sico">${ICONS.room}</span><div><h2>Host the room in EDOPro</h2>
        <ol><li>In EDOPro: <b>LAN Mode → Host Duel</b>, with a long time limit (or none), and wait in the room.</li>
        <li>Press <b>The room is open: send the bot</b> below; the agent's bot joins ${esc(r.host)}:${r.port}.</li></ol></div></div>`;
    }
    const who = r.spectator ? "as a <b>spectator</b> (both duelist seats are taken)" : "and take the free duelist seat with your deck";
    return `<div class="joinbox"><span class="sico">${ICONS.room}</span><div><h2>Join from EDOPro</h2>
      <ol><li><b>LAN Mode</b>, then type the host address <b class="mono">127.0.0.1</b> and port <b class="mono">${r.port}</b> and press <b>Join</b> ${who}.</li>
      <li>Type the address: EDOPro's room list may not show the room, and its Refresh button can crash EDOPro.</li>
      ${r.password ? `<li>Password: <b class="mono">${esc(r.password)}</b></li>` : ""}
      ${r.spectator ? "" : "<li>Pick your deck and ready up; the duel starts.</li>"}</ol>
      <p class="dim">Room “${esc(r.name)}”. From another machine on your network, use this machine's address instead of 127.0.0.1.</p></div></div>`;
  }

  PAGES.job = async (p, id) => {
    await loadInfo();
    const first = await api(`/api/jobs/${encodeURIComponent(id)}`);
    if (!alive(p)) return;
    const j0 = first.job;
    page().innerHTML = `<div class="pg jobpage">
      <div class="pg-head"><a class="backlink" href="#/jobs">Jobs</a><h1>${esc(j0.title)}</h1><span id="jb-chip"></span><div class="spacer"></div>
        <button class="btn danger" id="jb-stop">${ICONS.stop}<span>Stop</span></button></div>
      <div class="cmdline"><code>${esc(j0.command)}</code><span class="dim" id="jb-when"></span></div>
      <div id="jb-join"></div>
      <div id="jb-wait"></div>
      <div id="jb-games"></div>
      <div id="jb-extra"></div>
      <div class="box"><div class="box-head"><h2>Output</h2><span class="dim mono">${esc(j0.log)}</span></div><pre class="joblog tall" id="jb-log"></pre></div>
    </div>`;
    const log = logView($("#jb-log"), id, p);
    $("#jb-stop").onclick = async (e) => {
      e.currentTarget.disabled = true;
      try { const { job } = await api(`/api/jobs/${encodeURIComponent(id)}/stop`, {}); show(job); }
      catch (err) { notify("Couldn't stop it", err.message, [], "bad"); }
    };
    $("#jb-games").onclick = gameChipClick;
    $("#jb-wait").onclick = async (e) => {
      const b = e.target.closest("[data-go]");
      if (!b) return;
      b.disabled = true;
      try { await api(`/api/jobs/${encodeURIComponent(id)}/go`, {}); } catch (err) { notify("Not sent", err.message, [], "bad"); b.disabled = false; }
    };
    let extraFor = null;
    const show = (j) => {
      $("#jb-chip").innerHTML = statusChip(j);
      $("#jb-stop").classList.toggle("hidden", !j.running);
      $("#jb-stop").disabled = j.status === "stopping";
      $("#jb-when").textContent = j.running ? `started ${when(j.started)}, running for ${dur(Date.now() / 1000 - j.started)}`
        : `${j.status}${j.code != null ? ` (exit ${j.code})` : ""} after ${dur((j.ended || j.started) - j.started)} · ${when(j.ended)}${j.error ? ` · ${j.error}` : ""}`;
      const join = joinBox(j);
      if ($("#jb-join")._html !== join) { $("#jb-join").innerHTML = join; $("#jb-join")._html = join; }
      const wait = j.waiting ? `<div class="waitbox"><span>${esc(j.waiting.text)}</span><button class="btn primary" data-go>${esc(j.waiting.button)}</button></div>` : "";
      if ($("#jb-wait")._html !== wait) { $("#jb-wait").innerHTML = wait; $("#jb-wait")._html = wait; }
      const live = (j.games || []).find((g) => g.live);
      const games = (j.games || []).length ? `<div class="box gamesbox ${live ? "haslive" : ""}"><div class="box-head"><h2>${live ? "Live now" : "Its games"}</h2>${live ? `<button class="btn primary" data-game="${esc(live.game_id)}" data-recorded="${esc(live.recorded || "")}">Watch on the board</button>` : ""}</div><div class="gamechips">${gameChips(j)}</div></div>` : "";
      if ($("#jb-games")._html !== games) { $("#jb-games").innerHTML = games; $("#jb-games")._html = games; }
      const extraKey = `${j.status}:${j.deck}`;
      if (extraFor !== extraKey) { extraFor = extraKey; renderJobExtra(j); }
    };
    show(j0);
    every(p, 1000, async () => { const j = await log.poll(); if (j && alive(p)) show(j); });
  };

  function renderJobExtra(j) {
    const box = $("#jb-extra");
    if (!box) return;
    let html = "";
    if (j.kind === "doctor" && !j.running) html = `<div class="box"><div class="box-head"><h2>Results</h2><a class="lnk" href="#/setup">Setup</a></div>${doctorTable(j.result)}</div>`;
    else if (j.kind === "train-interview" && j.deck) html = `<div class="box next"><span>${j.running ? "Reading the deck…" : j.status === "done" ? "The questions are ready." : "The interview stopped."}</span><a class="btn primary" href="#/new/${encodeURIComponent(j.deck)}">Open the wizard</a></div>`;
    else if (j.kind === "train" && j.deck) html = `<div class="box next"><span>${j.running ? "Training: the wizard shows its progress and games." : j.status === "done" ? "Trained." : "Training stopped; the wizard can resume it."}</span><a class="btn primary" href="#/new/${encodeURIComponent(j.deck)}">Open the wizard</a></div>`;
    else if (j.kind === "learn" && j.deck) html = `<div class="box next"><span>${j.running ? "Learning from the notes on " + esc(j.deck) + "…" : "Learn " + esc(j.status) + "."}</span><a class="btn primary" href="#/decks/${encodeURIComponent(j.deck)}">Open the deck</a></div>`;
    box.innerHTML = html;
  }

  // ---------------------------------------------------------------- Setup

  function doctorTable(results) {
    if (!results) return `<p class="dim">No results (the output below says why).</p>`;
    const counts = { ok: 0, warn: 0, FAIL: 0, skip: 0 };
    for (const r of results) counts[r.status] = (counts[r.status] || 0) + 1;
    return `<p class="lead">${counts.ok} ok, ${plural(counts.warn, "warning")}, ${plural(counts.FAIL, "failure")}${counts.skip ? `, ${counts.skip} skipped` : ""}.</p>
      <div class="checks">${results.map((r) => `<div class="check-row ${r.status === "FAIL" ? "fail" : r.status}"><span class="st">${esc(r.status)}</span><b>${esc(r.name)}</b><span class="det">${esc(r.detail)}${r.hint ? `<small>→ ${esc(r.hint)}</small>` : ""}</span></div>`).join("")}</div>`;
  }

  PAGES.setup = async (p) => {
    const I = await loadInfo();
    await refreshJobs();
    if (!alive(p)) return;
    const last = S.jobs.find((j) => j.kind === "doctor");
    page().innerHTML = `<div class="pg setup">
      <div class="pg-head"><h1>Setup</h1><span class="sub">ygo-agent ${esc(I.version || "")} in <code>${esc(I.root)}</code></span></div>
      <div class="box"><div class="box-head"><h2>Checks</h2><span class="dim" id="dr-when"></span><div class="spacer"></div><button class="btn primary" id="dr-run">Run the checks</button></div>
        <div id="dr-out"><p class="dim">The same as <code>ygo-agent doctor</code>: Python, the config, EDOPro and its core, mono and WindBot, every backend profile and deck, the ports.</p></div></div>
      <div class="cols2">
        <div class="box"><div class="box-head"><h2>Backends</h2><span class="dim">default: <b>${esc(I.default_backend)}</b></span></div>
          <div class="table"><table><thead><tr><th>profile</th><th>type</th><th>model</th><th></th></tr></thead><tbody>${I.backends.map((b) => `<tr><td><b>${esc(b.name)}</b></td><td>${esc(b.type)}</td><td>${esc(b.model || "–")}${b.effort ? ` · ${esc(b.effort)}` : ""}</td><td>${b.ok ? `<span class="okt">ready</span>` : `<span class="badt" title="${esc(b.problem)}">${esc(b.problem)}</span>`}</td></tr>`).join("")}</tbody></table></div>
          <p class="hint">Profiles are <code>[backends.NAME]</code> tables in the config (docs/backends.md). WindBot deck AIs legal under ${esc(I.rules)}: ${I.windbots.map((w) => esc(w.name)).join(", ") || "none"}${I.windbot_problems.length ? ` (${esc(I.windbot_problems.length)} left out)` : ""}.</p></div>
        <div class="box"><div class="box-head"><h2>Where things are</h2></div>
          <dl class="paths">
            <dt>Defaults</dt><dd><code>${esc(I.config.default)}</code></dd>
            <dt>Your config</dt><dd><code>${esc(I.config.local)}</code> ${I.config.local_exists ? "" : `<span class="dim">(not created yet)</span>`}</dd>
            <dt>Decks</dt><dd><code>${esc(I.decks_dirs.repo)}</code> and <code>${esc(I.decks_dirs.user)}</code></dd>
            <dt>Games</dt><dd><code>${esc(I.games_dir)}</code></dd>
            <dt>EDOPro</dt><dd><code>${esc(I.edopro_dir)}</code></dd>
            <dt>Job output</dt><dd><code>${esc(I.jobs_dir)}</code></dd>
          </dl></div>
      </div>
      <div class="box"><div class="box-head"><h2>Changing the settings</h2></div>
        <p class="lead"><code>config/default.toml</code> has every setting with a comment. Don't edit it: put your changes in <code>config.local.toml</code> at the repo root (same layout, only the keys you change; git ignores it), then restart <code>ygo-agent web</code>. For example, to play the EDOPro copy of a deck (so edits in EDOPro's deck editor carry over) and add a local model through Ollama:</p>
        <pre class="snippet">[decks.saffira]
ydk = "~/Games/ProjectIgnis/deck/Saffira.ydk"

[backends.qwen]
type = "openai"
base_url = "http://localhost:11434/v1"
model = "qwen3:14b"
card_texts = "compact"</pre></div>
    </div>`;
    const showResult = (j) => {
      $("#dr-when").textContent = j.running ? "running…" : `${when(j.ended)}`;
      $("#dr-run").disabled = j.running;
      if (!j.running) $("#dr-out").innerHTML = doctorTable(j.result);
      else $("#dr-out").innerHTML = `<p class="dim">Checking…</p>`;
    };
    const watch = (job) => {
      showResult(job);
      if (!job.running) return;
      const t = setInterval(async () => {
        if (!alive(p)) return clearInterval(t);
        const { job: j } = await api(`/api/jobs/${encodeURIComponent(job.id)}`);
        if (!alive(p)) return;
        if (!j.running) { clearInterval(t); showResult(j); }
      }, 700);
      p.timers.push(t);
    };
    $("#dr-run").onclick = async (e) => { const job = await startJob("doctor", {}, e.currentTarget); if (job) watch(job); };
    if (last) {
      const { job } = await api(`/api/jobs/${encodeURIComponent(last.id)}`);
      if (alive(p)) watch(job);
    } else {
      const job = await startJob("doctor", {}, $("#dr-run"));
      if (job && alive(p)) watch(job);
    }
  };

  // ---------------------------------------------------------------- the poll: the nav badge and new games

  async function refreshJobs() {
    try { S.jobs = (await api("/api/jobs")).jobs; } catch { return; }
    renderNavCount();
    for (const j of S.jobs) {
      for (const g of j.games || []) {
        if (S.seenGames.has(g.game_id)) continue;
        S.seenGames.add(g.game_id);
        if (!S.primed || !g.live) continue;
        const here = S.route && ((S.route.name === "job" && S.route.arg === j.id) || (S.route.name === "new" && S.route.arg === j.deck));
        if (here || (S.route && S.route.name === "games")) continue;
        notify(j.room ? "Your game started" : "A game started", `${j.title}: ${g.title || g.game_id}`,
          [{ label: "Watch it", primary: true, run: () => openGame(g.game_id, g.recorded) }, { label: "The job", run: () => { location.hash = `#/jobs/${j.id}`; } }]);
      }
    }
    S.primed = true;
  }
  function renderNavCount() {
    const n = S.jobs.filter((j) => j.running).length;
    const b = $("#nav-jobs");
    b.textContent = n;
    b.classList.toggle("hidden", !n);
  }

  // The viewer's own hooks: a game starting while an app page is on screen is the poll's to announce.
  app.hooks.gameStart = () => !app.viewer;

  // ---------------------------------------------------------------- start

  document.title = "ygo-agent";
  $("#nav").classList.remove("hidden");
  window.addEventListener("hashchange", go);
  // Home's "Duel it" from a deck page preselects that deck.
  const homeHook = PAGES.home;
  PAGES.home = async (p) => {
    await homeHook(p);
    if (S.homeDeck && alive(p)) {
      const sel = $("form[data-start=play] [name=deck]");
      if (sel) { sel.value = S.homeDeck; sel.closest("form").scrollIntoView({ block: "center" }); sel.closest("form").classList.add("flash"); }
      S.homeDeck = null;
    }
  };
  refreshJobs();
  setInterval(refreshJobs, 2500);
  go();
})();
