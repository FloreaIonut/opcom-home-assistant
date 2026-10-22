// Teste offline pentru corecția de fus orar OPCOM. Rulare: node tests/run-tests.js
// Rulează chiar codul din nodurile Node-RED (flows/*.json), într-un sandbox cu node/flow/global/Date simulate. Nu accesează rețeaua.
const fs = require("fs"), path = require("path"), vm = require("vm"), assert = require("assert");
const R = p => path.join(__dirname, "..", p);
const standalone = JSON.parse(fs.readFileSync(R("flows/opcom-home-assistant.json"), "utf8"));
const nod = (flux, nume) => flux.find(n => n.name === nume && n.type === "function").func;
const nodId = (flux, id) => flux.find(n => n.id === id).func;
const SA = { cerere: nod(standalone, "Cerere OPCOM"), salveaza: nod(standalone, "Salvează prețuri"),
    publica: nod(standalone, "Publică în HA").replace("PUNE_AICI_TOKEN_HA", "TEST") };

function ruleaza(func, { msg = {}, flowS = {}, globalS = {}, now }) {
    const t0 = now;
    class FD extends Date { constructor(...a) { if (a.length === 0) super(t0); else super(...a); } static now() { return t0; } }
    const mk = S => ({ get: k => S[k], set: (k, v) => { S[k] = v; } });
    const stari = [], ctxS = {};
    const sandbox = { node: { status: s => stari.push(s), warn() {}, error() {} }, flow: mk(flowS), global: mk(globalS), context: mk(ctxS),
        env: { get: () => undefined }, Date: FD, console };
    vm.createContext(sandbox);
    const f = vm.runInContext("(async function(msg){\n" + func + "\n})", sandbox);
    return f(msg).then(ret => ({ ret: ret === undefined ? ret : JSON.parse(JSON.stringify(ret)), stari }));
}
const utc = (s) => Date.parse(s);
const fmt = (n) => n.toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
let ok = 0, bad = 0;
const T = (nume, fn) => Promise.resolve().then(fn).then(() => { ok++; console.log("  OK   " + nume); }, e => { bad++; console.log("  FAIL " + nume + "\n       " + e.message.split("\n")[0]); });

function csv15(fisier) {   // rânduri „Romania” din CSV-ul real, în formatul text pe care îl primește nodul
    return fs.readFileSync(path.join(__dirname, "date", fisier), "utf8");
}
function csv60(fisier) {
    const v = {}; fs.readFileSync(path.join(__dirname, "date", fisier), "utf8").split("\n").forEach(l => { const m = l.match(/^"(\d+)","([\d.]+)","PT60M"/); if (m) v[+m[1]] = parseFloat(m[2]); });
    return v;
}
// CSV sintetic pentru o zi OPCOM cu n sloturi; prețul = funcție de începutul slotului în UTC (identificabil)
const pretSintetic = tsMs => Math.round(tsMs / 900000) % 100000 + 0.5;
function csvSintetic(cheie, n, ctx) {
    const start = ctx.ocStartCET(cheie); let t = "\"x\"\n";
    for (let i = 1; i <= n; i++) t += `"Romania","${i}","${pretSintetic(start + (i - 1) * 900000)}","1","1","1","PT15M"\n`;
    return t;
}
// context cu funcțiile din core (pentru referințe independente în teste)
const coreSrc = fs.readFileSync(R("src/opcom-core.js"), "utf8");
const C = {}; vm.createContext(C); vm.runInContext(coreSrc + "\nthis.ocStartCET=ocStartCET;this.ocStartRO=ocStartRO;this.ocCheieRO=ocCheieRO;this.ocZiPlus=ocZiPlus;this.OC_Q=OC_Q;", C);

async function salveazaCsv(func, zi, text, flowS, globalS) {
    return ruleaza(func, { msg: { payload: text, statusCode: 200, opcomZi: zi }, flowS, globalS, now: utc("2026-10-22T10:00:00Z") });
}
async function publicaAcum(now, flowS) {   // rulează nodul „Publică în HA” (standalone) și întoarce payload-ul trimis
    const r = await ruleaza(SA.publica, { msg: {}, flowS, now });
    return { atr: r.ret.payload.attributes, stare: r.ret.payload.state, stari: r.stari };
}

