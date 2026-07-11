/* O'tish ballari 2025 — Telegram mini webapp SPA */
"use strict";

const $ = (sel, el = document) => el.querySelector(sel);
const app = $("#app");
const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

/* ── Tema (kun/tun) ── */
function detectTheme() {
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") return saved;
  if (tg && tg.colorScheme) return tg.colorScheme;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  $("#themeBtn").textContent = t === "dark" ? "☀️" : "🌙";
  const bg = t === "dark" ? "#0d0d0d" : "#f9f9f7";
  const meta = $('meta[name="theme-color"]');
  if (meta) meta.content = bg;
  if (tg) {
    try { tg.setHeaderColor(bg); tg.setBackgroundColor(bg); } catch (e) {}
  }
}

let theme = detectTheme();

/* ── API ── */
const cache = {};
async function api(path) {
  if (cache[path]) return cache[path];
  const res = await fetch("/api" + path);
  if (!res.ok) throw new Error("API xatosi: " + res.status);
  const data = await res.json();
  cache[path] = data;
  return data;
}

/* ── Yordamchilar ── */
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function shortRegion(name) {
  return name.replace(" viloyati", "").replace("Qoraqalpog‘iston Respublikasi", "Qoraqalpog‘iston");
}

/* Ball darajalari: raqam har doim ko'rinadi — rang faqat qo'shimcha belgi */
function ballClass(b) {
  if (!b || b <= 0) return "b-none";
  if (b < 85) return "b-good";
  if (b < 115) return "b-warn";
  if (b < 150) return "b-serious";
  return "b-critical";
}

function ballBadge(b) {
  const cls = ballClass(b);
  if (cls === "b-none") return `<span class="ball b-none">—</span>`;
  return `<span class="ball ${cls}"><span class="dot"></span>${b}</span>`;
}

function skel(n = 6) {
  return Array.from({ length: n }, () => `<div class="skel"></div>`).join("");
}

function emptyState(icon, text) {
  return `<div class="empty"><div class="big">${icon}</div>${text}</div>`;
}

function setHeader(title, hasBack) {
  $("header h1").textContent = title;
  $("header").classList.toggle("has-back", !!hasBack);
  if (tg) {
    try { hasBack ? tg.BackButton.show() : tg.BackButton.hide(); } catch (e) {}
  }
}

/* ── Ogohlantirish banneri (sahifaga qarab matn/rang almashadi) ── */
const BOT_USERNAME = new URLSearchParams(location.search).get("bot") || "";

const BANNERS = {
  warn: {
    mode: "warn",
    icon: "!",
    title: "2025-yil grant natijalari hali e'lon qilinmagan",
    text: "Hozircha faqat kontrakt ballari mavjud. Grant natijalari chiqishi bilan yangilanadi.",
  },
  info: {
    mode: "info",
    icon: "🔍",
    title: "Ushbu bo'limda sun'iy intellekt (AI) yordamida bilimingizga eng mos ta'lim yo'nalishlarini topishingiz mumkin.",
    text: "",
  },
};

function setBanner(mode) {
  const b = BANNERS[mode] || BANNERS.warn;
  const inner = $(".grant-banner .inner");
  inner.classList.toggle("info", b.mode === "info");
  $(".grant-banner .icon").textContent = b.icon;
  $(".grant-banner .title").textContent = b.title;
  const textEl = $(".grant-banner .text");
  textEl.textContent = b.text;
  textEl.style.display = b.text ? "" : "none";
}

/* ── Bottom sheet (yo'nalish tafsiloti) ── */
function openSheet(d) {
  const grand = d.grand_ball && d.grand_ball > 0 ? d.grand_ball : null;
  const canShare = BOT_USERNAME && d.un_id != null && d.ty_id != null && d.lan_id != null && d.mvdir != null;
  $("#sheet").innerHTML = `
    <div class="grab"></div>
    <h2>${esc(d.nomi)}</h2>
    <div class="code">Yo'nalish kodi: ${esc(d.mvdir)}</div>
    <div class="big-ball"><span class="k">Kontrakt o'tish balli (2025)</span>
      <span class="v">${d.ball > 0 ? d.ball : "—"}</span></div>
    <div class="kv"><span class="k">🏛 OTM</span><span class="v">${esc(d.un_text)}</span></div>
    <div class="kv"><span class="k">📍 Hudud</span><span class="v">${esc(d.region)}</span></div>
    <div class="kv"><span class="k">🔰 Ta'lim shakli</span><span class="v">${esc(d.ty)}</span></div>
    <div class="kv"><span class="k">🗣 Ta'lim tili</span><span class="v">${esc(d.lan)}</span></div>
    <div class="kv"><span class="k">🏅 Grant balli</span>
      <span class="v">${grand ?? "e’lon qilinmagan"}</span></div>
    ${canShare ? `<button class="share-btn" id="sheetShareBtn">📤 Botda ulashish</button>` : ""}`;
  $("#sheetBack").classList.add("open");
  $("#sheet").classList.add("open");
  if (canShare) {
    $("#sheetShareBtn").onclick = () => {
      const payload = `card_${d.un_id}_${d.ty_id}_${d.lan_id}_${d.mvdir}`;
      const url = `https://t.me/${BOT_USERNAME}?start=${payload}`;
      if (tg) {
        try { tg.openTelegramLink(url); return; } catch (e) {}
      }
      window.open(url, "_blank");
    };
  }
}

