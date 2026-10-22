// Card OPCOM PZU — date: sensor.opcom_pret_acum, trimis de fluxul Node-RED „OPCOM → Home Assistant”.
// Atribute: azi_15/30/60, maine_15/30/60 = prețuri (lei/MWh) pe 15 min și medii pe 30/60 min, în ordinea zilei locale (92/96/100 sloturi de 15 min).
// azi_start_utc / maine_start_utc = începutul fiecărui slot de 15 min (UTC); cu ele etichetele și intervalul curent sunt corecte și în zilele de 23/25 h.
// Fără aceste atribute (versiune veche a fluxului) cardul calculează ca înainte, din ceas (corect doar în zile de 24 h).
const a = entity.attributes || {};
const S = window.__opcomCard || (window.__opcomCard = { pas: 60, zi: "azi" });   // alegerea rămâne după actualizări
const d = new Date(), MIN = d.getHours() * 60 + d.getMinutes();
const kwh = v => (v / 1000).toFixed(3);
const lt = ms => new Date(ms).toLocaleTimeString("ro-RO", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "Europe/Bucharest" });
const st = zi => a[zi + "_start_utc"] || [];
// eticheta de început al intervalului i (pas minute) din ziua zi; sfârșitul = începutul lui i+1
const et = (i, pas, zi) => { const s = st(zi || "azi"), k = i * pas / 15;
  if (s[k]) return lt(Date.parse(s[k]));
  if (s.length && k >= s.length) return lt(Date.parse(s[s.length - 1]) + (k - s.length + 1) * 900000);
  const m = i * pas; return String(Math.floor(m / 60) % 24).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"); };
// indexul intervalului curent (pas minute) în ziua de azi
const curIdx = pas => { const s = st("azi"), n = Date.now(); if (!s.length) return Math.floor(MIN / pas);
  const k = Math.floor((n - Date.parse(s[0])) / 900000); return Math.floor(k * 15 / pas); };
function nivel(v, arr) {
  const s = arr.slice().sort((x, y) => x - y), t1 = s[Math.floor(s.length / 3)], t2 = s[Math.floor(2 * s.length / 3)];
  return v <= t1 ? "ief" : v <= t2 ? "med" : "scp";
}
function vedere(zi, pas) {
  const arr = a[zi + "_" + pas] || [];
  if (!arr.length) return `<div class="gol">${zi === "maine" ? "Prețurile pentru mâine apar după 14:30" : "Fără prețuri pentru azi"}</div>`;
  const mx = Math.max(...arr), mn = Math.min(...arr), cur = zi === "azi" ? curIdx(pas) : -1;
  const bare = arr.map((v, i) => `<div class="b ${nivel(v, arr)}${i === cur ? " cur" : ""}${i < cur ? " trec" : ""}" style="height:${Math.round(18 + (mx > mn ? (v - mn) / (mx - mn) : 0.5) * 92)}px"></div>`).join("");
  const ax = [0, 6, 12, 18, 24].map(o => `<span style="left:${o / 24 * 100}%">${String(o).padStart(2, "0")}</span>`).join("");
  const ramase = arr.map((v, i) => [v, i]).filter(x => x[1] >= Math.max(cur, 0));
  const ief = ramase.slice().sort((x, y) => x[0] - y[0]).slice(0, 3).sort((x, y) => x[1] - y[1])
    .map(([v, i]) => `<i class="ch">${et(i, pas, zi)}–${et(i + 1, pas, zi)} · ${kwh(v)}</i>`).join("");
  const medie = arr.reduce((x, y) => x + y, 0) / arr.length;
  const sh = zi === "azi" && arr[cur] != null
    ? `acum ${et(cur, pas, zi)}–${et(cur + 1, pas, zi)}: <em class="${nivel(arr[cur], arr)}">${kwh(arr[cur])} lei/kWh</em>`
    : `min <em class="ief">${kwh(mn)}</em> · medie ${kwh(medie)} · max <em class="scp">${kwh(mx)}</em>`;
  const lista = (zi === "azi" ? ramase.slice(0, pas === 60 ? 8 : 12) : [])
    .map(([v, i]) => `<div class="li${i === cur ? " cur" : ""}"><span>${et(i, pas, zi)}</span><b class="${nivel(v, arr)}">${kwh(v)}</b></div>`).join("");
  return `<div class="sh"><span>${zi === "azi" ? "AZI" : "MÂINE"} · LA ${pas} MINUTE</span><b>${sh}</b></div>
    <div class="ch2">${bare}</div><div class="ax">${ax}</div>
    <div class="chs"><small>${zi === "azi" ? "cele mai ieftine rămase:" : "cele mai ieftine:"}</small>${ief}</div>
    ${lista ? `<div class="ls">${lista}</div>` : ""}`;
}
// numărul mare = media orei curente, ca pe opcom.ro la „60min”; prețul pe 15 min apare dedesubt
const p15 = Number(entity.state), az = a.azi || {}, a60 = a.azi_60 || [];
const c60 = curIdx(60), ora = a60[c60], pa = ora != null ? Number(ora) : p15;
const nv = a60.length && !isNaN(pa) ? nivel(pa, a60) : "med";
// min/medie/max pe ore (ca tabelul OPCOM „60min”); dacă lipsesc, cele pe 15 min
const mm = a60.length ? { min: Math.min(...a60), max: Math.max(...a60), medie: a60.reduce((x, y) => x + y, 0) / a60.length } : az;
const ck = c => c ? "checked" : "";
// button-card blochează clicul implicit pe <label>, așa că bifăm direct și ținem minte alegerea
const tab = (id, cls, cheie, val, text) => `<label class="${cls}" onclick="event.stopPropagation();this.getRootNode().getElementById('${id}').checked=true;window.__opcomCard.${cheie}=${val}">${text}</label>`;
const v = (zi, pas) => `<div class="v v${pas}${zi}">${vedere(zi, pas)}</div>`;
return `<div class="op">
  <div class="hd"><ha-icon icon="mdi:flash"></ha-icon><span class="ti">PREȚ ENERGIE OPCOM</span><span class="bd">PZU</span></div>
  <div class="top"><div class="big ${nv}">${isNaN(pa) ? "–" : kwh(pa)}<small> lei/kWh</small><div class="sub">${isNaN(pa) ? "–" : pa.toFixed(2)} lei/MWh · ora ${et(c60, 60)}–${et(c60 + 1, 60)}</div><div class="sub">${isNaN(p15) ? "" : "acum pe 15 min: " + kwh(p15) + " lei/kWh"}</div></div>
    <div class="mm"><div><span>MIN</span><b class="ief">${mm.min != null ? kwh(mm.min) : "–"}</b></div><div><span>MEDIE</span><b>${mm.medie != null ? kwh(mm.medie) : "–"}</b></div><div><span>MAX</span><b class="scp">${mm.max != null ? kwh(mm.max) : "–"}</b></div></div></div>
  <input type="radio" name="opp" id="o15" ${ck(S.pas === 15)}><input type="radio" name="opp" id="o30" ${ck(S.pas === 30)}><input type="radio" name="opp" id="o60" ${ck(S.pas === 60)}>
  <input type="radio" name="opz" id="oaz" ${ck(S.zi === "azi")}><input type="radio" name="opz" id="oma" ${ck(S.zi === "maine")}>
  <div class="tabs">${tab("o15", "t15", "pas", 15, "15 MIN")}${tab("o30", "t30", "pas", 30, "30 MIN")}${tab("o60", "t60", "pas", 60, "60 MIN")}${tab("oaz", "taz", "zi", "'azi'", "AZI")}${tab("oma", "tma", "zi", "'maine'", "MÂINE" + (a.maine_disponibil ? "" : " ⏳"))}</div>
  <div class="vs">${v("azi", 15)}${v("maine", 15)}${v("azi", 30)}${v("azi", 60)}${v("maine", 30)}${v("maine", 60)}</div>
  <div class="ft">OPCOM PZU prin Node-RED · verde ieftin · turcoaz mediu · portocaliu scump</div>
</div>`;