(async () => {
    console.log("== 1. Date reale OPCOM (22.10.2026, ieri 21.10) — nodul standalone");
    const flowS = {};
    await salveazaCsv(SA.salveaza, "2026-10-21", csv15("21-10-2026_15.csv"), flowS);
    const sv = await salveazaCsv(SA.salveaza, "2026-10-22", csv15("22-10-2026_15.csv"), flowS);
    const p15 = flowS.opcom_preturi["2026-10-22"], p15ieri = flowS.opcom_preturi["2026-10-21"];
    const c60 = csv60("22-10-2026_60.csv"), c60ieri = csv60("21-10-2026_60.csv");
    console.log("  salvat:", sv.stari[0].text, "| ts_utc interval 1 =", p15[0].ts_utc, "| ora_cet =", p15[0].ora_cet);
    const now2130 = utc("2026-10-22T18:30:00Z");   // 21:30 EEST
    const r = await publicaAcum(now2130, flowS);
    const pret83 = p15.find(x => x.interval === 83).pret_lei_mwh;
    const pret87 = p15.find(x => x.interval === 87).pret_lei_mwh;
    console.log(`  21:30 EEST: state=${r.stare}  interval(local)=${r.atr.interval}  interval_opcom=${r.atr.interval_opcom}  [înainte de corecție: interval 87 => ${pret87}]`);
    console.log(`  azi_60[21] (21:00-22:00 local) = ${r.atr.azi_60[21]}  | CSV 60 min interval 21 = ${c60[21]}`);
    const iMin = r.atr.azi_60.indexOf(Math.min(...r.atr.azi_60));
    console.log(`  minimul zilei (60 min): ora locală ${String(iMin).padStart(2, "0")}:00-${String(iMin + 1).padStart(2, "0")}:00 = ${r.atr.azi_60[iMin]} | azi_60[0] (00:00-01:00) = ${r.atr.azi_60[0]} (CSV 21.10 interval 24 = ${c60ieri[24]})`);
    console.log(`  azi_start_utc[0]=${r.atr.azi_start_utc[0]}  [95]=${r.atr.azi_start_utc[95]}  maine_15=${r.atr.maine_15.length}  maine_disponibil=${r.atr.maine_disponibil}`);
    const json = JSON.stringify(r.atr); console.log("  mărime atribute JSON:", json.length, "octeți (limita HA recorder: 16384)");
    await T("21:30 local: state = preț 15 min al intervalului OPCOM 83", () => { assert.strictEqual(+r.stare, pret83); assert.strictEqual(r.atr.interval_opcom, 83); assert.strictEqual(r.atr.interval, 87); });
    await T("21:00-22:00 local în azi_60 = 1532.03 (interval 60-min 21)", () => assert.strictEqual(r.atr.azi_60[21], 1532.03));
    await T("minimul zilei în 05:00-06:00 local (968.94)", () => { assert.strictEqual(iMin, 5); assert.strictEqual(r.atr.azi_60[5], 968.94); });
    await T("azi_60[h] = CSV 60 min interval h pentru h=1..23 (±0.01)", () => { for (let h = 1; h <= 23; h++) assert(Math.abs(r.atr.azi_60[h] - c60[h]) <= 0.011, "h=" + h + " " + r.atr.azi_60[h] + " vs " + c60[h]); });
    await T("00:00-01:00 local = intervalul 24 (sloturile 93-96) din 21.10", () => { assert(Math.abs(r.atr.azi_60[0] - c60ieri[24]) <= 0.011); assert.strictEqual(r.atr.azi_15[0], p15ieri.find(x => x.interval === 93).pret_lei_mwh); });
    await T("valorile cheie din raportul anterior (1=1019.27 5=968.94 9=1718.78 20=1550.58 21=1532.03 22=1527.90 23=1482.59 24=1299.40)", () => {
        const e = { 1: 1019.27, 5: 968.94, 9: 1718.78, 20: 1550.58, 21: 1532.03, 22: 1527.90, 23: 1482.59 };
        Object.keys(e).forEach(k => assert.strictEqual(c60[k], e[k], "CSV60 " + k)); assert.strictEqual(c60ieri[24] > 0, true); assert.strictEqual(c60[24], 1299.40); });
    await T("liste: 96/48/24, maine gol, azi_start_utc 96 contigue, formatul atributelor păstrat", () => {
        assert.deepStrictEqual([r.atr.azi_15.length, r.atr.azi_30.length, r.atr.azi_60.length, r.atr.azi_start_utc.length], [96, 48, 24, 96]);
        assert.deepStrictEqual([r.atr.maine_15.length, r.atr.maine_60.length, r.atr.maine_start_utc.length], [0, 0, 0]);
        assert.strictEqual(r.atr.azi_start_utc[0], "2026-10-21T21:00Z"); assert.strictEqual(r.atr.data_azi, "2026-10-22"); assert.strictEqual(r.atr.data_maine, "2026-10-23");
        ["azi", "maine", "maine_disponibil", "data_azi", "data_maine", "azi_15", "azi_30", "azi_60", "maine_15", "maine_30", "maine_60", "interval", "azi_start_utc", "maine_start_utc"].forEach(k => assert(k in r.atr, k));
        assert(Object.keys(r.atr.azi).join() === "min,max,medie"); });
    await T("sub 16384 octeți de atribute (cu mâine complet)", () => { assert(json.length < 16384); });
    // mâine
    const flowM = JSON.parse(JSON.stringify(flowS));
    const sinM = csvSintetic("2026-10-23", 96, C);
    await salveazaCsv(SA.salveaza, "2026-10-23", sinM, flowM);
    const rm = await publicaAcum(utc("2026-10-22T12:00:00Z"), flowM);
    json2 = JSON.stringify(rm.atr); console.log("  cu mâine (23.10 sintetic): maine_15=" + rm.atr.maine_15.length + " maine_60=" + rm.atr.maine_60.length + ", atribute " + json2.length + " octeți");
    await T("mâine (după publicare): 96/48/24, începe cu sloturile 93-96 de azi", () => {
        assert.deepStrictEqual([rm.atr.maine_15.length, rm.atr.maine_30.length, rm.atr.maine_60.length], [96, 48, 24]); assert.strictEqual(rm.atr.maine_disponibil, true);
        assert.strictEqual(rm.atr.maine_15[0], p15.find(x => x.interval === 93).pret_lei_mwh); assert.strictEqual(rm.atr.maine_start_utc[0], "2026-10-22T21:00Z"); assert(json2.length < 16384); });
    await T("compatibilitate: date vechi fără ts_utc (format dinainte de corecție) dau același rezultat", () => {
        const veche = { "2026-10-21": p15ieri.map(x => ({ interval: x.interval, ora: x.ora_cet, pret_lei_mwh: x.pret_lei_mwh })), "2026-10-22": p15.map(x => ({ interval: x.interval, ora: x.ora_cet, pret_lei_mwh: x.pret_lei_mwh })) };
        return publicaAcum(now2130, { opcom_preturi: veche }).then(v => { assert.deepStrictEqual(v.atr.azi_60, r.atr.azi_60); assert.strictEqual(v.stare, r.stare); }); });
    await T("fără ziua de ieri: lista rămâne aliniată (primele 4 sloturi null), nu se mută", async () => {
        const f = { "2026-10-22": flowS.opcom_preturi["2026-10-22"] }; const v = await publicaAcum(now2130, { opcom_preturi: f });
        assert.strictEqual(v.atr.azi_15.length, 96); assert.strictEqual(v.atr.azi_15[0], null); assert.strictEqual(v.atr.azi_60[0], null); assert.strictEqual(v.atr.azi_60[21], 1532.03); assert.strictEqual(+v.stare, pret83); });

    console.log("\n== 2. Cererea zilelor (ieri/azi/mâine) și păstrarea a 5 zile");
    await T("standalone 22.10 08:00: cere 21.10 și 22.10 (nu mâine); 14:00: doar lipsa (23.10)", async () => {
        const a = await ruleaza(SA.cerere, { flowS: {}, now: utc("2026-10-22T05:00:00Z") }); assert.deepStrictEqual(a.ret[0].map(x => x.opcomZi), ["2026-10-21", "2026-10-22"]);
        assert(a.ret[0][0].url.endsWith("/21/10/2026/ro?resolution=15"));
        const b = await ruleaza(SA.cerere, { flowS: JSON.parse(JSON.stringify(flowS)), now: utc("2026-10-22T11:00:00Z") }); assert.deepStrictEqual(b.ret[0].map(x => x.opcomZi), ["2026-10-23"]); });
    await T("00:30 local (21:30 UTC ieri): ziua locală = azi, cere ieri OPCOM = ziua dinainte", async () => {
        const a = await ruleaza(SA.cerere, { flowS: {}, now: utc("2026-10-21T21:30:00Z") }); assert.deepStrictEqual(a.ret[0].map(x => x.opcomZi), ["2026-10-21", "2026-10-22"]); });

    console.log("\n== 3. Zile speciale (sintetic: prețul fiecărui slot = identificator al începutului în UTC)");
    const nextKey = k => C.ocZiPlus(k, 1);
    function umple(zile, deLa) {   // salvează zilele OPCOM (cu numărul real de sloturi)
        const f = {}; return (async () => { for (const z of zile) { const n = (C.ocStartCET(nextKey(z)) - C.ocStartCET(z)) / 900000;
            await salveazaCsv(SA.salveaza, z, csvSintetic(z, n, C), f); } return f; })(); }
    const fOct = await umple(["2026-10-23", "2026-10-24", "2026-10-25", "2026-10-26"]);
    // salvarea păstrează ultimele 5 zile; 4 zile -> toate rămân
    console.log("  sloturi salvate: " + Object.keys(fOct.opcom_preturi).map(k => k + "=" + fOct.opcom_preturi[k].length).join(", "));
    const rOct = await publicaAcum(utc("2026-10-25T10:00:00Z"), fOct);   // 25.10 13:00 EET
    const rOct26 = await publicaAcum(utc("2026-10-26T10:00:00Z"), fOct);
    function contigue(iso) { for (let i = 1; i < iso.length; i++) assert.strictEqual(Date.parse(iso[i]) - Date.parse(iso[i - 1]), 900000, "gol la " + i); }
    function preturiCorecte(atr) { atr.azi_start_utc.forEach((s, i) => assert.strictEqual(atr.azi_15[i], pretSintetic(Date.parse(s)), "slot " + s)); }
    await T("25.10.2026: azi = 100 sloturi (25 h), azi_60 = 25, contigue, de la 21:00Z (24.10) la 21:45Z (25.10)", () => {
        assert.deepStrictEqual([rOct.atr.azi_15.length, rOct.atr.azi_30.length, rOct.atr.azi_60.length, rOct.atr.azi_start_utc.length], [100, 50, 25, 100]);
        assert.strictEqual(rOct.atr.azi_start_utc[0], "2026-10-24T21:00Z"); assert.strictEqual(rOct.atr.azi_start_utc[99], "2026-10-25T21:45Z"); contigue(rOct.atr.azi_start_utc); preturiCorecte(rOct.atr); assert(!rOct.atr.azi_15.includes(null)); });
    await T("25.10: primele 4 sloturi = OPCOM 24.10 sloturile 93-96; ultimele 4 = OPCOM 25.10 sloturile 93-96; 97-100 trec pe 26.10", () => {
        const p24 = fOct.opcom_preturi["2026-10-24"], p25 = fOct.opcom_preturi["2026-10-25"];
        assert.deepStrictEqual(rOct.atr.azi_15.slice(0, 4), [93, 94, 95, 96].map(i => p24[i - 1].pret_lei_mwh));
        assert.deepStrictEqual(rOct.atr.azi_15.slice(96, 100), [93, 94, 95, 96].map(i => p25[i - 1].pret_lei_mwh));
        assert.strictEqual(p25.length, 100); assert.deepStrictEqual(rOct26.atr.azi_15.slice(0, 4), [97, 98, 99, 100].map(i => p25[i - 1].pret_lei_mwh));
        assert.strictEqual(rOct26.atr.azi_15.length, 96); preturiCorecte(rOct26.atr); assert.strictEqual(rOct26.atr.azi_start_utc[0], "2026-10-25T22:00Z"); });
    // intervalAcum în jurul 03:xx 25.10
    const pct = {};
    for (const [eticheta, t] of [["03:30 EEST", "2026-10-25T00:30:00Z"], ["03:30 EET", "2026-10-25T01:30:00Z"], ["03:59 EEST", "2026-10-25T00:59:00Z"], ["03:00 EET (prima ora după schimbare)", "2026-10-25T01:00:00Z"], ["02:59 EEST", "2026-10-24T23:59:00Z"], ["04:00 EET", "2026-10-25T02:00:00Z"]]) {
        const x = await publicaAcum(utc(t), fOct); pct[eticheta] = x; console.log(`  ${eticheta} (${t}): interval local=${x.atr.interval}, interval_opcom=${x.atr.interval_opcom}, preț=${x.stare}`);
    }
    await T("25.10: 03:30 EEST și 03:30 EET dau intervale diferite (15 vs 19), preț = al slotului cu ts_utc corect", () => {
        assert.strictEqual(pct["03:30 EEST"].atr.interval, 15); assert.strictEqual(pct["03:30 EET"].atr.interval, 19); assert.strictEqual(pct["03:30 EEST"].atr.interval_opcom, 11); assert.strictEqual(pct["03:30 EET"].atr.interval_opcom, 15);
        assert.strictEqual(+pct["03:30 EEST"].stare, pretSintetic(utc("2026-10-25T00:30:00Z"))); assert.strictEqual(+pct["03:30 EET"].stare, pretSintetic(utc("2026-10-25T01:30:00Z")));
        assert.strictEqual(pct["03:59 EEST"].atr.interval, 16); assert.strictEqual(pct["03:00 EET (prima ora după schimbare)"].atr.interval, 17); assert.strictEqual(pct["02:59 EEST"].atr.interval, 12); assert.strictEqual(pct["04:00 EET"].atr.interval, 21); });
    await T("25.10: ultimul slot al zilei (23:45 EET = 21:45Z) = interval 100; 00:00 EET 26.10 = interval 1 (OPCOM 97)", async () => {
        const a = await publicaAcum(utc("2026-10-25T21:45:00Z"), fOct), b = await publicaAcum(utc("2026-10-25T22:00:00Z"), fOct);
        assert.strictEqual(a.atr.interval, 100); assert.strictEqual(a.atr.data_azi, "2026-10-25"); assert.strictEqual(a.atr.interval_opcom, 96); assert.strictEqual(+a.stare, pretSintetic(utc("2026-10-25T21:45:00Z")));
        assert.strictEqual(b.atr.interval, 1); assert.strictEqual(b.atr.data_azi, "2026-10-26"); assert.strictEqual(b.atr.interval_opcom, 97); });
    await T("24.10 (zi de 24 h înainte): 00:00 EEST = OPCOM 23.10 interval 93; ultima oră a zilei = OPCOM 89-92; atributele maine pe 25.10 = 100 sloturi", async () => {
        const a = await publicaAcum(utc("2026-10-23T21:00:00Z"), fOct), b = await publicaAcum(utc("2026-10-24T20:45:00Z"), fOct), c = await publicaAcum(utc("2026-10-24T08:00:00Z"), fOct);
        assert.strictEqual(a.atr.interval, 1); assert.strictEqual(a.atr.interval_opcom, 93); assert.strictEqual(a.atr.data_azi, "2026-10-24"); assert.strictEqual(b.atr.interval, 96); assert.strictEqual(b.atr.interval_opcom, 92);
        assert.strictEqual(c.atr.maine_15.length, 100); assert.strictEqual(c.atr.maine_60.length, 25); assert.strictEqual(c.atr.maine_start_utc.length, 100); contigue(c.atr.maine_start_utc); });
    // martie 2027
    const fMar = await umple(["2027-03-26", "2027-03-27", "2027-03-28", "2027-03-29", "2027-03-30"]);
    console.log("  sloturi salvate: " + Object.keys(fMar.opcom_preturi).map(k => k + "=" + fMar.opcom_preturi[k].length).join(", "));
    const rM28 = await publicaAcum(utc("2027-03-28T10:00:00Z"), fMar), rM29 = await publicaAcum(utc("2027-03-29T10:00:00Z"), fMar);
    await T("28.03.2027 (ultima duminică din martie; zi OPCOM cu 92 sloturi): azi = 92 sloturi (23 h), azi_60 = 23, contigue", () => {
        assert.strictEqual(fMar.opcom_preturi["2027-03-28"].length, 92);
        assert.deepStrictEqual([rM28.atr.azi_15.length, rM28.atr.azi_30.length, rM28.atr.azi_60.length], [92, 46, 23]); assert.strictEqual(rM28.atr.azi_start_utc[0], "2027-03-27T22:00Z"); assert.strictEqual(rM28.atr.azi_start_utc[91], "2027-03-28T20:45Z");
        contigue(rM28.atr.azi_start_utc); preturiCorecte(rM28.atr); assert(!rM28.atr.azi_15.includes(null)); });
    await T("29.03.2027 (zi locală normală după schimbare): 96 sloturi = OPCOM 28.03 sloturile 89-92 + 29.03 sloturile 1-92", () => {
        assert.strictEqual(rM29.atr.azi_15.length, 96); assert.strictEqual(rM29.atr.azi_start_utc[0], "2027-03-28T21:00Z"); preturiCorecte(rM29.atr); contigue(rM29.atr.azi_start_utc);
        assert.deepStrictEqual(rM29.atr.azi_15.slice(0, 4), [89, 90, 91, 92].map(i => fMar.opcom_preturi["2027-03-28"][i - 1].pret_lei_mwh)); });
    await T("28.03.2027: intervalAcum la 03:30 EEST (00:30Z+... = 01:30Z) și ora lipsă 03:00-04:00 EEST", async () => {
        const a = await publicaAcum(utc("2027-03-28T00:59:00Z"), fMar), b = await publicaAcum(utc("2027-03-28T01:00:00Z"), fMar);   // 02:59 EET -> 04:00 EEST
        assert.strictEqual(b.atr.interval - a.atr.interval, 1); assert.strictEqual(b.atr.interval, 13); });

    console.log("\n== 4. Verificări pe 2026-2027: față de Intl (Europe/Berlin, Europe/Bucharest) și grile complete");
    await T("ocStartCET/ocStartRO/ocCheieRO = Intl pentru fiecare zi 2026-2027", () => {
        const dtf = (tz) => new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
        const off = (tz, t) => { const p = Object.fromEntries(dtf(tz).formatToParts(new Date(t)).map(x => [x.type, x.value])); return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute) - t; };
        for (let k = "2026-01-01"; k <= "2027-12-31"; k = C.ocZiPlus(k, 1)) {
            const u = Date.parse(k + "T00:00:00Z"), c = C.ocStartCET(k), b = C.ocStartRO(k);
            assert.strictEqual(c + off("Europe/Berlin", c), u, "CET " + k); assert.strictEqual(b + off("Europe/Bucharest", b), u, "RO " + k);
            for (const t of [b, b + 3600000 * 5 + 900000, b + 86400000 - 900000, c + 7 * 3600000]) { const p = Object.fromEntries(dtf("Europe/Bucharest").formatToParts(new Date(t)).map(x => [x.type, x.value])); assert.strictEqual(C.ocCheieRO(t), `${p.year}-${p.month}-${p.day}`, "cheie " + new Date(t).toISOString()); }
        } });
    await T("an întreg (2026-2027): fiecare zi locală are 92/96/100 sloturi, fără goluri, prețul fiecărui slot corect", async () => {
        const f = {}; const store = {}; let n23 = 0, n25 = 0;
        for (let k = "2025-12-31"; k <= "2028-01-02"; k = nextKey(k)) { const n = (C.ocStartCET(nextKey(k)) - C.ocStartCET(k)) / 900000; store[k] = ocParse(csvSintetic(k, n, C), k, n); }
        function ocParse(text, k, n) { const o = []; for (let i = 1; i <= n; i++) o.push({ interval: i, pret_lei_mwh: pretSintetic(C.ocStartCET(k) + (i - 1) * 900000) }); return o; }   // fără ts_utc: calea de compatibilitate
        const r0 = [];
        for (let k = "2026-01-01"; k <= "2027-12-31"; k = nextKey(k)) {
            const tzNow = C.ocStartRO(k) + 7 * 3600000 + 600000;
            const s = { [C.ocZiPlus(k, -1)]: store[C.ocZiPlus(k, -1)], [k]: store[k], [nextKey(k)]: store[nextKey(k)] };
            const x = await publicaAcum(tzNow, { opcom_preturi: s }); const n = (C.ocStartRO(nextKey(k)) - C.ocStartRO(k)) / 900000;
            assert.strictEqual(x.atr.azi_15.length, n, k); assert.strictEqual(x.atr.maine_15.length, (C.ocStartRO(C.ocZiPlus(k, 2)) - C.ocStartRO(nextKey(k))) / 900000, "maine " + k);
            assert(!x.atr.azi_15.includes(null) && !x.atr.maine_15.includes(null), "null " + k); contigue(x.atr.azi_start_utc); contigue(x.atr.maine_start_utc); preturiCorecte(x.atr);
            x.atr.maine_start_utc.forEach((s2, i) => assert.strictEqual(x.atr.maine_15[i], pretSintetic(Date.parse(s2)), "mâine slot"));
            assert.strictEqual(x.atr.azi_60.length, n / 4); assert.strictEqual(x.atr.data_azi, k);
            if (n === 92) n23++; if (n === 100) n25++;
        }
        assert.strictEqual(n23, 2, "zile de 23 h: " + n23); assert.strictEqual(n25, 2, "zile de 25 h: " + n25);   // 29.03.2026, 28.03.2027, 25.10.2026, 31.10.2027
    });

    console.log("\n== 5. Structura JSON");
    await T("JSON valid, ID-uri unice, fără token/parolă reală, HA_TOKEN rămâne placeholder", () => {
        const ids = standalone.map(n => n.id); assert.strictEqual(new Set(ids).size, ids.length, "ID duplicate");
        const raw = fs.readFileSync(R("flows/opcom-home-assistant.json"), "utf8"); assert(!/eyJ[A-Za-z0-9_-]{20,}/.test(raw), "pare token");
        assert(raw.includes('const HA_TOKEN = \\"PUNE_AICI_TOKEN_HA\\"')); });
    await T("toate funcțiile din flux se compilează", () => { standalone.filter(n => n.type === "function").forEach(n => new vm.Script("(async function(msg){\n" + n.func + "\n})", { filename: n.name })); });

    console.log("\n== 6. Cardul (card/card_opcom.js) cu azi_start_utc, în zile de 24 h și de 25 h");
    const cardSrc = fs.readFileSync(R("card/card_opcom.js"), "utf8");
    function card(atr, state, now) {   // rulează corpul cardului cu `entity` simulat și ceasul fixat; întoarce HTML-ul
        class FD extends Date { constructor(...x) { if (x.length === 0) super(now); else super(...x); } static now() { return now; } }
        return new Function("entity", "Date", "window", cardSrc)({ state: String(state), attributes: atr }, FD, {});
    }
    const hhmm = html => (html.match(/acum (\d\d:\d\d)–(\d\d:\d\d)/) || []).slice(1);
    await T("card, 22.10.2026 21:30 EEST: ora curentă 21:00–22:00 = azi_60[21]; slotul 21:30–21:45", async () => {
        const x = await publicaAcum(now2130, flowS); const h = card(x.atr, x.stare, now2130);
        assert(h.includes("ora 21:00–22:00"), "ora"); assert(h.includes((x.atr.azi_60[21] / 1000).toFixed(3))); });
    await T("card, 25.10.2026 (25 h): 03:30 EEST și 03:30 EET folosesc ore diferite (azi_60[3] vs [4]); prima oră dublă apare 03:00–03:00", async () => {
        const e1 = await publicaAcum(utc("2026-10-25T00:30:00Z"), fOct), e2 = await publicaAcum(utc("2026-10-25T01:30:00Z"), fOct);
        const h1 = card(e1.atr, e1.stare, utc("2026-10-25T00:30:00Z")), h2 = card(e2.atr, e2.stare, utc("2026-10-25T01:30:00Z"));
        assert(h1.includes("ora 03:00–03:00") && h2.includes("ora 03:00–04:00"), (h1.match(/ora [^<]*/)||[])[0] + " / " + (h2.match(/ora [^<]*/)||[])[0]);
        assert(h1.includes((e1.atr.azi_60[3] / 1000).toFixed(3)), "EEST"); assert(h2.includes((e2.atr.azi_60[4] / 1000).toFixed(3)), "EET");
        assert.notStrictEqual(e1.atr.azi_60[3], e2.atr.azi_60[4]); });
    await T("card fără azi_start_utc (flux vechi): revine la calculul din ceas, fără eroare", async () => {
        const x = await publicaAcum(now2130, flowS); const a2 = Object.assign({}, x.atr); delete a2.azi_start_utc; delete a2.maine_start_utc;
        const h = card(a2, x.stare, now2130); assert(h.includes("PREȚ ENERGIE OPCOM")); });

    console.log(`\nRezultat: ${ok} trecute, ${bad} eșuate`);
    process.exit(bad ? 1 : 0);
})();