function closeSheet() {
  $("#sheetBack").classList.remove("open");
  $("#sheet").classList.remove("open");
}

/* ── VIEW: Bosh sahifa ── */
async function viewHome() {
  setHeader("O'tish ballari", false);
  app.innerHTML = `
    <div class="search-wrap">
      <span class="icon">🔍</span>
      <input id="homeSearch" type="search" placeholder="Yo'nalish yoki OTM qidiring…" autocomplete="off">
    </div>
    <div id="searchOut"></div>
    <div id="homeBody">${skel(4)}</div>`;

  const input = $("#homeSearch");
  let timer;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => runSearch(input.value), 300);
  });

  const s = await api("/stats");

  let extremeList = [];

  function extremeRows(list) {
    extremeList = list;
    return list.map((t, i) => `
      <div class="row" data-i="${i}">
        <div class="body">
          <div class="t">${esc(t.nomi)}</div>
          <div class="s">${esc(t.un_text)}</div>
        </div>
        ${ballBadge(t.ball)}
      </div>`).join("");
  }

  function bindExtremeRows() {
    $("#extremeList").querySelectorAll(".row").forEach(el => {
      el.onclick = () => openSheet(extremeList[+el.dataset.i]);
    });
  }

  $("#homeBody").innerHTML = `
    <div class="tiles">
      <div class="tile"><div class="num">${s.universities}</div><div class="lbl">🏛 Oliy ta'lim muassasasi</div></div>
      <div class="tile"><div class="num">${s.directions}</div><div class="lbl">📚 Ta'lim yo'nalishi</div></div>
      <div class="tile"><div class="num">${s.regions}</div><div class="lbl">📍 Hudud</div></div>
      <div class="tile"><div class="num num-sm">${s.min_ball} – ${s.max_ball}</div><div class="lbl">📊 Ballar oralig'i</div></div>
    </div>
    <div class="chips" id="extremeToggle" style="margin-top:4px">
      <button class="chip${s.sort === "bottom" ? "" : " on"}" data-sort="top">📈 Eng baland ballilar</button>
      <button class="chip${s.sort === "bottom" ? " on" : ""}" data-sort="bottom">📉 Eng past ballilar</button>
    </div>
    <div class="section-title" id="extremeTitle">${s.sort === "bottom" ? "Eng past ballar" : "Eng yuqori ballar"} — ${s.year}</div>
    <div id="extremeList">${extremeRows(s.top)}</div>
    <p class="note">Ma'lumotlar mandat.uzbmb.uz saytining ${s.year}-yil kontrakt o'tish ballari asosida.
    Ball — shu yo'nalishga kontrakt asosida qabul qilingan eng past ball.</p>`;
  bindExtremeRows();

  $("#extremeToggle").querySelectorAll(".chip").forEach(c => {
    c.onclick = async () => {
      if (c.classList.contains("on")) return;
      $("#extremeToggle").querySelectorAll(".chip").forEach(x => x.classList.remove("on"));
      c.classList.add("on");
      const sort = c.dataset.sort;
      $("#extremeList").innerHTML = skel(5);
      const s2 = await api(`/stats?sort=${sort}`);
      $("#extremeTitle").textContent = `${sort === "bottom" ? "Eng past ballar" : "Eng yuqori ballar"} — ${s2.year}`;
      $("#extremeList").innerHTML = extremeRows(s2.top);
      bindExtremeRows();
    };
  });
}

