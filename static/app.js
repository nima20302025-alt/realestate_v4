/* LuxeHome frontend — vanilla JS, no build step. */
(() => {
"use strict";

/* ───────────────────────── utils ───────────────────────── */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => (n == null || isNaN(n) ? "—" : "$" + Math.round(n).toLocaleString("en-US"));
const num = (v) => { const n = parseMoney(v); return n > 0 ? n : null; };
function parseMoney(v) {
  if (v == null) return NaN;
  const m = String(v).trim().toLowerCase().replace(/[$,\s]/g, "").match(/^(\d*\.?\d+)([km]?)$/);
  if (!m) return NaN;
  return parseFloat(m[1]) * (m[2] === "m" ? 1e6 : m[2] === "k" ? 1e3 : 1);
}
const load = (k, d) => { try { const v = JSON.parse(localStorage.getItem(k)); return v == null ? d : v; } catch (e) { return d; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parseYMD = (s) => { const [y, m, d] = String(s).split("-").map(Number); return new Date(y, m - 1, d); };
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const startOfToday = () => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const fmtTime = (t) => { const [h, m] = String(t).split(":").map(Number); return `${((h + 11) % 12) + 1}:${String(m || 0).padStart(2, "0")} ${h >= 12 ? "PM" : "AM"}`; };
const fmtDateLong = (s) => { const d = parseYMD(s); return `${WEEKDAYS[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}`; };
const relDay = (s) => { const n = Math.round((parseYMD(s) - startOfToday()) / 864e5); return n === 0 ? "Today" : n === 1 ? "Tomorrow" : n > 1 ? `in ${n} days` : `${-n} day${n === -1 ? "" : "s"} ago`; };
const pctTxt = (v) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v}%`);

/* ───────────────────────── icons ───────────────────────── */
const IC = {
  home: '<path d="m3 11 9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
  chat: '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
  search: '<circle cx="11" cy="11" r="7.5"/><path d="m21 21-4.3-4.3"/>',
  heart: '<path d="M19 14c1.5-1.5 3-3.2 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4 3 5.5l7 7Z"/>',
  columns: '<rect x="3" y="3" width="7.5" height="18" rx="2"/><rect x="13.5" y="3" width="7.5" height="18" rx="2"/>',
  calendar: '<rect x="3" y="4.5" width="18" height="17" rx="2.5"/><path d="M16 2.5v4M8 2.5v4M3 10h18"/>',
  calplus: '<rect x="3" y="4.5" width="18" height="17" rx="2.5"/><path d="M16 2.5v4M8 2.5v4M3 10h18M12 13v5M9.5 15.5h5"/>',
  bed: '<path d="M3 18v-7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v7"/><path d="M3 15h18"/><path d="M7 9V7.5A1.5 1.5 0 0 1 8.5 6h2A1.5 1.5 0 0 1 12 7.5V9"/>',
  bath: '<path d="M4 12h16v3a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z"/><path d="M6 12V6.5a2.5 2.5 0 0 1 5 0"/><path d="M7 21l1-2M17 21l-1-2"/>',
  area: '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
  pin: '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
  clock: '<circle cx="12" cy="12" r="9.5"/><path d="M12 6.5V12l3.5 2"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
  sparkles: '<path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9Z"/><path d="M19 3v4M17 5h4"/>',
  pencil: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  trophy: '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0zM17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  nav: '<path d="m3 11 19-9-9 19-2-8z"/>',
  scale: '<path d="M12 3v18M5 21h14M5 7h14"/><path d="m5 7-3 7a3.5 3.5 0 0 0 6 0Z"/><path d="m19 7-3 7a3.5 3.5 0 0 0 6 0Z"/>',
};
const icon = (n, filled = false) => `<svg class="i${filled ? " filled" : ""}" viewBox="0 0 24 24" aria-hidden="true">${IC[n] || ""}</svg>`;

/* ───────────────────────── generated house art ───────────────────────── */
const PAL = [
  ["#c7d2fe", "#eef2ff", "#6366f1", "#312e81", "#a5b4fc"], ["#fde68a", "#fff7e0", "#f59e0b", "#92400e", "#fbbf24"],
  ["#a7f3d0", "#ecfdf5", "#10b981", "#065f46", "#6ee7b7"], ["#fbcfe8", "#fdf2f8", "#ec4899", "#831843", "#f9a8d4"],
  ["#bae6fd", "#f0f9ff", "#0ea5e9", "#0c4a6e", "#7dd3fc"], ["#fecaca", "#fff1f2", "#ef4444", "#7f1d1d", "#fca5a5"],
  ["#ddd6fe", "#f5f3ff", "#8b5cf6", "#4c1d95", "#c4b5fd"], ["#fed7aa", "#fff7ed", "#f97316", "#7c2d12", "#fdba74"],
];
const hash = (s) => { let h = 2166136261; for (const c of String(s)) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; };
let artSeq = 0;
function houseArt(p) {
  const h = hash(p.property_id || "x"), [top, bot, wall, roof, acc] = PAL[h % PAL.length], id = "g" + ++artSeq;
  const type = String(p.property_type || "House").toLowerCase();
  let b = "";
  if (/condo|apart/.test(type)) {
    b += `<rect x="96" y="120" width="46" height="88" rx="3" fill="${acc}"/><rect x="140" y="46" width="122" height="162" rx="4" fill="${wall}"/><rect x="132" y="40" width="138" height="10" rx="3" fill="${roof}"/>`;
    for (let r = 0; r < 6; r++) for (let c = 0; c < 3; c++) b += `<rect x="${154 + c * 34}" y="${62 + r * 24}" width="22" height="14" rx="2" fill="#fff" opacity="${(h >> (r * 3 + c)) & 1 ? 0.92 : 0.4}"/>`;
    for (let r = 0; r < 3; r++) b += `<rect x="108" y="${132 + r * 24}" width="22" height="14" rx="2" fill="#fff" opacity=".75"/>`;
    b += `<rect x="190" y="182" width="26" height="26" rx="3" fill="${roof}"/>`;
  } else if (/town/.test(type)) {
    [[84, 98], [160, 114], [236, 102]].forEach(([x, hgt], i) => {
      const y = 208 - hgt;
      b += `<rect x="${x}" y="${y}" width="76" height="${hgt}" fill="${i === 1 ? acc : wall}"/>`;
      b += i === 1 ? `<path d="M${x - 4} ${y} L${x + 38} ${y - 30} L${x + 80} ${y}Z" fill="${roof}"/>` : `<rect x="${x - 4}" y="${y - 10}" width="84" height="12" fill="${roof}"/>`;
      b += `<rect x="${x + 10}" y="${y + 16}" width="22" height="22" rx="2" fill="#fff" opacity=".88"/><rect x="${x + 44}" y="${y + 16}" width="22" height="22" rx="2" fill="#fff" opacity=".88"/>`;
      b += `<rect x="${x + 28}" y="182" width="20" height="26" rx="2" fill="${roof}" opacity=".9"/>`;
    });
  } else {
    b += `<rect x="246" y="76" width="16" height="40" fill="${roof}"/><rect x="116" y="132" width="168" height="76" rx="3" fill="${wall}"/><path d="M100 138 L200 66 L300 138Z" fill="${roof}"/>`;
    b += `<rect x="188" y="164" width="26" height="44" rx="3" fill="#fff" opacity=".92"/><rect x="132" y="152" width="36" height="28" rx="3" fill="#fff" opacity=".88"/><rect x="232" y="152" width="36" height="28" rx="3" fill="#fff" opacity=".88"/><circle cx="200" cy="112" r="9" fill="#fff" opacity=".85"/>`;
  }
  const tx = 40 + (h % 3) * 14, trees = `<rect x="${tx - 3}" y="178" width="6" height="30" fill="${roof}"/><circle cx="${tx}" cy="170" r="22" fill="#4f9d69"/><rect x="${352 - (h % 2) * 14}" y="186" width="5" height="22" fill="${roof}"/><circle cx="${354 - (h % 2) * 14}" cy="180" r="16" fill="#5fae78"/>`;
  return `<svg viewBox="0 0 400 260" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Illustration of a ${esc(type)}"><defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${top}"/><stop offset="1" stop-color="${bot}"/></linearGradient></defs><rect width="400" height="260" fill="url(#${id})"/><circle cx="${70 + (h % 5) * 55}" cy="54" r="26" fill="#fff" opacity=".75"/><path d="M0 186 Q100 140 200 180 T400 168 V260 H0Z" fill="${acc}" opacity=".5"/><rect y="206" width="400" height="54" fill="#9ccfa6"/><rect y="206" width="400" height="6" fill="#86bd92"/>${trees}${b}</svg>`;
}

/* ───────────────────────── state ───────────────────────── */
const TABS = [
  { id: "chat", label: "Chat", icon: "chat", title: "Your AI realtor" },
  { id: "explore", label: "Explore", icon: "search", title: "Explore homes" },
  { id: "favorites", label: "Saved", icon: "heart", title: "Saved homes" },
  { id: "compare", label: "Compare", icon: "columns", title: "Compare homes" },
  { id: "viewings", label: "Viewings", icon: "calendar", title: "Your viewings" },
];
const AMEN = [["parking", "Parking"], ["garden", "Garden"], ["near_metro", "Near transit"], ["pool", "Pool"], ["balcony", "Balcony"], ["elevator", "Elevator"], ["pet_friendly", "Pet-friendly"], ["furnished", "Furnished"]];
const S = {
  cid: null, name: "Guest", verified: false, contact: "", tab: "chat", props: {}, favs: new Set(), favCards: [], appts: [], apptCount: 0,
  compare: load("lh.compare", []), meta: null, exploreInit: false, explore: { limit: 12 }, cmpData: null,
  mort: load("lh.mort", { down: 20, rate: 6.5, years: 30 }), showHistory: false, sending: false,
};
const cache = (list) => (list || []).forEach((p) => p && p.property_id && (S.props[p.property_id] = { ...(S.props[p.property_id] || {}), ...p }));
const pidOf = (el) => el.dataset.pid || (el.closest("[data-pid]") || {}).dataset?.pid;

/* ───────────────────────── api ───────────────────────── */
async function api(path, opts = {}) {
  let res;
  try {
    res = await fetch(path, { method: opts.method || "GET", credentials: "same-origin", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: opts.body });
  } catch (e) {
    throw new Error("Can't reach the server right now. It may be restarting — try again in a few seconds.");
  }
  if (res.status === 401 && !opts._retried && path !== "/api/session") {
    const wasVerified = S.verified;
    await ensureSession({ force: true });
    if (wasVerified) toast("Your session expired — sign in again to get your saved homes back.", "warn");
    return api(path, { ...opts, _retried: true });
  }
  if (!res.ok) {
    let msg = res.statusText || "HTTP " + res.status;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail || j); } catch (_) {}
    throw new Error(msg.slice(0, 400));
  }
  return res.json();
}
const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });

/* ───────────────────────── ui primitives ───────────────────────── */
function toast(msg, kind = "", action) {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.innerHTML = `<span>${esc(msg)}</span>` + (action ? `<button>${esc(action.label)}</button>` : "");
  if (action) el.querySelector("button").onclick = () => { action.fn(); el.remove(); };
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), kind === "err" ? 6500 : 3600);
}
let modalCtl = null;
function openModal(html, { cls = "", onClose } = {}) {
  closeModal();
  const ov = document.createElement("div");
  ov.className = "overlay";
  ov.innerHTML = `<div class="modal ${cls}" role="dialog" aria-modal="true">${html}</div>`;
  ov.addEventListener("mousedown", (e) => { if (e.target === ov) closeModal(); });
  $("#modal-root").appendChild(ov);
  document.body.classList.add("no-scroll");
  modalCtl = { ov, onClose };
  return $(".modal", ov);
}
function closeModal() {
  if (!modalCtl) return;
  const { ov, onClose } = modalCtl;
  modalCtl = null;
  ov.remove();
  document.body.classList.remove("no-scroll");
  if (onClose) onClose();
}
const closeBtn = () => `<button class="icon-btn modal-x" data-act="close-modal" aria-label="Close">${icon("x")}</button>`;
function confirmBox({ title, text, ok = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolve(v); } };
    const m = openModal(`<div class="modal-pad"><h2>${esc(title)}</h2><p class="muted">${esc(text)}</p><div class="row" style="justify-content:flex-end;margin-top:18px"><button class="btn ghost" data-r="0">Keep it</button><button class="btn ${danger ? "danger" : "primary"}" data-r="1">${esc(ok)}</button></div></div>`, { cls: "small", onClose: () => finish(false) });
    $$("[data-r]", m).forEach((b) => (b.onclick = () => { finish(b.dataset.r === "1"); closeModal(); }));
  });
}

/* ───────────────────────── property card ───────────────────────── */
function cardHTML(p) {
  const fav = S.favs.has(p.property_id), inCmp = S.compare.includes(p.property_id);
  const where = [p.neighborhood, p.city].filter(Boolean).join(", ");
  return `<article class="pcard" data-pid="${esc(p.property_id)}">
    <div class="pcard-art" data-act="details">${houseArt(p)}
      ${p.match_score > 0 ? `<span class="badge match">${icon("sparkles")} ${Math.round(p.match_score)}% match</span>` : ""}
      <span class="badge type">${esc(p.property_type || "Home")}</span>
      <button class="icon-btn fav ${fav ? "on" : ""}" data-act="fav" aria-label="Save">${icon("heart", fav)}</button>
    </div>
    <div class="pcard-body">
      <div class="pid">${esc(p.property_id)}</div>
      <div class="price-row"><span class="price">${money(p.price)}</span>${p.price_per_sqft ? `<span class="ppsf">${money(p.price_per_sqft)}/sqft</span>` : ""}</div>
      <div class="loc">${icon("pin")}<span>${esc(where)}</span></div>
      <div class="facts"><span>${icon("bed")} ${p.bedrooms ?? "—"}</span><span>${icon("bath")} ${p.bathrooms ?? "—"}</span><span>${icon("area")} ${p.area_sqft ? p.area_sqft.toLocaleString() : "—"} sqft</span>${p.year_built ? `<span class="muted">${p.year_built}</span>` : ""}</div>
      <div class="pcard-actions">
        <button class="btn soft sm" data-act="details">Details</button>
        <button class="btn ghost sm ${inCmp ? "on" : ""}" data-act="cmp">${icon(inCmp ? "check" : "columns")}<span class="lbl">${inCmp ? "Added" : "Compare"}</span></button>
        <button class="btn primary sm" data-act="book">Book</button>
      </div>
    </div></article>`;
}
function syncHearts() {
  $$('[data-act="fav"]').forEach((el) => {
    const on = S.favs.has(pidOf(el));
    el.classList.toggle("on", on);
    const svg = $("svg", el); if (svg) svg.classList.toggle("filled", on);
    const lbl = $(".lbl", el); if (lbl) lbl.textContent = on ? "Saved" : "Save";
  });
}
function syncCompare() {
  $$('[data-act="cmp"]').forEach((el) => {
    const on = S.compare.includes(pidOf(el));
    el.classList.toggle("on", on);
    const lbl = $(".lbl", el); if (lbl) lbl.textContent = on ? "Added" : "Compare";
    const svg = $("svg", el); if (svg) svg.innerHTML = IC[on ? "check" : "columns"];
  });
  renderTray(); updateBadges();
}

/* ───────────────────────── nav / tabs ───────────────────────── */
function renderNav() {
  const html = TABS.map((t) => `<button class="nav-btn ${S.tab === t.id ? "active" : ""}" data-act="tab" data-tab="${t.id}">${icon(t.icon)}<span>${t.label}</span><span class="nav-badge" data-badge="${t.id}"></span></button>`).join("");
  $("#side-nav").innerHTML = html;
  $("#bottom-nav").innerHTML = html;
  updateBadges();
}
function updateBadges() {
  const counts = { favorites: S.favs.size, compare: S.compare.length, viewings: S.apptCount };
  $$("[data-badge]").forEach((b) => { const n = counts[b.dataset.badge] || 0; b.textContent = n; b.classList.toggle("show", n > 0); });
}
function switchTab(id) {
  if (!TABS.some((t) => t.id === id)) id = "chat";
  S.tab = id;
  document.body.dataset.tab = id;
  $$(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-" + id));
  $$(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === id));
  $("#page-title").textContent = TABS.find((t) => t.id === id).title;
  if (location.hash !== "#" + id) history.replaceState(null, "", "#" + id);
  ({ explore: openExplore, favorites: renderFavorites, compare: renderCompare, viewings: loadViewings }[id] || (() => {}))();
  renderTray();
  if (id === "chat") scrollChat();
}
function renderUser() {
  const initial = (S.name || "G").trim().charAt(0).toUpperCase() || "G";
  const html = `<span class="avatar">${esc(initial)}</span><span class="who"><b>${esc(S.name)}</b><span>${S.verified ? esc(S.contact) : "Sign in to save your account"}</span></span>`;
  $("#user-chip-side").innerHTML = html;
  $("#user-chip-top").innerHTML = html;
}
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  save("lh.theme", t);
  $("#theme-btn").innerHTML = icon(t === "dark" ? "sun" : "moon");
}

/* ───────────────────────── session ───────────────────────── */
let sessionP = null;
function applyMe(me) {
  const changed = S.cid != null && S.cid !== me.customer_id;
  S.cid = me.customer_id; S.name = me.name; S.verified = !!me.verified; S.contact = me.contact || "";
  renderUser();
  return changed;
}
// The server keeps the real identity in an HttpOnly signed cookie; the id here is only for display logic.
async function ensureSession(opt = {}) {
  if (S.cid && !opt.force) return S.cid;
  if (sessionP && !opt.force) return sessionP;
  sessionP = (async () => {
    const me = await api("/api/session", { method: "POST", body: "{}" });
    S.sessionChanged = applyMe(me);
    if (S.sessionChanged) { S.favs = new Set(); S.favCards = []; S.appts = []; S.apptCount = 0; S.viewingsLoaded = false; S.cmpData = null; }
    refreshFavs(); refreshAppts();
    return S.cid;
  })();
  try { return await sessionP; } finally { sessionP = null; }
}
async function refreshFavs() {
  try {
    const r = await api(`/api/favorites`);
    S.favs = new Set(r.ids); S.favCards = r.properties; cache(r.properties);
    syncHearts(); updateBadges();
    if (S.tab === "favorites") renderFavorites();
  } catch (e) { /* non-fatal */ }
}
async function refreshAppts() {
  try {
    const r = await api(`/api/appointments`);
    S.appts = r.appointments; S.apptCount = r.appointments.filter((a) => parseYMD(a.appointment_date) >= startOfToday()).length;
    updateBadges();
    if (S.tab === "viewings") loadViewings();
  } catch (e) { /* non-fatal */ }
}

/* ───────────────────────── chat ───────────────────────── */
const SUGGESTIONS = [
  "3-bedroom house in Seattle under $900k", "Cheapest condos in Bellevue", "Family home near good transit with a garden",
  "What's a fair price per sqft in Kirkland?",
];
const TOOL_LABEL = {
  search_properties: "Searched listings", get_property_details: "Looked up details", compare_properties: "Compared homes",
  save_feedback: "Noted your feedback", get_customer_memory: "Recalled your preferences", get_available_slots: "Checked open slots",
  book_appointment: "Booked a viewing", list_appointments: "Checked your viewings", cancel_appointment: "Cancelled a viewing",
  add_favorite: "Saved to favorites", list_favorites: "Looked at your favorites",
};
function fmtText(text) {
  return String(text || "").split("\n").map((l) => {
    const t = esc(l).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    const m = t.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
    return m ? `<span class="li">${m[1]}</span>` : t.trim() ? t + "<br>" : "<br>";
  }).join("").replace(/(<br>)+$/, "");
}
const scrollChat = () => requestAnimationFrame(() => { const l = $("#chat-log"); l.scrollTop = l.scrollHeight; });
function renderWelcome() {
  $("#chat-log").innerHTML = `<div class="welcome" id="welcome"><div class="logo">${icon("home")}</div><h2>Find a home you'll love.</h2><p>Tell me what you're looking for in plain language — budget, city, bedrooms, lifestyle. I'll search, compare and book viewings for you.</p><div class="chips">${SUGGESTIONS.map((q) => `<button class="chip" data-act="suggest" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div></div>`;
}
function addMsg(role, bodyHTML, { err = false, extra = "" } = {}) {
  $("#welcome")?.remove();
  const el = document.createElement("div");
  el.className = "msg " + role;
  el.innerHTML = `<div class="avatar">${role === "user" ? esc((S.name || "G").charAt(0).toUpperCase()) : icon("sparkles")}</div><div class="msg-main"><div class="bubble ${err ? "err" : ""}" dir="auto">${bodyHTML}</div>${extra}</div>`;
  $("#chat-log").appendChild(el);
  scrollChat();
  return el;
}
async function loadHistory() {
  try {
    const r = await api(`/api/history?limit=30`);
    const msgs = (r.messages || []).filter((m) => m.role === "user" || m.role === "assistant");
    if (!msgs.length) return;
    $("#chat-log").innerHTML = `<div class="divider">Earlier conversation</div>`;
    msgs.forEach((m) => addMsg(m.role === "user" ? "user" : "bot", fmtText(m.content)));
    const d = document.createElement("div"); d.className = "divider"; d.textContent = "Today"; $("#chat-log").appendChild(d);
    scrollChat();
  } catch (e) { /* history is a nicety */ }
}
async function send(text) {
  text = (text || "").trim();
  if (!text || S.sending) return;
  S.sending = true;
  $("#send").disabled = true;
  addMsg("user", fmtText(text));
  const typing = addMsg("bot", `<span class="typing"><i></i><i></i><i></i></span>`);
  try {
    await ensureSession();
    const r = await post("/api/chat", { message: text });
    typing.remove();
    cache(r.properties);
    let extra = "";
    const pills = (r.tools || []).map((t) => `<span class="pill ${t.ok ? "ok" : "err"}">${icon(t.ok ? "check" : "x")} ${esc(TOOL_LABEL[t.name] || t.name.replace(/_/g, " "))}</span>`).join("");
    if (pills) extra += `<div class="tool-pills">${pills}</div>`;
    if (r.properties && r.properties.length) extra += `<div class="msg-cards"><div class="cards-row">${r.properties.map(cardHTML).join("")}</div>${r.compare_ids && r.compare_ids.length > 1 ? `<div><button class="btn soft sm" data-act="open-compare" data-ids="${esc(r.compare_ids.join(","))}">${icon("columns")} Open side-by-side comparison</button></div>` : ""}</div>`;
    addMsg("bot", fmtText(r.reply), { extra });
    const names = (r.tools || []).filter((t) => t.ok).map((t) => t.name);
    if (names.some((n) => /appointment/.test(n))) {
      await refreshAppts();
      if (names.includes("book_appointment")) toast("Viewing booked", "", { label: "View", fn: () => switchTab("viewings") });
    }
    if (names.includes("add_favorite")) refreshFavs();
  } catch (e) {
    typing.remove();
    addMsg("bot", esc(e.message), { err: true });
  } finally {
    S.sending = false;
    $("#send").disabled = false;
    $("#input").focus({ preventScroll: true });
  }
}
function askAI(text) { switchTab("chat"); send(text); }

/* ───────────────────────── shared bits ───────────────────────── */
const TAXINS = 0.012; // rough property tax + insurance, share of price per year
function monthly(price, m = S.mort) {
  const loan = price * (1 - m.down / 100), r = m.rate / 100 / 12, n = m.years * 12;
  if (!loan) return 0;
  return r ? (loan * r) / (1 - Math.pow(1 + r, -n)) : loan / n;
}
function emptyState({ ic, title, text, buttons = "" }) {
  return `<div class="empty"><div class="big">${icon(ic)}</div><h3>${esc(title)}</h3><p>${esc(text)}</p><div class="row">${buttons}</div></div>`;
}
const skelGrid = (n = 6) => `<div class="grid">${'<div class="skel card"></div>'.repeat(n)}</div>`;
const whereOf = (p) => [p.neighborhood, p.city].filter(Boolean).join(", ");

async function toggleFav(pid) {
  await ensureSession();
  const was = S.favs.has(pid);
  was ? S.favs.delete(pid) : S.favs.add(pid);
  syncHearts(); updateBadges();
  try {
    await api(`/api/favorites/${encodeURIComponent(pid)}`, { method: was ? "DELETE" : "POST" });
    toast(was ? "Removed from saved" : "Saved to your favorites");
    refreshFavs();
  } catch (e) {
    was ? S.favs.add(pid) : S.favs.delete(pid);
    syncHearts(); updateBadges();
    throw e;
  }
}
function toggleCompare(pid) {
  if (!pid) return;
  if (S.compare.includes(pid)) S.compare = S.compare.filter((x) => x !== pid);
  else if (S.compare.length >= 4) return toast("You can compare up to 4 homes at once", "warn");
  else S.compare.push(pid);
  save("lh.compare", S.compare);
  syncCompare();
  if (S.tab === "compare") renderCompare();
}
function renderTray() {
  const t = $("#tray"), ids = S.compare, show = ids.length > 0 && S.tab !== "compare";
  t.classList.toggle("show", show);
  document.body.classList.toggle("has-tray", show);
  if (!show) return;
  t.innerHTML = `<div class="thumbs">${ids.map((id) => `<div class="thumb" data-act="cmp" data-pid="${esc(id)}" title="Remove">${S.props[id] ? houseArt(S.props[id]) : ""}<i>${icon("x")}</i></div>`).join("")}</div><span class="tray-text">${ids.length} of 4</span><button class="btn primary sm" data-act="go-compare" ${ids.length < 2 ? "disabled" : ""}>${ids.length < 2 ? "Add one more" : "Compare now"}</button><button class="x" data-act="cmp-clear" aria-label="Clear selection">${icon("x")}</button>`;
}
async function hydrateCompare() {
  const missing = S.compare.filter((id) => !S.props[id]);
  await Promise.all(missing.map((id) => api(`/api/property/${id}`).then((p) => cache([p])).catch(() => { S.compare = S.compare.filter((x) => x !== id); })));
  save("lh.compare", S.compare); syncCompare();
}

/* ───────────────────────── explore ───────────────────────── */
const FLAG_LABEL = { parking: "Parking", garden: "Garden / yard", near_metro: "Near transit", pet_friendly: "Pet-friendly" };
async function openExplore() {
  if (S.exploreInit) return;
  S.exploreInit = true;
  const page = $("#tab-explore .page");
  page.innerHTML = `<div class="skel" style="height:150px;margin-bottom:16px"></div>${skelGrid()}`;
  try { S.meta = await api("/api/meta"); } catch (e) { S.meta = { cities: [], flags: {}, types: [] }; }
  const m = S.meta, sel = (name, label, opts) => `<label class="field"><span>${label}</span><select name="${name}">${opts}</select></label>`;
  const nOpts = (any) => `<option value="">${any}</option>` + [1, 2, 3, 4, 5].map((n) => `<option value="${n}">${n}+</option>`).join("");
  page.innerHTML = `<div class="page-head"><div><h2>Explore homes</h2><p>${m.total ? `${m.total.toLocaleString()} listings` : "Browse listings"}${m.min_price ? ` · from ${money(m.min_price)} to ${money(m.max_price)}` : ""}</p></div></div>
  <form class="filters" id="f-form" autocomplete="off">
    ${sel("city", "City", `<option value="">All cities</option>` + (m.cities || []).map((c) => `<option value="${esc(c.city)}">${esc(c.city)} (${c.n})</option>`).join(""))}
    ${sel("type", "Type", `<option value="">Any type</option>` + (m.types || []).map((t) => `<option>${esc(t)}</option>`).join(""))}
    ${sel("beds", "Bedrooms", nOpts("Any"))}
    ${sel("baths", "Bathrooms", nOpts("Any"))}
    <label class="field"><span>Min price</span><input name="pmin" placeholder="e.g. 400k" inputmode="decimal"></label>
    <label class="field"><span>Max price</span><input name="pmax" placeholder="e.g. 1.2m" inputmode="decimal"></label>
    <label class="field"><span>Min size (sqft)</span><input name="area" placeholder="e.g. 1500" inputmode="numeric"></label>
    ${sel("sort", "Sort by", `<option value="match">Best match</option><option value="price_asc">Price: low to high</option><option value="price_desc">Price: high to low</option><option value="area_desc">Largest first</option><option value="newest">Newest built</option>`)}
    <div class="full">${Object.keys(FLAG_LABEL).filter((f) => (m.flags || {})[f] > 0).map((f) => `<button type="button" class="chip toggle" data-flag="${f}">${FLAG_LABEL[f]}</button>`).join("")}<span style="flex:1"></span><button type="button" class="btn ghost" data-act="f-reset">Reset</button><button class="btn primary" type="submit">${icon("search")} Search</button></div>
  </form><div id="results"></div>`;
  const form = $("#f-form");
  form.addEventListener("submit", (e) => { e.preventDefault(); runSearch(true); });
  $$("select", form).forEach((s) => s.addEventListener("change", () => runSearch(true)));
  $$("[data-flag]", form).forEach((c) => c.addEventListener("click", () => { c.classList.toggle("on"); runSearch(true); }));
  runSearch(true);
}
function readFilters() {
  const f = $("#f-form"), v = (n) => f.elements[n].value;
  const out = { city: v("city") || null, property_type: v("type") || null, bedrooms: num(v("beds")), bathrooms: num(v("baths")), budget_min: num(v("pmin")), budget_max: num(v("pmax")), min_area: num(v("area")), sort: v("sort") };
  $$("[data-flag].on", f).forEach((c) => (out[c.dataset.flag] = true));
  return out;
}
async function runSearch(reset) {
  const box = $("#results"); if (!box) return;
  const page = $("#tab-explore .page"), top = page.scrollTop;
  if (reset) { S.explore.limit = 12; box.innerHTML = skelGrid(6); }
  try {
    const r = await post("/api/search", { ...readFilters(), limit: S.explore.limit });
    cache(r.properties);
    if (!r.properties.length) {
      box.innerHTML = emptyState({ ic: "search", title: "No homes match those filters", text: "Try a wider price range or fewer filters.", buttons: `<button class="btn primary" data-act="f-reset">Reset filters</button>` });
      return;
    }
    box.innerHTML = `<div class="results-bar"><span><b>${r.count.toLocaleString()}</b> homes match · showing ${r.showing}</span></div><div class="grid">${r.properties.map(cardHTML).join("")}</div>${r.showing < Math.min(r.count, 60) ? `<div class="more"><button class="btn ghost" data-act="more">Show more homes</button></div>` : ""}`;
    if (!reset) page.scrollTop = top;
  } catch (e) {
    box.innerHTML = emptyState({ ic: "search", title: "Search didn't work", text: e.message, buttons: `<button class="btn primary" data-act="f-retry">Try again</button>` });
  }
}

/* ───────────────────────── favorites ───────────────────────── */
function renderFavorites() {
  const page = $("#tab-favorites .page"), list = S.favCards.filter((p) => S.favs.has(p.property_id));
  if (!list.length) {
    page.innerHTML = emptyState({ ic: "heart", title: "Nothing saved yet", text: "Tap the heart on any home to keep it here. Saved homes also teach me what you like.", buttons: `<button class="btn primary" data-act="tab" data-tab="explore">Explore homes</button><button class="btn ghost" data-act="tab" data-tab="chat">Ask the AI</button>` });
    return;
  }
  const ids = list.map((p) => p.property_id);
  page.innerHTML = `<div class="page-head"><div><h2>Saved homes</h2><p>${list.length} home${list.length === 1 ? "" : "s"} you liked</p></div><div class="row">${list.length > 1 ? `<button class="btn soft" data-act="cmp-saved">${icon("columns")} Compare saved</button><button class="btn ghost" data-act="pick-saved">${icon("sparkles")} Which should I see first?</button>` : ""}</div></div><div class="grid">${list.map(cardHTML).join("")}</div>`;
  page.dataset.ids = ids.join(",");
}

/* ───────────────────────── compare ───────────────────────── */
async function renderCompare() {
  const page = $("#tab-compare .page"), ids = S.compare.slice();
  if (ids.length < 2) {
    page.innerHTML = emptyState({ ic: "columns", title: ids.length ? "Add one more home" : "Pick homes to compare", text: "Tap Compare on two to four homes — in chat, Explore or Saved — and they line up here side by side, with the best value in each row highlighted.", buttons: `<button class="btn primary" data-act="tab" data-tab="explore">Browse homes</button>${S.favs.size > 1 ? `<button class="btn ghost" data-act="cmp-saved">Use my saved homes</button>` : ""}` });
    return;
  }
  const key = ids.join(",");
  if (!S.cmpData || S.cmpData.key !== key) {
    page.innerHTML = `<div class="page-head"><div><h2>Compare homes</h2></div></div><div class="skel" style="height:460px"></div>`;
    try {
      const d = await api("/api/compare?ids=" + encodeURIComponent(key));
      cache(d.properties); S.cmpData = { key, data: d };
    } catch (e) {
      page.innerHTML = emptyState({ ic: "columns", title: "Couldn't load the comparison", text: e.message, buttons: `<button class="btn primary" data-act="go-compare">Retry</button>` });
      return;
    }
    if (S.tab !== "compare" || S.compare.join(",") !== key) return;
  }
  drawCompare();
}
function cmpRows(ps) {
  const sale = !ps.some((p) => /rent/i.test(p.listing_type || ""));
  const defs = [
    ["Price", (p) => p.price, money, "min"],
    ["Price / sqft", (p) => p.price_per_sqft, (v) => money(v) + "/sqft", "min"],
    ...(sale ? [["Est. monthly cost", (p) => (p.price ? monthly(p.price) + (p.price * TAXINS) / 12 : null), (v) => money(v) + "/mo", "min"]] : []),
    ["vs. city average", (p) => p.vs_city_pct, pctTxt, "min"],
    ["Bedrooms", (p) => p.bedrooms, (v) => v, "max"],
    ["Bathrooms", (p) => p.bathrooms, (v) => v, "max"],
    ["Living area", (p) => p.area_sqft, (v) => v.toLocaleString() + " sqft", "max"],
    ["Year built", (p) => p.year_built, (v) => v, "max"],
    ["Condition", (p) => p.property_condition, esc, null],
    ["Type", (p) => p.property_type, esc, null],
    ["Location", whereOf, esc, null],
  ];
  let html = defs.map(([label, get, fmt, best]) => {
    const vals = ps.map(get), nums = vals.filter((v) => typeof v === "number");
    const bv = best && nums.length > 1 && new Set(nums).size > 1 ? (best === "min" ? Math.min(...nums) : Math.max(...nums)) : null;
    return `<tr><td>${label}</td>${vals.map((v) => `<td class="${bv != null && v === bv ? "best" : ""}">${v == null || v === "" ? "—" : fmt(v)}</td>`).join("")}</tr>`;
  }).join("");
  html += AMEN.filter(([k]) => ps.some((p) => p[k])).map(([k, l]) => `<tr><td>${l}</td>${ps.map((p) => `<td>${p[k] ? '<span class="yes">✓ Yes</span>' : '<span class="no">—</span>'}</td>`).join("")}</tr>`).join("");
  return html;
}
function drawCompare() {
  const page = $("#tab-compare .page"), { data } = S.cmpData, ps = data.properties, w = data.winners || {};
  const LAB = { price: "lowest price", price_per_sqft: "best value per sqft", area_sqft: "most space", year_built: "newest build", bedrooms: "most bedrooms" };
  const lead = ps.find((p) => p.property_id === w.overall);
  const reasons = lead ? Object.keys(LAB).filter((k) => (w[k] || []).includes(lead.property_id)).map((k) => LAB[k]) : [];
  const chips = Object.keys(LAB).filter((k) => w[k]).map((k) => `<span class="pill">${icon("check")} ${LAB[k]}: ${esc(w[k].join(" & "))}</span>`).join("");
  const head = (p) => `<div class="cmp-head" data-pid="${esc(p.property_id)}"><div class="art" data-act="details">${houseArt(p)}</div><button class="x" data-act="cmp" title="Remove from comparison" aria-label="Remove">${icon("x")}</button><div><div class="pid">${esc(p.property_id)} · ${esc(p.property_type || "")}</div><div class="price">${money(p.price)}</div><div class="loc">${icon("pin")}<span>${esc(whereOf(p))}</span></div></div><div class="row"><button class="btn soft sm" data-act="details">Details</button><button class="btn primary sm" data-act="book">Book</button></div></div>`;
  page.innerHTML = `<div class="page-head"><div><h2>Compare homes</h2><p>${ps.length} homes side by side · best value highlighted in green</p></div><div class="row">${ps.length < 4 ? `<button class="btn ghost" data-act="tab" data-tab="explore">${icon("plus")} Add a home</button>` : ""}<button class="btn soft" data-act="ask-compare">${icon("sparkles")} Ask the AI to compare</button><button class="btn ghost" data-act="cmp-clear">Clear</button></div></div>
  ${lead ? `<div class="winner-card"><div class="trophy">${icon("trophy")}</div><div class="txt"><b>${esc(lead.property_id)} · ${esc(whereOf(lead))}</b> looks like the best all-round value${reasons.length ? ` — it wins on ${reasons.join(", ")}` : ""}.<div class="tool-pills" style="margin-top:8px">${chips}</div></div></div>` : `<div class="winner-card"><div class="trophy">${icon("scale")}</div><div class="txt"><b>These homes are neck and neck.</b> The table below shows where they trade off.</div></div>`}
  <div class="assume"><label class="field"><span>Down payment %</span><input type="number" min="3" max="90" step="1" value="${S.mort.down}" data-cm="down"></label><label class="field"><span>Interest rate %</span><input type="number" min="0.5" max="15" step="0.05" value="${S.mort.rate}" data-cm="rate"></label><label class="field"><span>Loan term</span><select data-cm="years">${[15, 20, 30].map((y) => `<option value="${y}" ${S.mort.years === y ? "selected" : ""}>${y} years</option>`).join("")}</select></label><small>Monthly cost = mortgage payment plus a rough ${(TAXINS * 100).toFixed(1)}%/yr for property tax &amp; insurance. Adjust to match your own numbers.</small></div>
  <div class="cmp-wrap"><table class="cmp"><thead><tr><th></th>${ps.map((p) => `<th>${head(p)}</th>`).join("")}</tr></thead><tbody>${cmpRows(ps)}</tbody></table></div>
  <p class="note">City average compares each home with all sale listings in the same city. Estimates are for planning only, not a loan offer.</p>`;
}

/* ───────────────────────── viewings ───────────────────────── */
async function loadViewings() {
  const page = $("#tab-viewings .page");
  if (!S.viewingsLoaded) page.innerHTML = `<div class="page-head"><div><h2>Your viewings</h2></div></div><div class="skel" style="height:140px;margin-bottom:14px"></div><div class="skel" style="height:140px"></div>`;
  try {
    await ensureSession();
    const r = await api(`/api/appointments?include_history=${S.showHistory ? 1 : 0}`);
    S.viewingsLoaded = true;
    const today = startOfToday(), upcoming = r.appointments.filter((a) => a.status === "scheduled" && parseYMD(a.appointment_date) >= today);
    const past = r.appointments.filter((a) => !upcoming.includes(a)).reverse();
    S.apptCount = upcoming.length; updateBadges();
    r.appointments.forEach((a) => cache([{ property_id: a.property_id, property_type: a.property_type, city: a.city, neighborhood: a.neighborhood, price: a.price }]));
    const head = `<div class="page-head"><div><h2>Your viewings</h2><p>${upcoming.length ? `${upcoming.length} upcoming` : "Nothing scheduled yet"}</p></div><div class="row"><button class="btn ghost" data-act="history">${S.showHistory ? "Hide history" : "Show history"}</button><button class="btn primary" data-act="tab" data-tab="explore">${icon("plus")} Book another</button></div></div>`;
    if (!upcoming.length && !past.length) {
      page.innerHTML = head + emptyState({ ic: "calendar", title: "No viewings booked", text: "Find a home you like and pick a time — or just tell the AI “book me a viewing for Saturday morning”.", buttons: `<button class="btn primary" data-act="tab" data-tab="explore">Explore homes</button><button class="btn ghost" data-act="tab" data-tab="chat">Ask the AI</button>` });
      return;
    }
    page.innerHTML = head + (upcoming.length ? `<div class="group-title">${icon("calendar")} Upcoming</div>${upcoming.map(apptHTML).join("")}` : "") + (past.length ? `<div class="group-title">Past &amp; cancelled</div>${past.map(apptHTML).join("")}` : "");
  } catch (e) {
    page.innerHTML = emptyState({ ic: "calendar", title: "Couldn't load your viewings", text: e.message, buttons: `<button class="btn primary" data-act="history-retry">Try again</button>` });
  }
}
function apptHTML(a) {
  const d = parseYMD(a.appointment_date), past = a.status === "scheduled" && d < startOfToday(), active = a.status === "scheduled" && !past;
  const pill = a.status === "cancelled" ? `<span class="pill cancelled">Cancelled</span>` : past ? `<span class="pill past">Completed</span>` : `<span class="pill scheduled">${icon("check")} Confirmed</span>`;
  return `<article class="appt ${a.status === "cancelled" ? "cancelled" : ""}" data-pid="${esc(a.property_id)}" data-aid="${a.appointment_id}">
    <div class="date-block"><div class="m">${MONTHS[d.getMonth()]}</div><div class="d">${String(d.getDate()).padStart(2, "0")}</div><div class="w">${WEEKDAYS[d.getDay()].slice(0, 3)}</div></div>
    <div class="appt-art" data-act="details">${houseArt({ property_id: a.property_id, property_type: a.property_type })}</div>
    <div class="appt-main"><div class="row" style="gap:8px">${pill}<span class="muted">${esc(relDay(a.appointment_date))} · ${fmtTime(a.appointment_time)}</span></div>
      <h3>${esc(a.property_type || "Home")} in ${esc(whereOf(a) || a.property_id)}</h3>
      <div class="meta"><span>${esc(a.property_id)}</span>${a.price ? `<span>${money(a.price)}</span>` : ""}${a.bedrooms != null ? `<span>${a.bedrooms} bd · ${a.bathrooms ?? "—"} ba · ${a.area_sqft ? a.area_sqft.toLocaleString() : "—"} sqft</span>` : ""}</div>
      ${a.maps_url ? `<div class="meta" style="margin-top:4px"><a href="${esc(a.maps_url)}" target="_blank" rel="noopener" style="color:var(--brand);text-decoration:none">${icon("nav")} ${esc(a.address || "Open in Maps")}</a></div>` : ""}
      ${a.notes ? `<div class="notes">${esc(a.notes)}</div>` : ""}</div>
    <div class="appt-actions">${active ? `<a class="btn ghost sm" href="/api/appointments/${a.appointment_id}/ics" download>${icon("calplus")} Add to calendar</a><button class="btn soft sm" data-act="resched" data-aid="${a.appointment_id}">${icon("pencil")} Reschedule</button><button class="btn danger sm" data-act="cancel" data-aid="${a.appointment_id}">Cancel</button>` : `<button class="btn ghost sm" data-act="details">View home</button>`}</div></article>`;
}

/* ───────────────────────── property details ───────────────────────── */
function marketRow(label, val, avg, pct, fmt, city) {
  if (!avg || val == null) return "";
  const pos = Math.max(4, Math.min(96, (val / (avg * 2)) * 100)), small = pct == null || Math.abs(pct) < 1;
  const txt = small ? "about average" : `${Math.abs(pct)}% ${pct < 0 ? "below" : "above"} average`;
  return `<div><div class="row" style="justify-content:space-between"><b>${label}</b><span class="delta ${small ? "" : pct < 0 ? "down" : "up"}">${txt}</span></div><div class="bar"><div class="fill" style="width:${pos}%"></div><div class="avg"></div><div class="mark" style="left:${pos}%"></div></div><div class="bar-lab"><span>${fmt(val)} this home</span><span>${fmt(avg)} ${esc(city)} avg</span></div></div>`;
}
function mortHTML(p) {
  const m = S.mort;
  return `<div class="mort" data-price="${p.price}"><div><div class="eyebrow">Estimated monthly cost</div><div class="big" id="m-total">—</div><div class="muted" style="font-size:12.5px;margin-top:4px">mortgage + rough tax &amp; insurance</div></div>
  <div class="mort-controls"><label>Down payment <b id="m-down-v">${m.down}%</b><input type="range" min="5" max="50" step="1" value="${m.down}" data-mort="down"></label><label>Interest rate <b id="m-rate-v">${m.rate}%</b><input type="range" min="2" max="10" step="0.05" value="${m.rate}" data-mort="rate"></label><label>Loan term <select data-mort="years">${[15, 20, 30].map((y) => `<option value="${y}" ${m.years === y ? "selected" : ""}>${y} years</option>`).join("")}</select></label></div>
  <div class="mort-break" id="m-break"></div></div>`;
}
function mortOut(root) {
  const box = $(".mort", root || document); if (!box) return;
  const price = +box.dataset.price, m = S.mort, pi = monthly(price), ti = (price * TAXINS) / 12;
  $("#m-total", box).textContent = money(pi + ti) + "/mo";
  $("#m-down-v", box).textContent = m.down + "%"; $("#m-rate-v", box).textContent = m.rate + "%";
  $("#m-break", box).innerHTML = `<span>Down payment <b>${money((price * m.down) / 100)}</b></span><span>Loan <b>${money(price * (1 - m.down / 100))}</b></span><span>Mortgage <b>${money(pi)}</b></span><span>Tax &amp; insurance ≈ <b>${money(ti)}</b></span>`;
}
function detailsHTML(p) {
  const fav = S.favs.has(p.property_id), inCmp = S.compare.includes(p.property_id), ins = p.insights || {}, sale = !/rent/i.test(p.listing_type || "");
  const tags = AMEN.filter(([k]) => p[k]).map(([, l]) => `<span class="tag">${icon("check")} ${l}</span>`).join("");
  const market = ins.avg_price ? `<div><div class="sec-title">How it stacks up in ${esc(ins.city)}</div><div class="market">${marketRow("Price", p.price, ins.avg_price, ins.price_vs_city_pct, money, ins.city)}${marketRow("Price per sqft", p.price_per_sqft, ins.avg_price_per_sqft, ins.ppsf_vs_city_pct, (v) => money(v), ins.city)}<div class="muted" style="font-size:12px">Compared with ${ins.listings_in_city ? ins.listings_in_city.toLocaleString() : "all"} sale listings in ${esc(ins.city)}.</div></div></div>` : "";
  return `${closeBtn()}<div class="det-art">${houseArt(p)}</div>
  <div class="det-body" data-pid="${esc(p.property_id)}">
    <div class="det-head"><div><div class="eyebrow">${esc(p.property_id)} · ${esc(p.property_type || "Home")} · For ${/rent/i.test(p.listing_type || "") ? "rent" : "sale"}</div><div class="det-price">${money(p.price)}${sale ? "" : "<small>/mo</small>"}</div><div class="loc">${icon("pin")}<span>${esc(p.address || whereOf(p))}</span></div></div>
      <div class="row"><button class="btn ghost ${fav ? "on" : ""}" data-act="fav" data-pid="${esc(p.property_id)}">${icon("heart", fav)}<span class="lbl">${fav ? "Saved" : "Save"}</span></button><button class="btn ghost ${inCmp ? "on" : ""}" data-act="cmp" data-pid="${esc(p.property_id)}">${icon(inCmp ? "check" : "columns")}<span class="lbl">${inCmp ? "Added" : "Compare"}</span></button>${p.maps_url ? `<a class="btn ghost" href="${esc(p.maps_url)}" target="_blank" rel="noopener">${icon("nav")} Map</a>` : ""}</div></div>
    <div class="stat-grid"><div class="stat"><b>${p.bedrooms ?? "—"}</b><span>Bedrooms</span></div><div class="stat"><b>${p.bathrooms ?? "—"}</b><span>Bathrooms</span></div><div class="stat"><b>${p.area_sqft ? p.area_sqft.toLocaleString() : "—"}</b><span>Square feet</span></div><div class="stat"><b>${p.price_per_sqft ? money(p.price_per_sqft) : "—"}</b><span>Per sqft</span></div><div class="stat"><b>${p.year_built ?? "—"}</b><span>Year built</span></div>${p.property_condition ? `<div class="stat"><b>${esc(p.property_condition)}</b><span>Condition</span></div>` : ""}</div>
    ${tags ? `<div><div class="sec-title">Features</div><div class="tags">${tags}</div></div>` : ""}
    ${p.description ? `<div><div class="sec-title">About this home</div><p class="desc">${esc(p.description)}</p></div>` : ""}
    ${market}
    ${sale && p.price ? `<div><div class="sec-title">Monthly cost estimate</div>${mortHTML(p)}</div>` : ""}
    ${(p.similar || []).length ? `<div><div class="sec-title">Similar homes in ${esc(p.city)}</div><div class="cards-row">${p.similar.map(cardHTML).join("")}</div></div>` : ""}
  </div>
  <div class="det-foot"><button class="btn primary" data-act="book" data-pid="${esc(p.property_id)}">${icon("calendar")} Book a viewing</button><button class="btn soft" data-act="ask-about" data-pid="${esc(p.property_id)}">${icon("sparkles")} Ask AI</button></div>`;
}
async function openDetails(pid) {
  if (!pid) return;
  const m = openModal(`${closeBtn()}<div class="modal-pad"><div class="skel" style="height:220px"></div><div class="skel" style="height:34px;width:55%;margin-top:18px"></div><div class="skel" style="height:90px;margin-top:14px"></div></div>`, { cls: "details" });
  try {
    const p = await api(`/api/property/${encodeURIComponent(pid)}`);
    cache([p, ...(p.similar || [])]);
    if (!modalCtl || !modalCtl.ov.contains(m)) return;
    m.innerHTML = detailsHTML(p); m.scrollTop = 0; mortOut(m);
  } catch (e) { closeModal(); throw e; }
}

/* ───────────────────────── booking ───────────────────────── */
async function openBooking({ pid, appt = null }) {
  await ensureSession();
  let p = S.props[pid];
  if (!p || !p.price) { p = await api(`/api/property/${encodeURIComponent(pid)}`); cache([p]); }
  const today = new Date(), sel = { date: appt ? appt.appointment_date : ymd(addDays(today, 1)), time: null }, resched = !!appt;
  const days = Array.from({ length: 10 }, (_, i) => addDays(today, i));
  const m = openModal(`${closeBtn()}<div class="modal-pad">
    <div class="eyebrow">${resched ? "Reschedule viewing" : "Book a viewing"}</div><h2>Pick a day &amp; time</h2>
    <div class="sum"><div class="thumb">${houseArt(p)}</div><div><b>${esc(p.property_type || "Home")} · ${money(p.price)}</b><div class="muted">${esc(whereOf(p))} · ${esc(p.property_id)}</div></div></div>
    <div class="field"><span>Day</span></div><div class="days" id="bk-days">${days.map((d, i) => `<button class="day" data-d="${ymd(d)}"><small>${i === 0 ? "Today" : WEEKDAYS[d.getDay()].slice(0, 3)}</small><b>${d.getDate()}</b></button>`).join("")}</div>
    <label class="field" style="margin:4px 0 14px"><span>Or choose another date</span><input type="date" id="bk-date" min="${ymd(today)}" max="${ymd(addDays(today, 180))}" value="${sel.date}"></label>
    <div class="field"><span>Time</span></div><div class="slots" id="bk-slots"></div>
    <div class="slot-help">Viewings last about an hour. Greyed-out times are already taken.</div>
    ${resched ? "" : `<label class="field" style="margin-top:14px"><span>Notes for the agent (optional)</span><textarea id="bk-notes" rows="2" maxlength="500" dir="auto" placeholder="e.g. bringing my partner, would like to see the garage"></textarea></label>`}
    <p class="err-text" id="bk-err"></p>
    <div class="row" style="justify-content:flex-end"><button class="btn ghost" data-act="close-modal">Cancel</button><button class="btn primary" id="bk-go" disabled>${resched ? "Confirm new time" : "Confirm viewing"}</button></div></div>`);
  const slotsEl = $("#bk-slots", m), go = $("#bk-go", m), err = $("#bk-err", m), dateIn = $("#bk-date", m);
  let tok = 0;
  const markDay = () => $$(".day", m).forEach((b) => b.classList.toggle("sel", b.dataset.d === sel.date));
  const loadSlots = async () => {
    const t = ++tok; sel.time = null; go.disabled = true; err.textContent = "";
    slotsEl.innerHTML = `<span class="slot-help">Checking availability…</span>`; markDay();
    try {
      const r = await api(`/api/slots?property_id=${encodeURIComponent(pid)}&date=${sel.date}`);
      if (t !== tok) return;
      const now = new Date(), isToday = sel.date === ymd(now);
      const items = r.slots.map((s) => {
        const past = isToday && +s.time.slice(0, 2) <= now.getHours(), cur = resched && appt.appointment_date === sel.date && appt.appointment_time === s.time;
        return { ...s, off: !s.available || past, cur, why: cur ? "Your current time" : !s.available ? "Already booked" : past ? "Already passed" : "" };
      });
      slotsEl.innerHTML = items.every((i) => i.off && !i.cur) ? `<span class="slot-help">No open times that day — try another date.</span>` : items.map((i) => `<button class="slot ${i.cur ? "current" : ""}" data-t="${i.time}" ${i.off ? "disabled" : ""} title="${i.why}">${fmtTime(i.time)}</button>`).join("");
    } catch (e) { if (t === tok) slotsEl.innerHTML = `<span class="err-text">${esc(e.message)}</span>`; }
  };
  $("#bk-days", m).onclick = (e) => { const b = e.target.closest(".day"); if (b) { sel.date = b.dataset.d; dateIn.value = sel.date; loadSlots(); } };
  dateIn.onchange = () => { if (dateIn.value) { sel.date = dateIn.value; loadSlots(); } };
  slotsEl.onclick = (e) => { const b = e.target.closest(".slot"); if (!b || b.disabled) return; sel.time = b.dataset.t; $$(".slot", slotsEl).forEach((x) => x.classList.toggle("sel", x === b)); go.disabled = false; err.textContent = ""; };
  go.onclick = async () => {
    go.disabled = true; err.textContent = "";
    try {
      const base = { appointment_date: sel.date, appointment_time: sel.time };
      const r = resched ? await post(`/api/appointments/${appt.appointment_id}/reschedule`, base) : await post("/api/book", { ...base, property_id: pid, notes: $("#bk-notes", m).value });
      const aid = r.appointment_id || (r.appointment || {}).appointment_id;
      m.innerHTML = `${closeBtn()}<div class="success"><div class="check">${icon("check")}</div><h2>${resched ? "Viewing rescheduled" : "You're booked!"}</h2><div class="when">${esc(fmtDateLong(sel.date))} · ${fmtTime(sel.time)}</div><div class="muted">${esc(p.property_type || "Home")} in ${esc(whereOf(p))} · ${esc(p.property_id)}</div><div class="row"><a class="btn ghost" href="/api/appointments/${aid}/ics" download>${icon("calplus")} Add to calendar</a><button class="btn primary" data-act="tab" data-tab="viewings">See my viewings</button></div></div>`;
      S.viewingsLoaded = false; refreshAppts();
    } catch (e) { err.textContent = e.message; go.disabled = sel.time == null; if (/booked|taken/i.test(e.message)) loadSlots(); }
  };
  loadSlots();
}

/* ───────────────────────── profile ───────────────────────── */
async function applyAccount(me, { switched, merged } = {}) {
  applyMe(me);
  if (switched) { S.favs = new Set(); S.favCards = []; S.appts = []; S.apptCount = 0; S.cmpData = null; renderWelcome(); await loadHistory(); }
  S.viewingsLoaded = false;
  await Promise.all([refreshFavs(), refreshAppts()]);
  if (S.tab === "viewings") loadViewings();
  if (S.tab === "favorites") renderFavorites();
}
function openProfile() {
  const m = openModal(`${closeBtn()}<div class="modal-pad"><h2>Your account</h2>
    <label class="field" style="margin-top:14px"><span>Name</span><div class="row" style="flex-wrap:nowrap"><input id="pf-name" style="flex:1" value="${esc(S.name === "Guest" ? "" : S.name)}" placeholder="Your name" maxlength="60" dir="auto"><button class="btn soft" id="pf-name-save">Save</button></div></label>
    <div class="acct" id="pf-acct"></div></div>`, { cls: "small" });
  let timer = null, pending = null;
  const acct = $("#pf-acct", m);
  const stop = () => { if (timer) { clearInterval(timer); timer = null; } };
  const draw = () => {
    stop();
    if (S.verified) {
      acct.innerHTML = `<div class="acct-ok">${icon("check")} <span>Signed in as <b>${esc(S.contact)}</b></span></div><p class="muted" style="margin:8px 0 14px">Your chats, saved homes and viewings follow you on any device you sign in on.</p><button class="btn ghost sm" data-act="sign-out">Sign out</button>`;
    } else if (!pending) {
      acct.innerHTML = `<div class="eyebrow" style="margin-bottom:6px">Save your account</div><p class="muted" style="margin:0 0 12px">You're browsing as a guest. Add an email or phone number — we'll send a code to confirm it's you — and keep your saved homes and viewings safe on any device.</p>
        <label class="field"><span>Email or phone</span><input id="au-contact" inputmode="email" autocomplete="username" placeholder="you@example.com or +1 206 555 0123"></label>
        <p class="err-text" id="au-err"></p><div class="row" style="justify-content:space-between"><button class="btn danger sm" data-act="new-guest">Start fresh</button><button class="btn primary" id="au-send">Send code</button></div>`;
      $("#au-send", m).onclick = sendCode;
      $("#au-contact", m).addEventListener("keydown", (e) => { if (e.key === "Enter") sendCode(); });
    } else {
      acct.innerHTML = `<div class="eyebrow" style="margin-bottom:6px">Enter your code</div><p class="muted" style="margin:0 0 12px">We sent a 6-digit code to <b>${esc(pending.sent_to)}</b>. It expires in 10 minutes.</p>
        ${pending.dev_code ? `<div class="hint">Dev mode — your code is <b>${esc(pending.dev_code)}</b></div>` : ""}
        <label class="field"><span>6-digit code</span><input id="au-code" class="code-input" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="••••••"></label>
        <p class="err-text" id="au-err"></p><div class="row" style="justify-content:space-between"><button class="btn ghost sm" id="au-back">Use another</button><div class="row"><button class="btn ghost sm" id="au-resend" disabled>Resend</button><button class="btn primary" id="au-verify">Verify</button></div></div>`;
      $("#au-verify", m).onclick = verify; $("#au-back", m).onclick = () => { pending = null; draw(); };
      $("#au-resend", m).onclick = sendCode;
      $("#au-code", m).addEventListener("input", (e) => { e.target.value = e.target.value.replace(/\D/g, "").slice(0, 6); if (e.target.value.length === 6) verify(); });
      $("#au-code", m).focus();
      let left = 60; const rs = $("#au-resend", m);
      const tick = () => { if (!m.isConnected) return stop(); rs.disabled = left > 0; rs.textContent = left > 0 ? `Resend (${left}s)` : "Resend"; left--; };
      tick(); timer = setInterval(tick, 1000);
    }
  };
  async function sendCode() {
    const contact = pending ? pending.contact : $("#au-contact", m).value.trim(), err = $("#au-err", m), btn = $("#au-send", m) || $("#au-resend", m);
    if (!contact) { err.textContent = "Enter your email or phone number."; return; }
    btn.disabled = true; err.textContent = "";
    try { const r = await post("/api/auth/start", { contact }); pending = { contact, sent_to: r.sent_to, dev_code: r.dev_code }; draw(); }
    catch (e) { err.textContent = e.message; btn.disabled = false; }
  }
  async function verify() {
    const code = $("#au-code", m).value, err = $("#au-err", m), btn = $("#au-verify", m);
    if (code.length !== 6) { err.textContent = "Enter the 6-digit code."; return; }
    btn.disabled = true; err.textContent = "";
    try {
      const r = await post("/api/auth/verify", { contact: pending.contact, code });
      stop(); closeModal();
      await applyAccount(r, r);
      toast(r.switched ? `Welcome back, ${r.name}` : "Account saved — you're signed in");
    } catch (e) { err.textContent = e.message; btn.disabled = false; $("#au-code", m).select(); }
  }
  $("#pf-name-save", m).onclick = async () => {
    const name = $("#pf-name", m).value.trim(); if (!name) return toast("Enter a name first", "warn");
    try { applyMe(await api("/api/me", { method: "PATCH", body: JSON.stringify({ name }) })); toast("Name saved"); } catch (e) { toast(e.message, "err"); }
  };
  draw();
}

/* ───────────────────────── events ───────────────────────── */
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-act]"); if (!el) return;
  const act = el.dataset.act, pid = pidOf(el);
  const run = (p) => p && p.catch && p.catch((err) => toast(err.message || String(err), "err"));
  switch (act) {
    case "tab": closeModal(); switchTab(el.dataset.tab); break;
    case "theme": applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark"); break;
    case "profile": openProfile(); break;
    case "suggest": send(el.dataset.q); break;
    case "details": run(openDetails(pid)); break;
    case "fav": run(toggleFav(pid)); break;
    case "cmp": toggleCompare(pid); break;
    case "book": run(openBooking({ pid })); break;
    case "close-modal": closeModal(); break;
    case "open-compare": S.compare = el.dataset.ids.split(",").slice(0, 4); save("lh.compare", S.compare); S.cmpData = null; syncCompare(); switchTab("compare"); break;
    case "go-compare": switchTab("compare"); break;
    case "cmp-clear": S.compare = []; save("lh.compare", S.compare); syncCompare(); if (S.tab === "compare") renderCompare(); break;
    case "cmp-saved": S.compare = S.favCards.map((p) => p.property_id).slice(0, 4); save("lh.compare", S.compare); syncCompare(); switchTab("compare"); break;
    case "pick-saved": askAI(`Here are my saved homes: ${S.favCards.map((p) => p.property_id).join(", ")}. Which one should I book a viewing for first, and why?`); break;
    case "ask-compare": askAI(`Compare ${S.compare.join(", ")} for me. Which one is the best fit, and why?`); break;
    case "ask-about": closeModal(); askAI(`Tell me more about ${pid}. Is it good value?`); break;
    case "f-reset": { const f = $("#f-form"); if (f) { f.reset(); $$("[data-flag]", f).forEach((c) => c.classList.remove("on")); runSearch(true); } break; }
    case "f-retry": runSearch(true); break;
    case "more": S.explore.limit += 12; runSearch(false); break;
    case "history": S.showHistory = !S.showHistory; loadViewings(); break;
    case "history-retry": loadViewings(); break;
    case "resched": run(rescheduleFlow(el.dataset.aid)); break;
    case "cancel": run(cancelFlow(el.dataset.aid)); break;
    case "new-guest": run(leave(true)); break;
    case "sign-out": run(leave(false)); break;
  }
});
async function leave(guest) {
  if (guest && !(await confirmBox({ title: "Start fresh?", text: "You'll lose access to this guest's saved homes and viewings, unless you save your account first.", ok: "Start fresh", danger: true }))) return;
  await post("/api/auth/logout", {});
  location.reload();
}
async function findAppt(aid) {
  const r = await api(`/api/appointments?include_history=1`);
  return r.appointments.find((a) => String(a.appointment_id) === String(aid));
}
async function rescheduleFlow(aid) {
  const a = await findAppt(aid);
  if (!a) throw new Error("That viewing no longer exists.");
  return openBooking({ pid: a.property_id, appt: a });
}
async function cancelFlow(aid) {
  if (!(await confirmBox({ title: "Cancel this viewing?", text: "The time slot will be released for other buyers.", ok: "Cancel viewing", danger: true }))) return;
  await post(`/api/appointments/${aid}/cancel`, {});
  toast("Viewing cancelled"); await refreshAppts(); loadViewings();
}
document.addEventListener("input", (e) => {
  const t = e.target;
  if (t.matches("[data-mort]")) { S.mort[t.dataset.mort] = parseFloat(t.value); save("lh.mort", S.mort); mortOut(t.closest(".modal")); }
});
document.addEventListener("change", (e) => {
  const t = e.target;
  if (t.matches("[data-cm]")) { const v = parseFloat(t.value); if (v > 0) { S.mort[t.dataset.cm] = v; save("lh.mort", S.mort); if (S.cmpData) drawCompare(); } }
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

const inputEl = $("#input");
function submitInput() { const t = inputEl.value; inputEl.value = ""; inputEl.style.height = "auto"; send(t); }
inputEl.addEventListener("input", () => { inputEl.style.height = "auto"; inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + "px"; });
inputEl.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); submitInput(); } });
$("#send").addEventListener("click", submitInput);
window.addEventListener("hashchange", () => { const id = location.hash.slice(1); if (id && id !== S.tab) switchTab(id); });

/* ───────────────────────── boot ───────────────────────── */
(async function boot() {
  try { localStorage.removeItem("lh.session"); } catch (_) {}
  applyTheme(document.documentElement.getAttribute("data-theme") || "light");
  $("#logo").innerHTML = icon("home");
  $("#send").innerHTML = icon("send");
  renderNav(); renderUser(); renderWelcome();
  switchTab((location.hash || "#chat").slice(1));
  try { await ensureSession(); await loadHistory(); } catch (e) { toast(e.message, "err"); }
  hydrateCompare();
})();
})();
