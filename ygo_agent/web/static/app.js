"use strict";
// ygo-agent panel. Vanilla JS, no build step, no network beyond this server. The message schema is in docs/web.md.

// ---------------------------------------------------------------- helpers

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const clone = (o) => (typeof structuredClone === "function" ? structuredClone(o) : JSON.parse(JSON.stringify(o)));
const fmtK = (n) => (n >= 10000 ? `${Math.round(n / 1000)}k` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
const store = {
  get(k, d) { try { const v = localStorage.getItem("ygo-panel:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("ygo-panel:" + k, JSON.stringify(v)); } catch { /* private mode */ } },
};

const ICON = {
  check: '<svg viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  warn: '<svg viewBox="0 0 16 16"><path d="M8 1.8l6.6 11.7H1.4z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M8 6v3.6M8 11.6v.2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  plan: '<svg viewBox="0 0 16 16"><path d="M3 3.5h10M3 8h10M3 12.5h6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  caret: '<svg viewBox="0 0 16 16"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  coach: '<svg viewBox="0 0 16 16"><path d="M1.5 6L8 3l6.5 3L8 9z" fill="currentColor"/><path d="M4 7.4v3.2c1.2 1.3 6.8 1.3 8 0V7.4" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
  pen: '<svg viewBox="0 0 16 16"><path d="M10.8 2.5l2.7 2.7-7.8 7.8-3.4.7.7-3.4z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>',
  play: "M6 4l10 6-10 6z",
  pause: "M5 4h3.5v12H5zM11.5 4H15v12h-3.5z",
};

// EDOPro constants (docs/decision-protocol.md).
const L = { DECK: 0x1, HAND: 0x2, MZONE: 0x4, SZONE: 0x8, GRAVE: 0x10, REMOVED: 0x20, EXTRA: 0x40, OVERLAY: 0x80, FZONE: 0x100, PZONE: 0x200 };
const TYPE = { MONSTER: 0x1, XYZ: 0x800000, LINK: 0x4000000 };
const PHASES = [[0x1, "DP"], [0x2, "SP"], [0x4, "M1"], [0xf8, "BP"], [0x100, "M2"], [0x200, "EP"]];
const KIND = {
  idle: "Main phase", battle: "Battle phase", chain: "Chain window", effect_yn: "Activate?", yesno: "Yes / no",
  go_first: "Go first?", select_card: "Select", tribute: "Tribute", select_unselect: "Select", select_sum: "Select",
  option: "Choose effect", position: "Position", place: "Zone", announce_card: "Declare card",
  announce_number: "Declare number", announce_attrib: "Declare attribute", announce_race: "Declare type", game_over: "Game over",
};
const YES_NO = { effect_yn: ["No", "Yes"], yesno: ["No", "Yes"], go_first: ["Go second", "Go first"] };
const RESULT = { win: "Victory", loss: "Defeat", draw: "Draw" };

// ---------------------------------------------------------------- state

const app = {
  game: null,
  es: null,
  live: [],            // games on the bus
  recorded: [],        // games/* on disk
  seat: 0,             // whose side is at the bottom of the board
  streamSeats: "all",  // which seats the reasoning stream shows (self-play)
  god: store.get("god", true),
  showAuto: store.get("showAuto", false),
  tab: "stream",
  cards: new Map(),    // code -> {n, t, atk, def, lv}
  names: new Map(),    // card name -> code
  info: new Map(),     // code -> Promise of /cardinfo
  playing: null,
  stick: true,         // the stream follows new decisions until the viewer scrolls up
  lastUpto: -1,
  prevLp: {},
  params: new URLSearchParams(location.search),
};

class GameView {
  constructor(id, mode) {
    this.id = id;
    this.mode = mode;          // live | demo | recorded
    this.msgs = [];
    this.lastSeq = 0;
    this.seats = new Map();    // seat -> {deck_name, label, opponent, result, ...}
    this.decs = [];            // decision records in message order
    this.byKey = new Map();
    this.cursor = null;        // index into timeline(), or null = follow the newest
    this.caughtUp = mode === "recorded";
  }
  seat(s) {
    if (!this.seats.has(s)) this.seats.set(s, { seat: s });
    return this.seats.get(s);
  }
  get multi() { return this.seats.size > 1; }
  get ended() { return [...this.seats.values()].length > 0 && [...this.seats.values()].every((s) => s.result); }
}

const key = (seat, id) => `${seat}:${id}`;
const visible = (rec) => rec.d.kind !== "place";

// ---------------------------------------------------------------- cards

function learnCards(map) {
  if (!map) return;
  for (const [k, v] of Object.entries(map)) {
    app.cards.set(+k, v);
    if (v.n && !app.names.has(v.n)) app.names.set(v.n, +k);
  }
}
const cardName = (id) => (app.cards.get(id) || {}).n || (id ? `#${id}` : "unknown card");
const pic = (id) => `/card/${id}.jpg`;

function cardInfo(id) {
  if (!app.info.has(id)) app.info.set(id, fetch(`/cardinfo/${id}`).then((r) => (r.ok ? r.json() : null)).catch(() => null));
  return app.info.get(id);
}

// Quoted card names in describe.py text become hoverable names.
function nameSpans(text) {
  return esc(text).replace(/&quot;(.+?)&quot;/g, (m, name) => {
    const raw = name.replace(/&amp;/g, "&").replace(/&#39;/g, "'");
    const id = app.names.get(raw);
    return id ? `<span class="cn" data-card="${id}">${name}</span>` : m;
  });
}
function splitEffect(text) {
  const k = text.indexOf(" — effect: ");
  return k < 0 ? [text, null] : [text.slice(0, k), text.slice(k + 11).replace(/^"|"$/g, "")];
}

// ---------------------------------------------------------------- the board model

function emptySide() {
  return { lp: 8000, hand: [], mz: Array(7).fill(null), sz: Array(8).fill(null), gy: [], ban: [], deck: 0, extra: [] };
}
function emptyState() {
  return { turn: 0, turn_player: 0, phase: 0, me: emptySide(), opp: emptySide(), chain: [] };
}
const sideOf = (st, c) => (c === 0 ? st.me : st.opp);

function pull(list, id, seq) {
  let k = id ? list.map((c) => c && c.id).lastIndexOf(id) : -1;
  if (k < 0 && seq >= 0 && seq < list.length && list[seq] && !list[seq].id) k = seq;
  if (k < 0) k = list.map((c) => c && c.id).lastIndexOf(0);
  if (k < 0) k = list.length - 1;
  return k >= 0 ? list.splice(k, 1)[0] : null;
}
function take(st, loc, id) {
  const s = sideOf(st, loc.c);
  if (loc.l & L.OVERLAY) {
    const xyz = s.mz[loc.s];
    if (xyz && xyz.ov && xyz.ov.length) {
      const k = xyz.ov.lastIndexOf(id);
      xyz.ov.splice(k >= 0 ? k : xyz.ov.length - 1, 1);
    }
    return null;
  }
  const zone = (arr, i) => { const c = arr[i]; arr[i] = null; return c; };
  switch (loc.l) {
    case L.MZONE: return zone(s.mz, loc.s);
    case L.SZONE: return zone(s.sz, loc.s);
    case L.FZONE: return zone(s.sz, 5);
    case L.PZONE: return zone(s.sz, 6 + (loc.s % 2));
    case L.DECK: s.deck = Math.max(0, s.deck - 1); return null;
    case L.HAND: return pull(s.hand, id, loc.s);
    case L.GRAVE: return pull(s.gy, id, -1);
    case L.REMOVED: return pull(s.ban, id, -1);
    case L.EXTRA: return pull(s.extra, id, -1);
  }
  return null;
}
function put(st, loc, id) {
  const s = sideOf(st, loc.c);
  const card = { id, c: loc.c, l: loc.l, s: loc.s, p: loc.p };
  if (loc.l & L.OVERLAY) { const xyz = s.mz[loc.s]; if (xyz) (xyz.ov = xyz.ov || []).push(id); return; }
  switch (loc.l) {
    case L.MZONE: s.mz[loc.s] = card; break;
    case L.SZONE: s.sz[loc.s] = card; break;
    case L.FZONE: s.sz[5] = card; break;
    case L.PZONE: s.sz[6 + (loc.s % 2)] = card; break;
    case L.DECK: s.deck += 1; break;
    case L.HAND: s.hand.push(card); break;
    case L.GRAVE: s.gy.push(card); break;
    case L.REMOVED: s.ban.push(card); break;
    case L.EXTRA: s.extra.push(card); break;
  }
}

function relocate(st, card) {
  if (!card || !card.id) return;
  for (const side of [st.me, st.opp]) {
    for (const zone of [side.mz, side.sz]) {
      const k = zone.findIndex((c) => c && c.id === card.id && !(c.c === card.c && c.s === card.s));
      if (k >= 0) { const [old] = zone.splice(k, 1, null); put(st, card, card.id); Object.assign(sideOf(st, card.c).mz[card.s] || {}, { atk: old.atk, def: old.def }); return; }
    }
  }
}

// The board between two decisions: the last decision's state plus the events since (resynced at every decision).
function applyEvent(st, ev, m) {
  switch (ev.e) {
    case "start": if (ev.lp) { st.me.lp = ev.lp[0]; st.opp.lp = ev.lp[1]; } break;
    case "new_turn": st.turn = ev.turn; st.turn_player = ev.player; break;
    case "new_phase": st.phase = ev.phase; break;
    case "draw": {
      const s = sideOf(st, ev.player);
      for (let i = 0; i < ev.count; i++) s.hand.push({ id: 0, c: ev.player, l: L.HAND, s: s.hand.length, p: 10 });
      s.deck = Math.max(0, s.deck - ev.count);
      break;
    }
    case "move": {
      const f = ev.from || {}, t = ev.to || {};
      if (f.l === t.l && f.c === t.c && [L.DECK, L.HAND, L.EXTRA].includes(f.l & 0x7f)) break;
      if (f.l === L.DECK && t.l === L.HAND && ev.reason & 0x2000000) break; // the draw event counted it
      if (f.l) take(st, f, ev.id);
      if (t.l) put(st, t, ev.id);
      break;
    }
    case "pos_change": {  // a monster changing position, or a Set Spell/Trap flipped face-up
      const s = sideOf(st, ev.c);
      const c = ev.l === L.SZONE ? s.sz[ev.s] : ev.l === L.FZONE ? s.sz[5] : ev.l == null || ev.l === L.MZONE ? s.mz[ev.s] : null;
      if (c) { c.p = ev.to; if (ev.id) c.id = ev.id; }
      break;
    }
    case "swap": for (const c of ev.cards || []) relocate(st, c); break; // native seats: control swaps
    case "counter": {  // native seats
      const at = ev.card || {};
      const zone = at.l === L.MZONE ? sideOf(st, at.c).mz : at.l === L.SZONE ? sideOf(st, at.c).sz : null;
      const card = zone && zone[at.s];
      if (!card) break;
      const list = card.ctr = (card.ctr || []).map((x) => [...x]);
      const k = list.findIndex((x) => x[0] === ev.type);
      const n = (k >= 0 ? list[k][1] : 0) + (ev.add ? ev.count : -ev.count);
      if (k >= 0) list[k][1] = Math.max(0, n);
      else if (n > 0) list.push([ev.type, n]);
      break;
    }
    case "damage": case "pay_lp": case "recover": case "lp": sideOf(st, ev.player).lp = ev.lp; break;
    case "chaining": {
      st.chain.push({ card: ev.card, id: ev.id, player: ev.player, desc: ev.desc, desc_text: m.desc_text });
      const c = ev.card;  // a face-down card activated on the field is face-up now
      const z = c && (c.l === L.MZONE ? sideOf(st, c.c).mz : c.l === L.SZONE ? sideOf(st, c.c).sz : null);
      const here = z && z[c.l === L.SZONE && c.s === 5 ? 5 : c.s];
      if (here && c.id && (!here.id || here.id === c.id)) { here.id = c.id; if (c.p) here.p = c.p; }
      break;
    }
    case "chain_solved": { const l = st.chain[ev.link - 1]; if (l) l.done = true; break; }
    case "chain_negated": case "chain_disabled": { const l = st.chain[ev.link - 1]; if (l) l.negated = true; break; }
    case "chain_end": st.chain = []; break;
    case "win": st.result = ev.result; break;
  }
}

function boardAt(g, seat, upto) {
  let start = -1, st = null;
  for (let k = g.decs.length - 1; k >= 0; k--) {
    const r = g.decs[k];
    if (r.i <= upto && r.seat === seat && r.d.state && r.d.state.me) { start = r.i; st = clone(r.d.state); break; }
  }
  if (!st) st = emptyState();
  st.chain = st.chain || [];
  for (let i = start + 1; i <= upto && i < g.msgs.length; i++) {
    const m = g.msgs[i];
    if (m.type === "event" && (m.seat || 0) === seat) applyEvent(st, m.ev, m);
  }
  return st;
}

// ---------------------------------------------------------------- the board view

const COLS = { mz: [2, 3, 4, 5, 6], sz: [2, 3, 4, 5, 6] };
const board = { zones: {}, built: false };

function buildBoard() {
  for (const side of ["opp", "me"]) {
    const root = $(`#side-${side}`);
    root.innerHTML = "";
    const mirror = (col) => (side === "opp" ? 9 - col : col);
    const handrow = el("div", "handrow");
    const plate = el("div", "plate");
    plate.innerHTML = `<div class="who"><div class="avatar"></div><div class="nm"><b></b><span></span></div><div class="lp">8000</div></div><div class="lpbar"><i class="ghost"></i><i class="fill"></i></div>`;
    handrow.append(plate, el("div", "hand"));
    board.zones[`${side}:plate`] = plate;
    board.zones[`${side}:hand`] = handrow.lastChild;
    // One grid per side: the monster row next to the middle of the board, the Spell/Trap row outside it, and the
    // banished pile in the outer column across both rows (mirrored for the opponent, as seen across the table).
    const grid = el("div", "grid");
    const mrow = side === "me" ? 1 : 2, srow = side === "me" ? 2 : 1;
    const zone = (row, name, col, label, cls = "") => {
      const z = el("div", `zone ${cls}`);
      z.style.gridColumn = mirror(col);
      z.style.gridRow = row;
      z.innerHTML = `<span class="lbl">${label}</span>`;
      grid.append(z);
      board.zones[`${side}:${name}`] = z;
      return z;
    };
    zone(mrow, "field", 1, "Field");
    COLS.mz.forEach((col, i) => zone(mrow, `mz${i}`, col, `M${i + 1}`));
    zone(mrow, "gy", 7, "GY", "pile");
    zone(srow, "extra", 1, "Extra", "pile");
    COLS.sz.forEach((col, i) => zone(srow, `sz${i}`, col, `S${i + 1}`));
    zone(srow, "deck", 7, "Deck", "pile");
    zone("1 / span 2", "ban", 8, "Banished", "pile ban");
    zone(srow, "pend", 8, "Pendulum", "pend hidden");
    for (const pile of ["gy", "ban", "extra", "deck"]) {
      const z = board.zones[`${side}:${pile}`];
      z.dataset.pile = { gy: "GY", ban: "Banished", extra: "Extra", deck: "Deck" }[pile];
      if (pile !== "deck") { z.classList.add("clickable"); z.addEventListener("click", () => showPile(side, pile)); }
    }
    if (side === "opp") root.append(handrow, grid);
    else root.append(grid, handrow);
  }
  $("#mid").innerHTML = `<div class="emz"></div><span class="turn">TURN <b id="turn-no">–</b></span><div class="phases">${PHASES.map(([, n]) => `<span>${n}</span>`).join("")}</div><span class="whose" id="whose"></span><div id="chain" class="chainbar hidden"></div>`;
  board.built = true;
}

function names(g) {
  const s = app.seat, mine = g.seat(s);
  const other = g.multi ? g.seat(1 - s) : null;
  const meName = mine.deck_name || mine.deck || "Agent";
  const oppName = other ? other.deck_name || other.deck || "Seat " + (1 - s) : mine.opponent || "Opponent";
  const coached = mine.mode === "coach" && !g.multi;
  return {
    me: [meName, coached ? `you · coach ${(mine.label || "").split(" (")[0]}`.trim() : mine.label || (mine.mode && mine.mode !== "play" ? mine.mode : "")],
    opp: [oppName, other ? other.label || "" : mine.opponent ? "opponent" : ""],
  };
}

function cardSig(c, extra = "") {
  return c ? [c.id, c.p, c.atk, c.def, (c.ov || []).length, c.dis ? 1 : 0, c.att ? 1 : 0, JSON.stringify(c.ctr || ""), extra].join("|") : "";
}

function cardEl(c, side, where) {
  const e = el("div", "card");
  const faceDown = (c.p & 0xa) && (where === "field");
  const hidden = !c.id || (faceDown && side === "opp");
  if (hidden) e.append(el("div", "back"));
  else {
    const img = el("img");
    img.src = pic(c.id);
    img.alt = cardName(c.id);
    img.draggable = false;
    e.append(img);
    e.dataset.card = c.id;
  }
  if (!c.id) e.classList.add("unknown");
  if (where === "field") {
    if (c.l === L.MZONE && (c.p === 4 || c.p === 8)) e.classList.add("def");
    if (faceDown && !hidden) e.classList.add("mine-set");
    if (c.dis) e.classList.add("negated");
  }
  return e;
}

function statsHtml(c) {
  const base = app.cards.get(c.id) || {};
  const t = base.t || 0;
  if (!(t & TYPE.MONSTER) && t) return "";
  const atk = c.atk ?? base.atk, def = c.def ?? base.def;
  if (atk == null) return "";
  const cls = (v, b) => (b == null || v == null || v === b ? "" : v > b ? "up" : "down");
  const defPos = c.p & 0xc;
  if (t & TYPE.LINK) return `<span class="${cls(atk, base.atk)}">${atk}</span>`;
  return `<span class="${defPos ? "off" : ""} ${cls(atk, base.atk)}">${atk}</span><span class="sep">/</span><span class="${defPos ? "" : "off"} ${cls(def, base.def)}">${def}</span>`;
}

function renderZone(z, c, side, opts = {}) {
  const sig = cardSig(c, `${opts.chainNo || ""}${opts.chainP || ""}`);
  if (z._sig === sig) return;
  const prevId = z._id;
  z._sig = sig;
  z._id = c ? c.id : null;
  $$(".card, .badges", z).forEach((n) => n.remove());
  z.classList.toggle("filled", !!c);
  if (!c) return;
  const card = cardEl(c, side, "field");
  if (opts.animate && prevId !== c.id) card.classList.add("enter");
  z.append(card);
  const badges = el("div", "badges");
  const faceDown = c.p & 0xa;
  if (c.l === L.MZONE && c.id && !faceDown) {
    const s = statsHtml(c);
    if (s) badges.insertAdjacentHTML("beforeend", `<div class="stats">${s}</div>`);
  }
  if (faceDown) badges.insertAdjacentHTML("beforeend", `<div class="tag">SET</div>`);
  if (c.ov && c.ov.length) badges.insertAdjacentHTML("beforeend", `<div class="ov" title="${c.ov.map(cardName).map(esc).join(", ")}">${c.ov.length}</div>`);
  if (c.dis) badges.insertAdjacentHTML("beforeend", `<div class="flag">NEG</div>`);
  const counters = (c.ctr || []).reduce((n, [, k]) => n + k, 0);  // native seats report counters
  if (counters) badges.insertAdjacentHTML("beforeend", `<div class="ctr" title="counters">${counters}</div>`);
  if (opts.chainNo) badges.insertAdjacentHTML("beforeend", `<div class="chain-no ${opts.chainP ? "p1" : ""}">${opts.chainNo}</div>`);
  z.append(badges);
}

function renderPile(z, list, side, kind, animate) {
  const top = kind === "deck" ? (list > 0 ? { id: 0, p: 0xa } : null) : list.length ? list[list.length - 1] : null;
  const count = kind === "deck" ? list : list.length;
  const faceDown = top && (kind === "extra" || (kind === "ban" && top.p & 0xa));
  const sig = `${top ? top.id : ""}|${count}|${faceDown ? 1 : 0}`;
  if (z._sig === sig) return;
  const prev = z._id;
  z._sig = sig;
  z._id = top ? top.id : null;
  $$(".card, .count", z).forEach((n) => n.remove());
  z.classList.toggle("filled", !!top);
  if (!top) return;
  const shown = faceDown || kind === "deck" ? { id: 0, p: 0xa } : top;
  const card = cardEl(shown, side, "pile");
  if (animate && prev !== top.id && kind !== "deck") card.classList.add("enter");
  z.append(card);
  z.insertAdjacentHTML("beforeend", `<span class="count"><em>${z.dataset.pile}</em>${count}</span>`);
}

function renderHand(container, cards, side, animate, highlight) {
  const sig = cards.map((c) => c.id).join(",") + `|${container.clientWidth}`;
  if (container._sig !== sig) {
    const prev = container._ids || [];
    container._sig = sig;
    container._ids = cards.map((c) => c.id);
    container.innerHTML = "";
    if (!cards.length) container.append(el("span", "empty-hand", side === "me" ? "no cards in hand" : ""));
    const remaining = [...prev];
    cards.forEach((c) => {
      const e = cardEl(c, side, "hand");
      const k = remaining.indexOf(c.id);
      if (k >= 0) remaining.splice(k, 1);
      else if (animate) e.classList.add("enter");
      container.append(e);
    });
    const kids = $$(".card", container);
    if (kids.length > 1) {
      const w = kids[0].getBoundingClientRect().width || 60;
      const avail = container.clientWidth - 8;
      const gap = Math.min(6, (avail - kids.length * w) / (kids.length - 1));
      kids.forEach((k, i) => { k.style.marginLeft = i ? `${gap}px` : "0"; });
    }
  }
  $$(".card", container).forEach((e, i) => e.classList.toggle("picked", highlight && highlight.has(i)));
}

function renderPlate(side, st, label, animate) {
  const plate = board.zones[`${side}:plate`];
  const s = side === "me" ? st.me : st.opp;
  const [name, sub] = label;
  $(".avatar", plate).textContent = (name || "?").replace(/[^A-Za-z0-9]/g, "").slice(0, 1).toUpperCase() || "?";
  $(".nm b", plate).textContent = name || "";
  $(".nm span", plate).textContent = sub || "";
  const lpEl = $(".lp", plate);
  const prev = app.prevLp[side];
  const lp = s.lp ?? 8000;
  const pct = Math.max(0, Math.min(100, (lp / 8000) * 100));
  $(".fill", plate).style.width = pct + "%";
  $(".ghost", plate).style.width = pct + "%";
  if (prev != null && prev !== lp && animate) {
    const diff = lp - prev;
    const f = el("span", `floater ${diff < 0 ? "dmg" : "gain"}`, `${diff > 0 ? "+" : "−"}${Math.abs(diff)}`);
    lpEl.append(f);
    setTimeout(() => f.remove(), 1700);
    if (diff < 0) { lpEl.classList.remove("hit"); void lpEl.offsetWidth; lpEl.classList.add("hit"); }
    tween(lpEl, prev, lp);
  } else if (!lpEl._tween) {
    lpEl.firstChild ? (lpEl.firstChild.nodeValue = String(lp)) : (lpEl.textContent = String(lp));
  }
  app.prevLp[side] = lp;
}

function tween(node, from, to) {
  const t0 = performance.now(), dur = 650;
  node._tween = true;
  const text = node.firstChild && node.firstChild.nodeType === 3 ? node.firstChild : node.insertBefore(document.createTextNode(""), node.firstChild);
  const step = (now) => {
    const k = Math.min(1, (now - t0) / dur);
    text.nodeValue = String(Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3))));
    if (k < 1) requestAnimationFrame(step);
    else node._tween = false;
  };
  requestAnimationFrame(step);
}

function chainMarks(st) {
  const marks = {};
  (st.chain || []).forEach((link, i) => {
    const c = link.card;
    if (!c || link.done) return;
    const side = c.c === 0 ? "me" : "opp";
    let zone = null;
    if (c.l === L.MZONE && c.s < 5) zone = `mz${c.s}`;
    else if (c.l === L.SZONE && c.s < 5) zone = `sz${c.s}`;
    else if ((c.l === L.SZONE && c.s === 5) || c.l === L.FZONE) zone = "field";
    else if (c.l === L.GRAVE) zone = "gy";
    if (zone) marks[`${side}:${zone}`] = { no: i + 1, p: link.player };
  });
  return marks;
}

function renderChain(st) {
  const box = $("#chain");
  const chain = st.chain || [];
  $("#mid").classList.toggle("chaining", chain.length > 0);
  if (!chain.length) { box.classList.add("hidden"); box._sig = ""; return; }
  const sig = JSON.stringify(chain.map((l) => [l.id, l.done, l.negated]));
  if (box._sig === sig) return;
  box._sig = sig;
  box.classList.remove("hidden");
  // Link 1 first; it resolves last (the arrows point the way the chain was built).
  const links = chain.map((l, i) => {
    const id = l.id || (l.card && l.card.id);
    const state = l.negated ? "negated" : l.done ? "resolved" : "";
    const older = chain.length > 3 && i < chain.length - 2;  // long chains: only the newest links keep their text
    return `<div class="link ${l.player ? "p1" : ""} ${l.done ? "done" : ""} ${l.negated ? "negated" : ""} ${older ? "older" : ""}" data-card="${id}" title="${esc(l.desc_text || "")}">
      <img src="${pic(id)}" alt=""><span class="cl">CL${i + 1}</span>
      <div class="t"><b>${esc(cardName(id))}</b><span>${esc(state || l.desc_text || "")}</span></div></div>`;
  });
  box.innerHTML = `<span class="chain-lbl">Chain</span>${links.join(`<span class="chain-arrow">${ICON.caret}</span>`)}`;
}

function renderBoard(animate) {
  const g = app.game;
  if (!g) return;
  if (!board.built) buildBoard();
  $("#board").classList.remove("empty");
  const upto = uptoIndex(g);
  const st = boardAt(g, app.seat, upto);
  // God view (self-play): the other seat's own state knows its hand.
  if (g.multi && app.god) {
    const other = boardAt(g, 1 - app.seat, upto);
    if (other.me && other.me.hand && other.me.hand.length === st.opp.hand.length) st.opp.hand = other.me.hand.map((c) => ({ ...c, c: 1 }));
  }
  const labels = names(g);
  const marks = chainMarks(st);
  const pending = pendingFor(g, upto);
  const optZones = new Set(), pickZones = new Set();
  const handPick = { me: new Set(), opp: new Set() };
  markOptions(pending, st, optZones, pickZones, handPick);
  for (const side of ["opp", "me"]) {
    const s = side === "me" ? st.me : st.opp;
    for (let i = 0; i < 5; i++) {
      const mk = marks[`${side}:mz${i}`], z = board.zones[`${side}:mz${i}`];
      renderZone(z, s.mz[i], side, { animate, chainNo: mk && mk.no, chainP: mk && mk.p });
      const sk = marks[`${side}:sz${i}`], y = board.zones[`${side}:sz${i}`];
      renderZone(y, s.sz[i], side, { animate, chainNo: sk && sk.no, chainP: sk && sk.p });
    }
    const fk = marks[`${side}:field`];
    renderZone(board.zones[`${side}:field`], s.sz[5], side, { animate, chainNo: fk && fk.no, chainP: fk && fk.p });
    const pend = board.zones[`${side}:pend`];
    const pz = s.sz[6] || s.sz[7];
    pend.classList.toggle("hidden", !pz);
    board.zones[`${side}:ban`].classList.toggle("short", !!pz);
    renderZone(pend, pz, side, { animate });
    renderPile(board.zones[`${side}:gy`], s.gy, side, "gy", animate);
    renderPile(board.zones[`${side}:ban`], s.ban, side, "ban", animate);
    renderPile(board.zones[`${side}:extra`], s.extra, side, "extra", animate);
    renderPile(board.zones[`${side}:deck`], s.deck, side, "deck", animate);
    renderHand(board.zones[`${side}:hand`], s.hand, side, animate, handPick[side]);
    renderPlate(side, st, labels[side], animate);
  }
  for (const [k, z] of Object.entries(board.zones)) {
    if (!z.classList || !z.classList.contains("zone")) continue;
    z.classList.toggle("opt", optZones.has(k));
    z.classList.toggle("picked", pickZones.has(k));
  }
  renderEmz(st, animate);
  $("#turn-no").textContent = st.turn || "–";
  const phaseSpans = $$(".phases span");
  PHASES.forEach(([bits], i) => phaseSpans[i].classList.toggle("on", !!(st.phase & bits)));
  const mine = st.turn_player === 0;
  $("#mid").classList.toggle("opp-turn", !mine && st.turn > 0);
  const whose = $("#whose");
  whose.className = `whose ${mine ? "me" : "opp"}`;
  whose.textContent = st.turn ? `${(mine ? labels.me : labels.opp)[0]}'s turn` : "Before the duel";
  renderChain(st);
  renderBanner(g, st, upto);
  app.board = st;
}

function renderEmz(st, animate) {
  const box = $("#mid .emz");
  const used = [st.me.mz[5], st.me.mz[6], st.opp.mz[5], st.opp.mz[6]].some(Boolean);
  if (!used) { box.innerHTML = ""; return; }
  box.innerHTML = "";
  const slots = [[st.me.mz[5] || st.opp.mz[6], 3], [st.me.mz[6] || st.opp.mz[5], 5]];
  for (const [c, col] of slots) {
    const z = el("div", "zone");
    z.style.gridColumn = col;
    z.style.height = "calc(var(--ch) * .9)";
    z.style.alignSelf = "center";
    box.append(z);
    if (c) renderZone(z, c, c.c === 0 ? "me" : "opp", { animate });
  }
}

function renderBanner(g, st, upto) {
  const b = $("#banner");
  const end = g.msgs.slice(0, upto + 1).reverse().find((m) => m.type === "game_end" && (m.seat || 0) === app.seat);
  if (!end || b._dismissed === g.id + upto) { b.classList.add("hidden"); return; }
  b.className = `banner ${end.result}`;
  b.innerHTML = `<b>${RESULT[end.result] || "Game over"}</b><span>${esc(end.reason_text || "")}</span>`;
  b.onclick = () => { b._dismissed = g.id + upto; b.classList.add("hidden"); };
}

// Which board cards a decision is about: its options while it's pending, its picks once answered.
function markOptions(rec, st, optZones, pickZones, handPick) {
  if (!rec || rec.seat !== app.seat) return;
  const d = rec.d, opts = d.options || [];
  const chosen = new Set(choiceOf(rec) || []);
  const answered = !!(rec.reply || rec.human);
  opts.forEach((o, i) => {
    const c = o && typeof o === "object" ? o.card || (o.id !== undefined && o.l !== undefined ? o : null) : null;
    if (!c) return;
    const side = c.c === 0 ? "me" : "opp";
    let zone = null;
    if (c.l === L.MZONE && c.s < 5) zone = `${side}:mz${c.s}`;
    else if (c.l === L.SZONE && c.s < 5) zone = `${side}:sz${c.s}`;
    else if (c.l === L.SZONE && c.s === 5) zone = `${side}:field`;
    else if (c.l === L.HAND && answered && chosen.has(i)) {
      const hand = (side === "me" ? st.me : st.opp).hand;
      const k = hand.findIndex((h, j) => h.id === c.id && !handPick[side].has(j));
      if (k >= 0) handPick[side].add(k);
    }
    if (!zone) return;
    if (answered && chosen.has(i)) pickZones.add(zone);
    else if (!answered) optZones.add(zone);
  });
}

// ---------------------------------------------------------------- the reasoning stream

const choiceOf = (rec) => (rec.reply ? rec.reply.choice : rec.human ? rec.human.choice : null);

function sourceBadge(rec, g) {
  const r = rec.reply;
  if (!r) return "";
  const s = r.source || "backend";
  let cls = s, text = s;
  if (s === "backend") text = r.label || g.seat(rec.seat).label || "model";
  else if (s.startsWith("rule")) { cls = "rule"; text = s.replace(/^rule:/, "rule · "); }
  else if (s === "human") text = "you";  // coach games: the human's own move
  else if (!["fallback", "pilot", "auto"].includes(s)) cls = "auto";
  return `<span class="src ${cls}" title="${esc(s)}">${esc(text)}</span>`;
}

function usageText(r) {
  if (!r) return "";
  const u = r.usage || {};
  const secs = r.seconds ?? u.seconds;
  const parts = [];
  if (secs != null) parts.push(`${(+secs).toFixed(1)}s`);
  const inp = (u.input_tokens || 0) + (u.cache_read_tokens || 0) + (u.cache_write_tokens || 0);
  if (inp) parts.push(`${fmtK(inp)} in`);
  if (u.output_tokens) parts.push(`${fmtK(u.output_tokens)} out`);
  return parts.join(" · ");
}

function headline(rec) {
  const d = rec.d, m = rec.m, q = m.question || "";
  const cut = (s) => { const k = s.search(/\s(Reply|You may reply)\b/); return k > 0 ? s.slice(0, k) : s; };
  switch (d.kind) {
    case "idle": return ["Choose the next action", null];
    case "battle": return ["Choose the next battle action", null];
    case "chain": return [d.forced ? "An activation is mandatory here" : "Respond with an effect, or pass", null];
    case "go_first": return ["Won the coin toss: go first or second?", null];
    case "select_card": case "tribute": case "select_sum": case "select_unselect": {
      const hint = m.hint_text || "Select card(s)";
      let sub = d.kind === "select_sum" ? `values adding up to ${d.exact ? "exactly" : "at least"} ${d.sum}`
        : d.min === d.max ? `pick ${d.min}` : `pick ${d.min}–${d.max}`;
      if (d.kind === "select_unselect") {
        sub = "picked one at a time";
        if (d.selected && d.selected.length) sub += ` · already: ${d.selected.map((c) => cardName(c.id)).join(", ")}`;
      }
      return [hint, sub];
    }
    default: return [cut(q), null];
  }
}

function optionThumb(o) {
  const c = o && typeof o === "object" ? o.card || o : null;
  if (c && c.id) return `<img class="th" src="${pic(c.id)}" alt="" data-card="${c.id}" loading="lazy">`;
  return `<span class="th blank"></span>`;
}

function optionsHtml(rec) {
  const d = rec.d, texts = rec.m.options || [];
  const chosen = choiceOf(rec) || [];
  const advised = rec.advice ? rec.advice.choice || [] : [];
  if (YES_NO[d.kind]) {
    const words = YES_NO[d.kind];
    return `<div class="yn">${[1, 0].map((v) => `<span class="${chosen.includes(v) ? "chosen" : ""} ${advised.includes(v) ? "advised" : ""}">${words[v]}</span>`).join("")}</div>`;
  }
  if (!texts.length) return "";
  const many = texts.length > 7 && !rec.expanded;
  const keep = new Set([...chosen, ...advised]);
  let shown = texts.map((t, i) => i);
  if (many) {
    shown = shown.filter((i) => keep.has(i));
    for (const i of texts.keys()) { if (shown.length >= 5) break; if (!keep.has(i)) shown.push(i); }
    shown.sort((a, b) => a - b);
  }
  const rows = shown.map((i) => {
    const [main, effect] = splitEffect(texts[i]);
    const order = chosen.indexOf(i);
    const marks = [];
    if (advised.includes(i)) marks.push(`<span class="coach">${ICON.coach}coach</span>`);
    if (order >= 0) marks.push(`<span class="pick">${chosen.length > 1 ? order + 1 : ICON.check}</span>`);
    return `<li class="opt ${order >= 0 ? "chosen" : ""} ${advised.includes(i) ? "advised" : ""}">
      <span class="ix">${i}</span>${optionThumb(d.options[i])}
      <span class="tx">${nameSpans(main)}${effect ? ` <span class="eff" style="color:var(--faint)">— ${esc(effect)}</span>` : ""}</span>
      <span class="mark">${marks.join("")}</span></li>`;
  });
  const more = many ? `<button class="more" data-more>+ ${texts.length - shown.length} more option${texts.length - shown.length > 1 ? "s" : ""}</button>` : "";
  return `<ul class="opts">${rows.join("")}</ul>${more}`;
}

function verdictHtml(rec) {
  const a = rec.advice;
  if (rec.human) {
    const late = a && a.hindsight ? `<span class="verdict late">looked back</span>` : a && a.late ? `<span class="verdict late">late</span>` : "";
    return late + (rec.human.matched ? `<span class="verdict match">followed coach</span>` : `<span class="verdict diverge">diverged</span>`);
  }
  if (a && a.choice != null && !(rec.reply && rec.reply.source === "human")) return `<span class="verdict late">coach</span>`;
  return "";
}

// Coach games: the coach's line under a decision (its pick is marked in the options).
const quietAdvice = (a) => !a || a.choice == null || a.source === "auto";
function coachHtml(rec, waiting) {
  const a = rec.advice;
  const wait = waiting ? `<div class="thinking"><span class="dots"><i></i><i></i><i></i></span>${waiting}</div>` : "";
  if (!a) return `<div class="thinking"><span class="dots"><i></i><i></i><i></i></span>coach is thinking</div>${wait}`;
  if (a.choice == null) {
    const why = a.source === "skipped" ? "no advice: you answered before the coach got to it" : a.source === "failed" ? `the coach had no usable advice${a.why ? ` (${a.why.replace(/^no usable advice:\s*/, "")})` : ""}` : "";
    return (why ? `<div class="coachline quiet"><b>Coach</b>${esc(why)}</div>` : "") + wait;
  }
  const when = a.hindsight ? "looking back" : a.late ? `late · ${(+a.after).toFixed(1)}s` : a.after != null ? `${(+a.after).toFixed(1)}s` : "";
  const usage = usageText({ usage: a.usage, seconds: null }).replace(/^[\d.]+s( · )?/, "");  // tokens; the time is `when`
  const rule = a.source && a.source.startsWith("rule") ? `<span class="src rule">${esc(a.source.replace(/^rule:/, "rule · "))}</span>` : "";
  const meta = `<span class="cmeta" title="after the decision · the coach's tokens">${esc(when)}${usage ? ` · ${esc(usage)}` : ""}</span>`;
  const plan = a.plan && !a.late ? `<div class="planned" data-plan>${ICON.plan}<span>The coach's plan${rec.planOpen ? "" : " (show)"}</span></div>${rec.planOpen ? `<div class="planned-body">${esc(a.plan)}</div>` : ""}` : "";
  return `<div class="coachline"><b>Coach</b>${rule}${meta}<div>${nameSpans(a.why || "")}</div></div>${plan}${wait}`;
}

function fillCard(card, rec) {
  const g = app.game, r = rec.reply;
  const src = r ? (r.source || "backend") : "";
  const coached = g.seat(rec.seat).mode === "coach" || src === "human";
  const auto = src === "auto" || (r && !r.why && !["backend", "fallback", "pilot", "human"].includes(src) && !src.startsWith("rule"))
    || (coached && (r ? r.trivial || (rec.advice && quietAdvice(rec.advice) && rec.advice.source === "auto") : rec.advice && rec.advice.source === "auto"));
  card.className = `dc src-${src.startsWith("rule") ? "rule" : src || "none"} ${auto ? "compact is-auto" : ""} ${!r && !rec.human ? "pending" : ""}`;
  card.dataset.i = rec.i;
  const [q, sub] = headline(rec);
  const seatB = g.multi ? `<span class="seatb s${rec.seat}">${esc(g.seat(rec.seat).deck_name || "seat " + rec.seat)}</span>` : "";
  const head = `<div class="hd"><span class="num">#${rec.d.id}</span><span class="kind">${KIND[rec.d.kind] || rec.d.kind}</span>${seatB}
    <span class="meta">${verdictHtml(rec)}<span class="usage">${usageText(r)}</span>${sourceBadge(rec, g)}</span></div>`;
  if (auto) {
    const chosen = choiceOf(rec) || [];
    const texts = rec.m.options || [];
    const what = YES_NO[rec.d.kind] ? YES_NO[rec.d.kind][chosen[0]] || "—" : chosen.map((k) => splitEffect(texts[k] || "")[0]).join(", ") || "pass";
    const quiet = r && r.source === "human" ? (rec.advice && rec.advice.why) || "" : r && r.why;
    card.innerHTML = r || rec.human ? `${head}<div class="q">${nameSpans(what)}${quiet ? ` <span style="color:var(--faint)">· ${esc(quiet)}</span>` : ""}</div>`
      : `${head}<div class="q" style="color:var(--faint)">waiting for your move</div>`;
    return;
  }
  const why = (r && r.why) || (rec.advice && rec.advice.why) || "";
  let body = `${head}<div class="q">${nameSpans(splitEffect(q)[0])}${sub ? `<span class="sub">${esc(sub)}</span>` : ""}</div>${optionsHtml(rec)}`;
  if (coached) {  // the human decides; the coach's line comes with it, before or after their move
    body += coachHtml(rec, r || rec.human ? "" : "waiting for your move");
    card.innerHTML = body;
    return;
  }
  if (!r && !rec.human) {
    body += rec.advice
      ? `<div class="coachline"><b>Coach</b>${esc(rec.advice.why || "")}</div><div class="thinking"><span class="dots"><i></i><i></i><i></i></span>waiting for the player</div>`
      : `<div class="thinking"><span class="dots"><i></i><i></i><i></i></span>thinking<span class="elapsed"></span></div>`;
  } else {
    if (why) body += `<div class="why">${nameSpans(why)}</div>`;
    if (rec.human && !rec.human.matched && rec.advice && rec.advice.why && r && r.why !== rec.advice.why) body += `<div class="coachline"><b>Coach</b>${esc(rec.advice.why)}</div>`;  // old copilot logs
    if (r && r.note) body += `<div class="note">${ICON.warn}<span>${esc(r.note)}</span></div>`;
    if (r && r.say) body += `<div class="note" style="color:var(--good)">${ICON.pen}<span>said in chat: “${esc(r.say)}”</span></div>`;
    if (r && r.plan) body += `<div class="planned" data-plan>${ICON.plan}<span>Plan for the turn${rec.planOpen ? "" : " (show)"}</span></div>${rec.planOpen ? `<div class="planned-body">${esc(r.plan)}</div>` : ""}`;
  }
  card.innerHTML = body;
}

function addTurnSep(g, rec) {
  const st = rec.d.state || {};
  const turn = st.turn || 0;
  if (!turn || turn === app.lastSepTurn) return;
  app.lastSepTurn = turn;
  const n = names(g);
  const mine = (rec.seat === app.seat) === (st.turn_player === 0);
  const sep = el("div", `turnsep ${mine ? "me" : "opp"}`, `<span class="pill">Turn ${turn} · ${esc((mine ? n.me : n.opp)[0])}</span>`);
  sep.dataset.i = rec.i;
  $("#stream").append(sep);
}

function showsInStream(g, rec) {
  return visible(rec) && (app.streamSeats === "all" || rec.seat === app.streamSeats);
}

function addDecision(g, rec, animate) {
  if (!showsInStream(g, rec)) return;
  addTurnSep(g, rec);
  const card = el("div", "dc");
  rec.el = card;
  fillCard(card, rec);
  if (animate) card.classList.add("new");
  $("#stream").append(card);
  $("#count-stream").textContent = String(g.decs.filter((r) => showsInStream(g, r)).length);
}

function addNote(g, m, animate) {
  const item = el("div", "fbitem", `${ICON.pen}<div>${esc(m.text)}<small>${esc(m.who || "Note")} · ${esc(m.context || "")}</small></div>`);
  item.dataset.i = m._i;
  if (animate) item.classList.add("new");
  $("#stream").append(item);
}

// ---------------------------------------------------------------- the coach's review

// The small Markdown the review uses: headings, lists, quotes, fenced blocks, paragraphs, **bold**, *italic*, `code`.
function mdInline(text) {
  return nameSpans(text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|[\s(])\*([^*\s][^*]*?)\*(?=[\s.,;:)!?]|$)/g, "$1<i>$2</i>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}
function markdown(text) {
  const out = [];
  let para = [], list = null;
  const flush = () => {
    if (para.length) { out.push(`<p>${mdInline(para.join(" "))}</p>`); para = []; }
    if (list) { out.push(`<${list.tag}>${list.items.join("")}</${list.tag}>`); list = null; }
  };
  let pre = null;
  for (const raw of String(text || "").split("\n")) {
    const line = raw.replace(/\s+$/, "");
    let m;
    if (/^```/.test(line)) {  // a fenced block: kept as it is (states, option lists)
      if (pre) { out.push(`<pre>${esc(pre.join("\n"))}</pre>`); pre = null; } else { flush(); pre = []; }
      continue;
    }
    if (pre) { pre.push(raw); continue; }
    if (!line.trim()) { flush(); continue; }
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flush(); const n = Math.min(4, m[1].length + 1); out.push(`<h${n}>${mdInline(m[2])}</h${n}>`); continue; }
    if ((m = line.match(/^(\s*)([-*]|\d+[.)])\s+(.*)$/))) {
      if (para.length) { out.push(`<p>${mdInline(para.join(" "))}</p>`); para = []; }
      const tag = /\d/.test(m[2]) ? "ol" : "ul";
      if (!list || list.tag !== tag) { if (list) flush(); list = { tag, items: [] }; }
      list.items.push(`<li class="${m[1].length >= 2 ? "sub" : ""}">${mdInline(m[3])}</li>`);
      continue;
    }
    if ((m = line.match(/^>\s?(.*)$/))) { flush(); out.push(`<blockquote>${mdInline(m[1])}</blockquote>`); continue; }
    if (list && /^\s{2,}\S/.test(raw)) { list.items[list.items.length - 1] = list.items[list.items.length - 1].replace(/<\/li>$/, ` ${mdInline(line.trim())}</li>`); continue; }
    if (list) flush();
    para.push(line.trim());
  }
  flush();
  if (pre) out.push(`<pre>${esc(pre.join("\n"))}</pre>`);
  return out.join("");
}
function renderReview() {
  const g = app.game, tab = $("#tab-review"), pane = $("#review");
  const m = g && g.review;
  tab.classList.toggle("hidden", !m);
  if (!m) { pane.innerHTML = ""; if (app.tab === "review") setTab("stream"); return; }
  const where = m.path ? `<div class="rv-foot">${esc(m.path)}${m.seconds ? ` · written in ${(+m.seconds).toFixed(0)}s` : ""}${m.label ? ` by ${esc(m.label)}` : ""}</div>` : "";
  pane.innerHTML = `<article class="review-doc">${markdown(m.markdown)}${where}</article>`;
}

// ---------------------------------------------------------------- the event log

const EV_CLASS = {
  new_turn: "turn", new_phase: "phase", chaining: "chain", summoning: "summon", damage: "damage", pay_lp: "damage",
  recover: "gain", attack: "attack", chat: "chat", win: "win", chain_solved: "resolved", chain_negated: "negated",
  chain_disabled: "negated", retry: "warn",
};
const evClass = (ev) => EV_CLASS[ev.e] || "";

function addLog(g, m) {
  if ((m.seat || 0) !== app.seat) return;
  let text = m.type === "event" ? m.text : null;
  let cls = m.type === "event" ? evClass(m.ev) : "";
  if (m.type === "reply" && m.say) { text = `${names(g).me[0]} says in chat: “${m.say}”`; cls = "chat"; }
  if (!text) return;
  const line = el("div", `ev ${cls ? "ev-" + cls : ""}`);
  line.dataset.i = m._i;
  if (cls === "turn") text = text.replace(/^=+\s*|\s*=+$/g, "");
  if (cls === "phase") text = text.replace(/^--\s*/, "");
  const [main, effect] = splitEffect(text.trim());
  line.innerHTML = `<span class="dot"></span><span>${nameSpans(main)}${effect ? ` <span style="color:var(--faint)">— ${esc(effect)}</span>` : ""}</span>`;
  $("#log").append(line);
  app.logCount = (app.logCount || 0) + 1;
  $("#count-log").textContent = String(app.logCount);
}

// ---------------------------------------------------------------- ingesting messages

function ingest(g, m, animate) {
  if (m.seq && g.mode !== "recorded") {
    if (m.seq <= g.lastSeq) return;
    g.lastSeq = m.seq;
  }
  learnCards(m.cards);
  m._i = g.msgs.push(m) - 1;
  const seat = m.seat || 0;
  const info = g.seat(seat);
  switch (m.type) {
    case "game_start": case "meta":
      for (const k of ["deck", "deck_name", "mode", "opponent", "first", "rules", "dir", "name", "result", "demo", "recorded"]) if (m[k] != null) info[k] = m[k];
      if (m.backend && m.backend.label) info.label = m.backend.label;
      if (g.msgs.length < 4 || m.type === "game_start") scheduleHeader();
      break;
    case "decision": {
      const rec = { seat, i: m._i, m, d: m.decision || {}, reply: null, advice: null, human: null };
      g.decs.push(rec);
      g.byKey.set(key(seat, rec.d.id), rec);
      addDecision(g, rec, animate);
      break;
    }
    case "reply": case "advice": case "human_choice": {
      const rec = g.byKey.get(key(seat, m.id));
      if (rec) {
        rec[m.type === "reply" ? "reply" : m.type === "advice" ? "advice" : "human"] = m;
        if (m.type === "reply") rec.ri = m._i;
        if (rec.el) fillCard(rec.el, rec);
        if (m.plan) schedulePlan();
      }
      if (m.type === "reply" && m.source === "backend" && m.label && !info.label) { info.label = m.label; scheduleHeader(); }
      if (m.type === "reply") addLog(g, m);
      break;
    }
    case "event":
      addLog(g, m);
      if (animate && seat === app.seat) effects(m);
      break;
    case "feedback_ack":
      addNote(g, m, animate);
      break;
    case "review":
      g.review = m;
      renderReview();
      if (animate) { toast("The coach's review is ready", "Open the Review tab", "good"); setTab("review"); }
      break;
    case "game_end":
      info.result = m.result;
      scheduleHeader();
      break;
  }
}

// ---------------------------------------------------------------- live effects

function zoneOf(c) {
  if (!c) return null;
  const side = c.c === 0 ? "me" : "opp";
  if (c.l === L.MZONE && c.s < 5) return board.zones[`${side}:mz${c.s}`];
  if (c.l === L.SZONE && c.s < 5) return board.zones[`${side}:sz${c.s}`];
  if (c.l === L.SZONE && c.s === 5) return board.zones[`${side}:field`];
  return null;
}

function effects(m) {
  const ev = m.ev;
  if (ev.e === "attack") requestAnimationFrame(() => arrow(zoneOf(ev.attacker), ev.target ? zoneOf(ev.target) : board.zones[`${ev.attacker.c === 0 ? "opp" : "me"}:plate`]));
  if (ev.e === "targeted") {
    requestAnimationFrame(() => {
      const z = zoneOf(ev.card);
      if (!z) return;
      z.classList.remove("targeted"); void z.offsetWidth; z.classList.add("targeted");
      setTimeout(() => z.classList.remove("targeted"), 1700);
    });
  }
}

function arrow(from, to) {
  if (!from || !to) return;
  const svg = $("#fx"), box = $("#board").getBoundingClientRect();
  const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
  const x1 = a.left + a.width / 2 - box.left, y1 = a.top + a.height / 2 - box.top;
  const x2 = b.left + b.width / 2 - box.left, y2 = b.top + b.height / 2 - box.top;
  const mx = (x1 + x2) / 2 + (y2 - y1) * 0.12, my = (y1 + y2) / 2 - (x2 - x1) * 0.12;
  const ang = Math.atan2(y2 - my, x2 - mx), s = 13;
  const ns = "http://www.w3.org/2000/svg";
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", `M${x1},${y1} Q${mx},${my} ${x2 - Math.cos(ang) * 10},${y2 - Math.sin(ang) * 10}`);
  path.setAttribute("class", "arrow");
  const head = document.createElementNS(ns, "path");
  head.setAttribute("d", `M${x2},${y2} L${x2 - s * Math.cos(ang - 0.45)},${y2 - s * Math.sin(ang - 0.45)} L${x2 - s * Math.cos(ang + 0.45)},${y2 - s * Math.sin(ang + 0.45)}z`);
  head.setAttribute("class", "arrow-head");
  svg.append(path, head);
  setTimeout(() => { path.remove(); head.remove(); }, 2000);
}

// ---------------------------------------------------------------- timeline and cursor

function timeline(g) {
  return g.decs.filter((r) => visible(r) && (app.streamSeats === "all" || r.seat === app.streamSeats));
}
function uptoIndex(g) {
  if (g.cursor == null) return g.msgs.length - 1;
  const t = timeline(g);
  const rec = t[Math.max(0, Math.min(g.cursor, t.length - 1))];
  if (!rec) return g.msgs.length - 1;
  // Through its reply (and the advice around it), so the card shows what was chosen.
  let upto = rec.ri ?? rec.i;
  while (upto + 1 < g.msgs.length && ["advice", "human_choice", "feedback_ack"].includes(g.msgs[upto + 1].type) && g.msgs[upto + 1].id === rec.d.id) upto++;
  return upto;
}
function currentRec(g) {
  const t = timeline(g);
  if (!t.length) return null;
  return g.cursor == null ? t[t.length - 1] : t[Math.max(0, Math.min(g.cursor, t.length - 1))];
}
function pendingFor(g, upto) {
  for (let k = g.decs.length - 1; k >= 0; k--) {
    const r = g.decs[k];
    if (r.i <= upto && r.seat === app.seat && visible(r)) return r;
  }
  return null;
}

// Moving the cursor: timeline scrubs, arrow keys, decision clicks. In a game still being played, the newest decision
// is the live view, so seeking there (stepping forward onto it, End, clicking its card) follows the game again;
// anything older pauses the board on it, with the paused bar over the board.
const followable = (g) => g && g.mode !== "recorded" && !g.ended;
const pausedLive = (g) => followable(g) && g.cursor != null;
function seek(k, opts = {}) {
  const g = app.game;
  if (!g) return;
  const t = timeline(g);
  if (!t.length) return;
  if (k == null || (followable(g) && k >= t.length - 1)) g.cursor = null;
  else g.cursor = Math.max(0, Math.min(k, t.length - 1));
  applyCursor(opts.animate);
  if (opts.scroll !== false) scrollToCurrent();
  syncUrl();
}

function applyCursor(animate) {
  const g = app.game;
  if (!g) return;
  const upto = uptoIndex(g);
  const cur = g.cursor != null ? currentRec(g) : null;
  for (const n of $$("#stream > [data-i], #log > [data-i]")) n.classList.toggle("future", +n.dataset.i > upto);
  for (const r of g.decs) if (r.el) r.el.classList.toggle("current", r === cur);
  const jump = Math.abs(upto - app.lastUpto);
  const anim = animate ?? (g.cursor == null ? g.caughtUp : upto > app.lastUpto && jump < 80);
  app.lastUpto = upto;
  renderBoard(anim);
  renderPlan();
  renderTimeline();
  renderFeedbackHint();
  renderStatus();
}

function scrollToCurrent() {
  const g = app.game;
  const pane = $("#stream");
  if (g.cursor == null) { if (app.stick) pane.scrollTop = pane.scrollHeight; return; }
  const cur = currentRec(g);
  if (cur && cur.el) {
    // Centred, unless it's too tall to fit: then its header stays in view.
    const tall = cur.el.clientHeight > pane.clientHeight * 0.75;
    const top = tall ? cur.el.offsetTop - 10 : cur.el.offsetTop - pane.clientHeight / 2 + cur.el.clientHeight / 2;
    pane.scrollTop = Math.max(0, top);
  }
}

function renderTimeline() {
  const g = app.game;
  const t = g ? timeline(g) : [];
  const ticks = $("#ticks"), turns = $("#turns");
  const n = t.length;
  const pos = (k) => (n <= 1 ? 50 : (k / (n - 1)) * 100);
  if (ticks._n !== n || ticks._gid !== (g && g.id) || ticks._dirty) {
    ticks._n = n; ticks._gid = g && g.id; ticks._dirty = false;
    let html = "", thtml = "", lastTurn = 0;
    t.forEach((r, k) => {
      const s = r.reply ? (r.reply.source || "backend") : "pending";
      const cls = s.startsWith("rule") ? "rule" : s === "backend" ? "" : s === "human" && r.human && !r.human.matched ? "diverge" : s;
      html += `<i class="tick ${cls}" style="left:${pos(k)}%" data-k="${k}"></i>`;
      const st = r.d.state || {};
      if (st.turn && st.turn !== lastTurn) {
        lastTurn = st.turn;
        const mine = (r.seat === app.seat) === (st.turn_player === 0);
        thtml += `<div class="turnmark ${mine ? "me" : "opp"}" style="left:${pos(k)}%"><span>T${st.turn}</span></div>`;
      }
    });
    ticks.innerHTML = html;
    turns.innerHTML = thtml;
  }
  const k = g && g.cursor != null ? g.cursor : n - 1;
  $$(".tick", ticks).forEach((e, i) => { e.classList.toggle("past", i <= k); });
  const last = t[n - 1];
  if (last && !last.reply && !last.human) ticks.lastChild && ticks.lastChild.classList.add("pending");
  const thumb = $("#thumb");
  thumb.classList.toggle("hidden", !n);
  thumb.style.left = pos(Math.max(0, k)) + "%";
  const rec = n ? t[Math.max(0, k)] : null;
  $("#tl-label").innerHTML = rec ? `<b>#${rec.d.id}</b> · ${k + 1}/${n} · turn ${(rec.d.state || {}).turn || 0}` : "no decisions yet";
  const live = g && g.mode !== "recorded";
  const lb = $("#live-btn");
  lb.classList.toggle("hidden", !live);
  lb.classList.toggle("on", !!(live && g.cursor == null && !g.ended));
  $("#play-path").setAttribute("d", app.playing ? ICON.pause : ICON.play);
  $("#tl-prev").disabled = !n || k <= 0;
  $("#tl-next").disabled = !n || (g.cursor == null);
}

function turnStarts(g) {
  const t = timeline(g), out = [];
  let last = -1;
  t.forEach((r, k) => { const turn = (r.d.state || {}).turn || 0; if (turn !== last) { out.push(k); last = turn; } });
  return out;
}
function step(delta, byTurn) {
  const g = app.game;
  if (!g) return;
  stopPlaying();
  const t = timeline(g);
  const k = g.cursor == null ? t.length - 1 : g.cursor;
  if (!byTurn) return seek(k + delta);
  const starts = turnStarts(g);
  if (delta < 0) {
    const prev = starts.filter((s) => s < k);
    return seek(prev.length ? prev[prev.length - 1] : 0);
  }
  const next = starts.find((s) => s > k);
  return seek(next == null ? t.length - 1 : next);
}
function togglePlay() {
  const g = app.game;
  if (!g) return;
  if (app.playing) return stopPlaying();
  const t = timeline(g);
  if (g.cursor == null && followable(g)) return;  // following a live game already
  if (g.cursor == null || g.cursor >= t.length - 1) seek(0);
  app.playing = setInterval(() => {
    const gg = app.game, tt = timeline(gg);
    if (!gg || gg.cursor == null || gg.cursor >= tt.length - 1) { stopPlaying(); return; }
    seek(gg.cursor + 1, { animate: true });  // in a live game, reaching the newest decision follows it again
  }, 1400);
  renderTimeline();
}
function stopPlaying() {
  if (app.playing) { clearInterval(app.playing); app.playing = null; renderTimeline(); }
}

// ---------------------------------------------------------------- plan, header, feedback hint

const planOf = (r) => (r.reply && r.reply.plan) || (r.advice && !r.advice.late && r.advice.plan) || null;
let planTimer = 0;
function schedulePlan() { cancelAnimationFrame(planTimer); planTimer = requestAnimationFrame(renderPlan); }
function renderPlan() {
  const g = app.game, box = $("#plan");
  if (!g) return box.classList.add("hidden");
  const upto = uptoIndex(g);
  const st = app.board || {};
  let found = null;
  for (let k = g.decs.length - 1; k >= 0; k--) {
    const r = g.decs[k];
    if (r.i > upto || r.seat !== app.seat) continue;
    if ((r.d.state || {}).turn !== st.turn) break;
    if (planOf(r) && (r.ri ?? r.i) <= upto) { found = r; break; }
  }
  if (!found) { box.classList.add("hidden"); box._sig = ""; return; }
  const sig = `${found.d.id}|${found.seat}`;
  box.classList.remove("hidden");
  if (box._sig === sig) return;
  box._sig = sig;
  const steps = planOf(found).split(/\n+/).map((s) => `<span class="step">${nameSpans(s.trim())}</span>`).join("");
  const who = names(g).me[0];
  box.classList.toggle("collapsed", store.get("planCollapsed", false));
  box.innerHTML = `<div class="plan-head">${ICON.plan}<span>Plan</span><span class="when">turn ${st.turn} · ${esc(who)} · since #${found.d.id}</span><span class="caret">${ICON.caret}</span></div><div class="plan-body">${steps}</div>`;
  $(".plan-head", box).onclick = () => { box.classList.toggle("collapsed"); store.set("planCollapsed", box.classList.contains("collapsed")); };
}

let headerTimer = 0;
function scheduleHeader() { clearTimeout(headerTimer); headerTimer = setTimeout(renderHeader, 30); }
function renderHeader() {
  const g = app.game;
  const chip = $("#status-chip"), title = $("#game-title");
  if (!g) { chip.className = "chip status idle"; chip.textContent = "NO GAME"; title.textContent = "Open a game"; return; }
  const n = names(g);
  title.innerHTML = `${esc(n.me[0])}<span class="vs">vs</span>${esc(n.opp[0])}`;
  renderStatus();
  document.title = `${n.me[0]} vs ${n.opp[0]} · ygo-agent`;
  const tabs = $("#seat-tabs");
  tabs.classList.toggle("hidden", !g.multi);
  $("#god-toggle").classList.toggle("hidden", !g.multi);
  if (g.multi) {
    const seats = [...g.seats.keys()].sort();
    tabs.innerHTML = seats.map((s) => `<button data-seat="${s}" class="${s === app.seat ? "on" : ""}"><span class="sw" style="background:var(${s === 0 ? "--me" : "--opp"})"></span>${esc(g.seat(s).deck_name || "Seat " + s)}</button>`).join("")
      + `<button data-seat="all" class="${app.streamSeats === "all" ? "on" : ""}" title="Reasoning from both seats">both</button>`;
  }
  renderPlan();
}

// The status chip and the paused bar say whether the BOARD is live, not just the game.
function renderStatus() {
  const g = app.game, chip = $("#status-chip"), bar = $("#pausebar");
  if (!g) return;
  const paused = pausedLive(g);
  const rec = paused ? currentRec(g) : null;
  const state = g.mode === "recorded" ? "replay" : g.ended ? "done" : paused ? "paused" : g.mode === "demo" ? "demo" : "live";
  chip.className = `chip status ${state}`;
  chip.textContent = paused && rec ? `PAUSED AT #${rec.d.id}` : { replay: "REPLAY", done: "ENDED", demo: "DEMO", live: "LIVE", paused: "PAUSED" }[state];
  chip.title = paused ? "The board shows an earlier decision. Esc, End or “Back to live” follows the game again." : "";
  $("#board").classList.toggle("past", paused);
  bar.classList.toggle("hidden", !paused);
  if (paused && rec) {
    const st = rec.d.state || {};
    const behind = timeline(g).length - 1 - g.cursor;
    $("#pause-text").innerHTML = `Viewing decision <b>#${rec.d.id}</b> (turn ${st.turn || 0}), not live<span class="behind"> · ${behind} newer</span>`;
  }
}

function backToLive() { stopPlaying(); app.stick = true; $("#jump").classList.add("hidden"); seek(null); }

// One bad message must never stop the board or the timeline: it is logged and counted, and the rest goes on.
function renderError(where, e, m) {
  app.renderErrors = (app.renderErrors || 0) + 1;
  console.error(`panel: ${where} failed`, e, m);
  const n = $("#render-err");
  n.classList.remove("hidden");
  n.textContent = app.renderErrors > 1 ? `render errors: ${app.renderErrors}` : "render error";
  n.title = `${where}: ${(e && e.message) || e}${m && m.type ? ` (message ${m.type}${m.seq ? " #" + m.seq : ""})` : ""}. Details in the browser console.`;
}

function renderFeedbackHint() {
  const g = app.game, hint = $("#fb-hint");
  if (!g) { hint.innerHTML = "Open a game to leave notes."; return; }
  const rec = currentRec(g);
  const st = rec ? rec.d.state || {} : {};
  const where = g.mode === "recorded" ? "this game's feedback.md" : "feedback.md, like a <code>!note</code> in duel chat";
  hint.innerHTML = rec ? `Tagged with <b>decision #${rec.d.id}</b> (turn ${st.turn || 0}${g.multi ? `, ${esc(g.seat(rec.seat).deck_name || "seat " + rec.seat)}` : ""}) · saved to ${where}` : `Saved to ${where}`;
}

// ---------------------------------------------------------------- opening games

function resetView(g) {
  stopPlaying();
  app.game = g;
  renderReview();
  app.lastSepTurn = 0;
  app.logCount = 0;
  app.lastUpto = -1;
  app.prevLp = {};
  app.stick = true;
  $("#stream").innerHTML = "";
  $("#log").innerHTML = "";
  $("#count-stream").textContent = "";
  $("#count-log").textContent = "";
  $("#plan").classList.add("hidden");
  $("#plan")._sig = "";
  $("#banner")._dismissed = null;
  $("#ticks")._dirty = true;
  for (const z of Object.values(board.zones)) { z._sig = null; z._id = null; }
  $("#chain")._sig = "";
  renderHeader();
}

function rebuildPanes() {
  const g = app.game;
  if (!g) return;
  app.lastSepTurn = 0;
  app.logCount = 0;
  $("#stream").innerHTML = "";
  $("#log").innerHTML = "";
  for (const m of g.msgs) {
    if (m.type === "decision") { const r = g.byKey.get(key(m.seat || 0, m.decision.id)); if (r) addDecision(g, r, false); }
    else if (m.type === "event" || (m.type === "reply" && m.say)) addLog(g, m);
    else if (m.type === "feedback_ack") addNote(g, m, false);
  }
  $("#ticks")._dirty = true;
  applyCursor(false);
  scrollToCurrent();
}

function openLive(id) {
  const info = app.live.find((x) => x.game_id === id);
  const demo = (info && info.seats && info.seats.some((s) => s.demo)) || id.startsWith("demo:");
  resetView(new GameView(id, demo ? "demo" : "live"));
  connect(id);
  syncUrl();
  closeModal();
}

async function openRecorded(name, decision) {
  closeModal();
  const res = await fetch(`/api/recorded/${encodeURIComponent(name)}`);
  if (!res.ok) return toast("Couldn't open that game", name, "bad");
  const data = await res.json();
  const g = new GameView(`rec:${name}`, "recorded");
  resetView(g);
  for (const m of data.messages) { try { ingest(g, m, false); } catch (e) { renderError("ingest", e, m); } }
  renderHeader();
  const t = timeline(g);
  let k = 0;
  if (decision != null) { const j = t.findIndex((r) => r.d.id === +decision); if (j >= 0) k = j; }
  g.cursor = Math.min(k, Math.max(0, t.length - 1));
  $("#ticks")._dirty = true;
  applyCursor(false);
  scrollToCurrent();
  syncUrl();
  connect("");  // only the game list from now on
}

function syncUrl() {
  const g = app.game;
  const p = new URLSearchParams();
  if (g) {
    p.set("game", g.id);
    if (g.cursor != null) { const r = currentRec(g); if (r) p.set("d", r.d.id); }
  }
  for (const k of ["theme", "tab", "seat", "width"]) if (app.params.get(k)) p.set(k, app.params.get(k));
  history.replaceState(null, "", `${location.pathname}?${p}`);
}

function connect(id) {
  if (app.es) app.es.close();
  const es = new EventSource(`/stream${id ? `?game=${encodeURIComponent(id)}` : ""}`);
  app.es = es;
  es.onopen = () => setConn(true);
  es.onerror = () => setConn(false);
  es.onmessage = (e) => {
    let m;
    try { m = JSON.parse(e.data); } catch { return; }
    onStream(m, id);
  };
}
function setConn(ok) {
  const c = $("#conn");
  c.className = `conn ${ok ? "ok" : "bad"}`;
  c.title = ok ? "Connected to the panel server" : "Reconnecting…";
}

let liveTimer = 0;
function onStream(m, subscribed) {
  const g = app.game;
  if (m.type === "games") {
    app.live = m.games || [];
    if (!g && !app.params.get("game")) {
      const live = app.live.find((x) => x.live);
      if (live) return openLive(live.game_id);
      showGames();
    }
    return;
  }
  if (m.type === "caught_up") {
    if (g && g.id === m.game_id) {
      g.caughtUp = true;
      rebuildIfNeeded();
      if (!g.msgs.length && g.mode !== "recorded") { toast("That game isn't on this panel", "Pick one from the list.", "bad"); showGames(); app.awaiting = g.id; }
    }
    return;
  }
  if (g && m.game_id === g.id && g.mode !== "recorded" && subscribed === g.id) {
    const following = g.caughtUp && g.cursor == null;
    if (app.awaiting === g.id) { app.awaiting = null; if ($("#modal")._kind === "games") closeModal(); }  // it started after all
    try { ingest(g, m, following); } catch (e) { renderError("ingest", e, m); }
    if (g.caughtUp) liveUpdate(following);
    return;
  }
  if (["game_start", "meta", "game_end"].includes(m.type)) {
    clearTimeout(liveTimer);
    liveTimer = setTimeout(refreshGames, 300);
    if (m.type === "game_start" && (!g || g.ended || g.mode === "recorded") && m.game_id !== (g && g.id)) {
      if (!g || (g.ended && g.mode !== "recorded")) setTimeout(() => openLive(m.game_id), 400);
      else toast("A live game started", "Open it from the games list (G).", "good");
    }
  }
}

function rebuildIfNeeded() {
  try {
    renderHeader();
    $("#ticks")._dirty = true;
    applyCursor(false);
    scrollToCurrent();
  } catch (e) { renderError("catch-up", e); }
}

let liveFrame = 0;
function liveUpdate(following) {
  cancelAnimationFrame(liveFrame);
  liveFrame = requestAnimationFrame(() => {
    const g = app.game;
    $("#ticks")._dirty = true;
    try {
      if (following) {
        applyCursor(true);
        if (app.stick) { const pane = $("#stream"); pane.scrollTop = pane.scrollHeight; }
        else $("#jump").classList.remove("hidden");
      } else { renderTimeline(); renderStatus(); }
    } catch (e) { renderError("live update", e); }
    try { if (g) renderHeader(); } catch (e) { renderError("header", e); }
  });
}

async function refreshGames() {
  try {
    const r = await fetch("/api/games");
    const data = await r.json();
    app.live = data.live || [];
    app.recorded = data.recorded || [];
  } catch { /* offline */ }
  if (!$("#modal").classList.contains("hidden") && $("#modal")._kind === "games") renderGames();
}

// ---------------------------------------------------------------- overlays

function closeModal() { $("#modal").classList.add("hidden"); $("#modal")._kind = null; }
function openModal(kind, html) {
  const m = $("#modal");
  m._kind = kind;
  $("#modal-card").innerHTML = html;
  m.classList.remove("hidden");
}

async function showGames() {
  await refreshGames();
  renderGames(true);
}
function fmtStarted(s) {
  if (!s) return "";
  const d = typeof s === "number" ? new Date(s * 1000) : new Date(String(s).replace(" ", "T"));
  if (isNaN(d)) return String(s);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
function renderGames(open) {
  const g = app.game;
  const live = app.live.map((x) => {
    const seats = x.seats || [];
    const label = seats.map((s) => s.label).filter(Boolean).join(" / ");
    const state = x.live ? "live" : (seats[0] && seats[0].result) || "unfinished";
    return `<button class="gitem ${g && g.id === x.game_id ? "current" : ""}" data-live="${esc(x.game_id)}">
      <div class="gt">${esc(x.title)}<span class="res ${state}">${state === "live" ? "LIVE" : esc(String(state).toUpperCase())}</span></div>
      <div class="gm"><span>${fmtStarted(x.started)}</span><span>${x.decisions} decisions</span><span>turn ${x.turn}</span>${label ? `<span class="chip">${esc(label)}</span>` : ""}${seats.some((s) => s.demo) ? `<span class="chip">demo</span>` : ""}</div></button>`;
  }).join("");
  const rec = app.recorded.map((x) => {
    const state = x.result || "unfinished";
    return `<button class="gitem ${g && g.id === x.game_id ? "current" : ""}" data-rec="${esc(x.name)}">
      <div class="gt">${esc(x.deck_name || x.deck || "?")}<span class="vs">vs</span>${esc(x.opponent || "?")}<span class="res ${state}">${esc(state.toUpperCase())}</span></div>
      <div class="gm"><span>${fmtStarted(x.started) || esc(x.name)}</span><span>${x.decisions} decisions</span><span>${x.turns} turns</span>${x.backend ? `<span class="chip">${esc(x.backend)}</span>` : ""}${x.mode && x.mode !== "play" ? `<span class="chip">${esc(x.mode)}</span>` : ""}${x.notes ? `<span class="chip">${x.notes} note${x.notes > 1 ? "s" : ""}</span>` : ""}${x.latest ? `<span class="chip">latest</span>` : ""}</div></button>`;
  }).join("");
  const html = `<div class="modal-head"><h2>Games</h2><span class="sub">live games in this process, and every log under games/</span><div class="spacer"></div><button class="icon-btn" data-close title="Close (Esc)">✕</button></div>
    <div class="modal-body">
      <div class="gsec"><h3>Live</h3>${live ? `<div class="glist">${live}</div>` : `<div class="empty-note" style="padding:14px 0;text-align:left">No live game. Start one with <code>ygo-agent play --web</code> (or <code>selfplay</code> / <code>teach</code> / <code>coach</code> with <code>--web</code>), or replay a log live with <code>ygo-agent web --demo games/&lt;dir&gt;</code>.</div>`}</div>
      <div class="gsec"><h3>Recorded</h3>${rec ? `<div class="glist">${rec}</div>` : `<div class="empty-note" style="padding:14px 0;text-align:left">No game logs found.</div>`}</div>
    </div>`;
  if (open || $("#modal")._kind === "games") openModal("games", html);
}

function showPile(side, kind) {
  const st = app.board;
  if (!st) return;
  const list = (side === "me" ? st.me : st.opp)[kind] || [];
  const title = { gy: "Graveyard", ban: "Banished", extra: "Extra Deck" }[kind];
  const who = names(app.game)[side][0];
  const items = [...list].reverse().map((c) => {
    const hidden = !c.id || (kind === "ban" && c.p & 0xa && side === "opp");
    return hidden ? `<div class="pc"><div class="back"></div><span>face-down</span></div>`
      : `<div class="pc" data-card="${c.id}"><img src="${pic(c.id)}" alt="" loading="lazy"><span>${esc(cardName(c.id))}</span></div>`;
  }).join("");
  openModal("pile", `<div class="modal-head"><h2>${title}</h2><span class="sub">${esc(who)} · ${list.length} card${list.length === 1 ? "" : "s"}${kind === "gy" || kind === "ban" ? " · newest first" : ""}</span><div class="spacer"></div><button class="icon-btn" data-close>✕</button></div>
    <div class="modal-body">${items ? `<div class="pilegrid">${items}</div>` : `<div class="empty-note">Empty.</div>`}</div>`);
}

let previewFor = null;
async function showPreview(target) {
  const id = +target.dataset.card;
  if (!id) return;
  previewFor = target;
  const box = $("#preview");
  const brief = app.cards.get(id) || {};
  box.innerHTML = `<img src="${pic(id)}" alt=""><div class="info"><h3>${esc(brief.n || cardName(id))}</h3><div class="tl"></div><div class="st"></div><div class="tx" style="color:var(--faint)">…</div></div>`;
  box.classList.remove("hidden");
  place(box, target);
  const info = await cardInfo(id);
  if (previewFor !== target || !info) return;
  $(".tl", box).textContent = info.type_line;
  const stats = [];
  if (info.type & TYPE.MONSTER) {
    stats.push(`ATK ${info.atk < 0 ? "?" : info.atk}`);
    if (!(info.type & TYPE.LINK)) stats.push(`DEF ${info.def < 0 ? "?" : info.def}`);
    stats.push(info.type & TYPE.LINK ? `LINK-${info.level}` : info.type & TYPE.XYZ ? `Rank ${info.level}` : `Level ${info.level}`);
  }
  $(".st", box).innerHTML = stats.map((s) => `<span>${s}</span>`).join("");
  const tx = $(".tx", box);
  tx.style.color = "";
  tx.textContent = info.text;
  place(box, target);
}
function place(box, target) {
  const r = target.getBoundingClientRect(), b = box.getBoundingClientRect();
  const vw = innerWidth, vh = innerHeight, pad = 12;
  let x = r.right + pad;
  if (x + b.width > vw - pad) x = r.left - b.width - pad;
  if (x < pad) x = Math.max(pad, Math.min(vw - b.width - pad, r.left + r.width / 2 - b.width / 2));
  let y = r.top + r.height / 2 - b.height / 2;
  y = Math.max(pad, Math.min(vh - b.height - pad, y));
  box.style.left = `${x}px`;
  box.style.top = `${y}px`;
}
function hidePreview() { previewFor = null; $("#preview").classList.add("hidden"); }

let toastN = 0;
function toast(title, sub, kind = "") {
  const t = el("div", `toast ${kind}`, `${esc(title)}${sub ? `<small>${esc(sub)}</small>` : ""}`);
  $("#toasts").append(t);
  const n = ++toastN;
  setTimeout(() => t.remove(), 4200 + (n % 2));
}

// ---------------------------------------------------------------- feedback

async function sendFeedback(ev) {
  ev.preventDefault();
  const input = $("#fb-text");
  const text = input.value.trim();
  const g = app.game;
  if (!text || !g) return;
  const rec = currentRec(g);
  const body = { game_id: g.id, seat: rec ? rec.seat : app.seat, text };
  if (rec && (g.cursor != null || g.mode === "recorded")) { body.decision = rec.d.id; body.turn = (rec.d.state || {}).turn; }
  $("#fb-send").disabled = true;
  try {
    const r = await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const out = await r.json();
    if (!r.ok) throw new Error(out.error || r.statusText);
    input.value = "";
    const file = out.file ? out.file.split("/").slice(-2).join("/") : "";
    toast(`Noted feedback #${out.n}`, `${out.context}${file ? " · " + file : ""}`, "good");
    if (g.mode === "recorded") {
      // Shown right after the decision it is about (not at the end of the game).
      ingest(g, { type: "feedback_ack", game_id: g.id, seat: body.seat, text, context: out.context, who: "Web panel" }, true);
      const item = $("#stream").lastElementChild;
      if (rec && rec.el && item) { item.dataset.i = rec.ri ?? rec.i; rec.el.after(item); }
    }
  } catch (e) {
    toast("The note wasn't saved", String(e.message || e), "bad");
  } finally {
    $("#fb-send").disabled = false;
    input.focus();
  }
}

// ---------------------------------------------------------------- layout and wiring

function fit() {
  const wrap = $("#board-wrap");
  const W = wrap.clientWidth - 20, H = wrap.clientHeight - 12;
  const cw = Math.max(34, Math.min(W / 10.7, (H - 48) / 9.25, 118));
  $("#board").style.setProperty("--cw", `${cw.toFixed(1)}px`);
  for (const k of ["me:hand", "opp:hand"]) if (board.zones[k]) board.zones[k]._sig = null;
  if (app.game) renderBoard(false);
}

const THEME_ICON = {
  dark: '<svg viewBox="0 0 20 20"><path d="M10 3.2a6.8 6.8 0 1 0 6.8 6.8A5.3 5.3 0 0 1 10 3.2z" fill="currentColor"/></svg>',
  light: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="3.6" fill="currentColor"/><path d="M10 1.8v2.4M10 15.8v2.4M1.8 10h2.4M15.8 10h2.4M4.2 4.2l1.7 1.7M14.1 14.1l1.7 1.7M4.2 15.8l1.7-1.7M14.1 5.9l1.7-1.7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
};
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  $("#theme-btn").innerHTML = THEME_ICON[t] || THEME_ICON.dark;
  store.set("theme", t);
}

function wire() {
  setTheme(app.params.get("theme") || store.get("theme", "dark"));
  $("#theme-btn").onclick = () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  $("#game-btn").onclick = showGames;
  $("#show-auto").checked = app.showAuto;
  $("#stream").classList.toggle("hide-auto", !app.showAuto);
  $("#show-auto").onchange = (e) => { app.showAuto = e.target.checked; store.set("showAuto", app.showAuto); $("#stream").classList.toggle("hide-auto", !app.showAuto); };
  $("#god").checked = app.god;
  $("#god").onchange = (e) => { app.god = e.target.checked; store.set("god", app.god); renderBoard(false); };
  for (const t of $$(".tab")) t.onclick = () => setTab(t.dataset.tab);
  $("#seat-tabs").onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.seat === "all") app.streamSeats = app.streamSeats === "all" ? app.seat : "all";
    else { app.seat = +b.dataset.seat; if (app.streamSeats !== "all") app.streamSeats = app.seat; for (const z of Object.values(board.zones)) z._sig = null; }
    app.prevLp = {};
    renderHeader();
    rebuildPanes();
  };
  $("#feedback").onsubmit = sendFeedback;
  $("#tl-prev").onclick = () => step(-1);
  $("#tl-next").onclick = () => step(1);
  $("#tl-prev-turn").onclick = () => step(-1, true);
  $("#tl-next-turn").onclick = () => step(1, true);
  $("#tl-play").onclick = togglePlay;
  $("#live-btn").onclick = backToLive;
  $("#pause-live").onclick = backToLive;
  $("#jump").onclick = backToLive;
  const pane = $("#stream");
  // Auto-scroll pauses only when the viewer scrolls up (content growing below never counts as scrolling away).
  let lastTop = 0;
  pane.addEventListener("scroll", () => {
    const atEnd = pane.scrollTop + pane.clientHeight >= pane.scrollHeight - 40;
    if (app.game && app.game.cursor == null) {
      if (atEnd) { app.stick = true; $("#jump").classList.add("hidden"); }
      else if (pane.scrollTop < lastTop - 4) app.stick = false;
    }
    lastTop = pane.scrollTop;
  });
  pane.addEventListener("click", (e) => {
    const card = e.target.closest(".dc");
    const rec = card && app.game && app.game.decs.find((r) => r.el === card);
    if (!rec) return;
    if (e.target.closest("[data-more]")) { rec.expanded = true; fillCard(card, rec); return; }
    if (e.target.closest("[data-plan]")) { rec.planOpen = !rec.planOpen; fillCard(card, rec); return; }
    if (String(getSelection && getSelection()).trim()) return;  // selecting text to copy, not seeking
    const k = timeline(app.game).indexOf(rec);
    if (k >= 0) { stopPlaying(); seek(k, { scroll: false }); }
  });
  // Track: click or drag to scrub.
  const track = $("#track");
  const scrub = (e) => {
    const g = app.game;
    if (!g) return;
    const n = timeline(g).length;
    const r = track.getBoundingClientRect();
    const k = Math.round(((e.clientX - r.left) / r.width) * (n - 1));
    stopPlaying();
    seek(Math.max(0, Math.min(n - 1, k)));
  };
  track.addEventListener("pointerdown", (e) => { track.setPointerCapture(e.pointerId); scrub(e); track.onpointermove = scrub; });
  track.addEventListener("pointerup", () => { track.onpointermove = null; });
  $("#modal").addEventListener("click", (e) => {
    if (e.target.id === "modal" || e.target.closest("[data-close]")) return closeModal();
    const live = e.target.closest("[data-live]");
    if (live) return openLive(live.dataset.live);
    const rec = e.target.closest("[data-rec]");
    if (rec) return openRecorded(rec.dataset.rec);
  });
  document.addEventListener("mouseover", (e) => {
    const t = e.target.closest("[data-card]");
    if (t && t !== previewFor) showPreview(t);
    else if (!t && previewFor) hidePreview();
  });
  document.addEventListener("keydown", (e) => {
    const t = e.target;
    // Typing (the note box, any field) never drives the timeline; Space/Enter on a button just press it.
    if (t && t.closest && t.closest("input, textarea, select, [contenteditable], #feedback")) {
      if (e.key === "Escape" && t.matches("input, textarea")) t.blur();
      return;
    }
    if (t && t.closest && t.closest("button") && (e.key === " " || e.key === "Enter")) return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.isComposing) return;
    if (e.key === "Escape") {
      if (!$("#modal").classList.contains("hidden")) return closeModal();
      if (pausedLive(app.game)) backToLive();
      return;
    }
    if (e.key === "ArrowLeft") { e.preventDefault(); step(-1, e.shiftKey); }
    else if (e.key === "ArrowRight") { e.preventDefault(); step(1, e.shiftKey); }
    else if (e.key === "Home") { e.preventDefault(); stopPlaying(); seek(0); }
    else if (e.key === "End") { e.preventDefault(); stopPlaying(); seek(timeline(app.game || { decs: [] }).length - 1); }
    else if (e.key === " ") { e.preventDefault(); togglePlay(); }
    else if (e.key === "l" || e.key === "L") { stopPlaying(); seek(null); }
    else if (e.key === "g" || e.key === "G") showGames();
    else if (e.key === "n" || e.key === "N") { e.preventDefault(); $("#fb-text").focus(); }
  });
  new ResizeObserver(fit).observe($("#board-wrap"));
  setInterval(() => {
    // the "thinking" timer on a pending decision
    for (const n of $$(".dc.pending .elapsed")) {
      const card = n.closest(".dc");
      const rec = app.game && app.game.decs.find((r) => r.el === card);
      if (rec && rec.m.ts && app.game.mode !== "recorded") n.textContent = ` · ${Math.max(0, Date.now() / 1000 - rec.m.ts).toFixed(0)}s`;
    }
  }, 1000);
}

function setTab(tab) {
  if (tab === "review" && !(app.game && app.game.review)) tab = "stream";
  app.tab = tab;
  for (const t of $$(".tab")) t.classList.toggle("on", t.dataset.tab === tab);
  $("#stream").classList.toggle("hidden", tab !== "stream");
  $("#log").classList.toggle("hidden", tab !== "log");
  $("#review").classList.toggle("hidden", tab !== "review");
  $("#feedback").classList.toggle("hidden", tab === "review");
  if (tab === "log") { const l = $("#log"); if (!app.game || app.game.cursor == null) l.scrollTop = l.scrollHeight; else { const f = $$("#log > :not(.future)"); const last = f[f.length - 1]; if (last) l.scrollTop = last.offsetTop - l.clientHeight + 60; } }
}

async function main() {
  wire();
  buildBoard();
  fit();
  const p = app.params;
  if (p.get("seat")) app.seat = +p.get("seat");
  if (p.get("tab")) setTab(p.get("tab"));
  const game = p.get("game");
  if (game && game.startsWith("rec:")) await openRecorded(game.slice(4), p.get("d"));
  else if (game) { app.live = []; openLive(game); }
  else connect("");
  if (p.get("tab")) setTab(p.get("tab"));
}

main();