async function runSearch(q) {
  const out = $("#searchOut");
  if (!out) return;
  q = q.trim();
  if (q.length < 2) { out.innerHTML = ""; return; }
  const r = await api("/search?q=" + encodeURIComponent(q));
  if (!r.universities.length && !r.directions.length) {
    out.innerHTML = emptyState("🤷", "Hech narsa topilmadi.<br>Boshqacha yozib ko'ring.");
    return;
  }
  out.innerHTML =
    (r.directions.length ? `<div class="section-title">Yo'nalishlar</div>` +
      r.directions.map(d => `
        <div class="row" onclick="location.hash='#/dir/${encodeURIComponent(d.nomi)}'">
          <div class="body"><div class="t">${esc(d.nomi)}</div>
          <div class="s">${d.unis} ta OTMda mavjud</div></div>
          ${d.min_ball ? ballBadge(d.min_ball) : ""}
          <span class="chev">›</span>
        </div>`).join("") : "") +
    (r.universities.length ? `<div class="section-title">OTMlar</div>` +
      r.universities.map(u => `
        <div class="row" onclick="location.hash='#/uni/${esc(u.un_id)}'">
          <div class="body"><div class="t">${esc(u.name)}</div>
          <div class="s">📍 ${esc(shortRegion(u.region))} · ${u.dirs} ta yo'nalish</div></div>
          <span class="chev">›</span>
        </div>`).join("") : "");
}

/* ── VIEW: Hududlar ── */
async function viewRegions() {
  setHeader("Hududlar", false);
  app.innerHTML = skel(8);
  const rows = await api("/regions");
  app.innerHTML = rows.map(r => `
    <div class="row" onclick="location.hash='#/region/${r.id}'">
      <div class="body">
        <div class="t">📍 ${esc(r.name)}</div>
        <div class="s">${r.unis} ta OTM · ${r.dirs} ta yo'nalish</div>
      </div>
      <span class="chev">›</span>
    </div>`).join("");
}

/* ── VIEW: Hudud OTMlari ── */
async function viewRegion(id) {
  setHeader("Yuklanmoqda…", true);
  app.innerHTML = skel(6);
  const r = await api(`/region/${id}/universities`);
  setHeader(shortRegion(r.region), true);
  app.innerHTML =
    `<div class="section-title">${r.universities.length} ta OTM</div>` +
    r.universities.map(u => `
      <div class="row" onclick="location.hash='#/uni/${esc(u.un_id)}'">
        <div class="body">
          <div class="t">${esc(u.name)}</div>
          <div class="s">${u.dirs} ta yo'nalish${u.min_ball ? ` · ball ${u.min_ball}–${u.max_ball}` : ""}</div>
        </div>
        <span class="chev">›</span>
      </div>`).join("");
}

/* ── VIEW: OTM sahifasi ── */
async function viewUni(unId) {
  setHeader("Yuklanmoqda…", true);
  app.innerHTML = skel(8);
  const u = await api(`/university/${unId}`);
  setHeader(u.name, true);

  let tyF = "", lanF = "";

  function render() {
    const list = u.directions.filter(d =>
      (!tyF || d.ty_id === tyF) && (!lanF || d.lan_id === lanF));
    $("#uniList").innerHTML = list.length
      ? list.map((d, i) => `
        <div class="row" data-i="${i}">
          <div class="body">
            <div class="t">${esc(d.nomi)}</div>
            <div class="s"><span class="mini">${esc(d.ty)}</span><span class="mini">${esc(d.lan)}</span></div>
          </div>
          ${ballBadge(d.ball)}
        </div>`).join("")
      : emptyState("🤷", "Bu filtrlar bo'yicha yo'nalish yo'q.");
    $("#uniCount").textContent = `${list.length} ta yo'nalish`;
    $("#uniList").querySelectorAll(".row").forEach(el => {
      el.onclick = () => {
        const d = list[+el.dataset.i];
        openSheet({ ...d, un_id: u.un_id, un_text: u.name, region: u.region });
      };
    });
  }

  const tyChips = [{ id: "", name: "Barchasi" }, ...u.types];
  const lanChips = [{ id: "", name: "Barcha tillar" }, ...u.langs];
  app.innerHTML = `
    <div class="card" style="padding:11px 14px">
      <div style="font-size:13px;color:var(--ink-2)">📍 ${esc(u.region)} · <span id="uniCount"></span></div>
    </div>
    <div class="chips" id="tyChips">${tyChips.map(t =>
      `<button class="chip${t.id === "" ? " on" : ""}" data-id="${esc(t.id)}">${esc(t.name)}</button>`).join("")}</div>
    <div class="chips" id="lanChips">${lanChips.map(l =>
      `<button class="chip${l.id === "" ? " on" : ""}" data-id="${esc(l.id)}">${esc(l.name)}</button>`).join("")}</div>
    <div id="uniList"></div>`;

  function bindChips(wrapId, setter) {
    $(wrapId).querySelectorAll(".chip").forEach(c => {
      c.onclick = () => {
        $(wrapId).querySelectorAll(".chip").forEach(x => x.classList.remove("on"));
        c.classList.add("on");
        setter(c.dataset.id);
        render();
      };
    });
  }
  bindChips("#tyChips", v => (tyF = v));
  bindChips("#lanChips", v => (lanF = v));
  render();
}

/* ── VIEW: Yo'nalishlar ── */
async function viewDirs() {
  setHeader("Yo'nalishlar", false);
  app.innerHTML = `
    <div class="search-wrap">
      <span class="icon">🔍</span>
      <input id="dirSearch" type="search" placeholder="Yo'nalish nomini yozing…" autocomplete="off">
    </div>
    <div id="dirList">${skel(8)}</div>`;

  const all = await api("/directions");

  function render(q) {
    const qn = (q || "").toLowerCase().replace(/[ʼʻ'’‘`´ʹ]/g, "");
    const list = qn
      ? all.filter(d => d.nomi.toLowerCase().replace(/[ʼʻ'’‘`´ʹ]/g, "").includes(qn))
      : all;
    $("#dirList").innerHTML = list.length
      ? `<div class="section-title">${list.length} ta yo'nalish</div>` +
        list.map(d => `
          <div class="row" onclick="location.hash='#/dir/${encodeURIComponent(d.nomi)}'">
            <div class="body">
              <div class="t">${esc(d.nomi)}</div>
              <div class="s">${d.unis} ta OTMda mavjud${d.min_ball ? ` · eng past ball ${d.min_ball}` : ""}</div>
            </div>
            <span class="chev">›</span>
          </div>`).join("")
      : emptyState("🤷", "Yo'nalish topilmadi.<br>Boshqacha yozib ko'ring.");
  }

  let timer;
  $("#dirSearch").addEventListener("input", e => {
    clearTimeout(timer);
    timer = setTimeout(() => render(e.target.value), 200);
  });
  render("");
}

/* ── VIEW: Yo'nalish tafsiloti ── */
async function viewDir(nomi) {
  setHeader(nomi, true);
  app.innerHTML = skel(6);
  const r = await api("/direction?nomi=" + encodeURIComponent(nomi));
  app.innerHTML = `
    <div class="card" style="padding:11px 14px">
      <div style="font-size:13px;color:var(--ink-2)">
        ${r.offers.length} ta taklif · eng pastdan yuqoriga saralangan</div>
    </div>
    <div id="dirOffers">
    ${r.offers.map((o, i) => `
      <div class="row" data-i="${i}">
        <div class="body">
          <div class="t">${esc(o.un_text)}</div>
          <div class="s">📍 ${esc(shortRegion(o.region))}<br>
            <span class="mini">${esc(o.ty)}</span><span class="mini">${esc(o.lan)}</span></div>
        </div>
        ${ballBadge(o.ball)}
      </div>`).join("")}
    </div>`;
  $("#dirOffers").querySelectorAll(".row").forEach(el => {
    el.onclick = () => openSheet({ ...r.offers[+el.dataset.i], nomi: r.nomi });
  });
}

/* ── VIEW: Ballim ── */
async function viewBall() {
  setHeader("Ballim yetadimi?", false);
  const regions = await api("/regions");
  app.innerHTML = `
    <div class="card">
      <div style="font-size:14px;font-weight:700;margin-bottom:10px">🎯 Ballingizni kiriting</div>
      <div class="score-input">
        <input id="ballInput" type="number" inputmode="decimal" min="0" max="200" step="0.1" placeholder="masalan: 120">
        <button id="ballGo">Ko'rish</button>
      </div>
      <div class="chips" id="ballTy" style="margin-top:12px;padding-bottom:0">
        <button class="chip on" data-id="">Barchasi</button>
        <button class="chip" data-id="1">Kunduzgi</button>
        <button class="chip" data-id="4">Kechki</button>
        <button class="chip" data-id="6">Masofaviy</button>
      </div>
      <select class="region-sel" id="ballRegion">
        <option value="">Barcha hududlar</option>
        ${regions.map(r => `<option value="${r.id}">${esc(r.name)}</option>`).join("")}
      </select>
    </div>
    <div id="ballOut">
      <p class="note">Ballingizni kiriting — 2025-yil kontrakt o'tish ballari asosida
      qaysi yo'nalishlarga hujjat topshira olishingizni ko'rasiz.</p>
    </div>`;

  let tyF = "";
  $("#ballTy").querySelectorAll(".chip").forEach(c => {
    c.onclick = () => {
      $("#ballTy").querySelectorAll(".chip").forEach(x => x.classList.remove("on"));
      c.classList.add("on");
      tyF = c.dataset.id;
      if ($("#ballInput").value) run();
    };
  });
  $("#ballRegion").onchange = () => { if ($("#ballInput").value) run(); };
  $("#ballGo").onclick = run;
  $("#ballInput").addEventListener("keydown", e => { if (e.key === "Enter") run(); });

  async function run() {
    const b = parseFloat($("#ballInput").value);
    if (isNaN(b) || b <= 0) {
      $("#ballOut").innerHTML = emptyState("✍️", "Avval balingizni kiriting.");
      return;
    }
    $("#ballOut").innerHTML = skel(5);
    let url = `/by-score?ball=${b}`;
    const reg = $("#ballRegion").value;
    if (reg) url += `&region_id=${reg}`;
    if (tyF) url += `&ty_id=${tyF}`;
    const r = await api(url);
    if (!r.items.length) {
      $("#ballOut").innerHTML = emptyState("😔",
        `${b} ball bilan mos yo'nalish topilmadi.<br>Filtrlarni kengaytirib ko'ring.`);
      return;
    }
    $("#ballOut").innerHTML = `
      <div class="result-count">✅ <b>${r.total}</b> ta yo'nalishga ballingiz yetadi
        ${r.total > r.items.length ? ` (eng yaqin ${r.items.length} tasi ko'rsatildi)` : ""}</div>
      <div id="ballList">
      ${r.items.map((o, i) => `
        <div class="row" data-i="${i}">
          <div class="body">
            <div class="t">${esc(o.nomi)}</div>
            <div class="s">${esc(o.un_text)}<br>
              <span class="mini">📍 ${esc(shortRegion(o.region))}</span><span class="mini">${esc(o.ty)}</span><span class="mini">${esc(o.lan)}</span></div>
          </div>
          ${ballBadge(o.ball)}
        </div>`).join("")}
      </div>`;
    $("#ballList").querySelectorAll(".row").forEach(el => {
      el.onclick = () => openSheet(r.items[+el.dataset.i]);
    });
  }
}

/* ── Router ── */
const routes = [
  { re: /^#?\/?$/, view: () => viewHome(), tab: "home" },
  { re: /^#\/regions$/, view: () => viewRegions(), tab: "regions" },
  { re: /^#\/region\/(\d+)$/, view: m => viewRegion(+m[1]), tab: "regions" },
  { re: /^#\/uni\/([^/]+)$/, view: m => viewUni(decodeURIComponent(m[1])), tab: "regions" },
  { re: /^#\/dirs$/, view: () => viewDirs(), tab: "dirs" },
  { re: /^#\/dir\/(.+)$/, view: m => viewDir(decodeURIComponent(m[1])), tab: "dirs" },
  { re: /^#\/ball$/, view: () => viewBall(), tab: "ball", banner: "info" },
];

async function route() {
  closeSheet();
  const h = location.hash || "#/";
  const r = routes.find(x => x.re.test(h)) || routes[0];
  document.querySelectorAll("nav a").forEach(a =>
    a.classList.toggle("on", a.dataset.tab === r.tab));
  setBanner(r.banner || "warn");
  window.scrollTo(0, 0);
  try {
    await r.view(h.match(r.re));
  } catch (e) {
    app.innerHTML = emptyState("⚠️", "Ma'lumot yuklashda xatolik.<br>Internetni tekshirib qayta urining.");
    console.error(e);
  }
}

/* ── Init ── */
applyTheme(theme);
$("#themeBtn").onclick = () => {
  theme = theme === "dark" ? "light" : "dark";
  localStorage.setItem("theme", theme);
  applyTheme(theme);
};
$("#backBtn").onclick = () => history.back();
$("#sheetBack").onclick = closeSheet;
if (tg) {
  try {
    tg.ready();
    tg.expand();
    tg.BackButton.onClick(() => history.back());
  } catch (e) {}
}
window.addEventListener("hashchange", route);
route();
