// ===== OPCOM: conversie CET/CEST -> ziua locală a României (corecție fus orar, 22.10.2026) =====
// Intervalele OPCOM sunt în CET/CEST (ora României minus 1 h): intervalul 1 = 00:00-00:15 CET = 01:00-01:15 ora României.
// Pentru fiecare slot se calculează începutul în UTC (ts_utc); ziua locală se ia din ts_utc, în Europe/Bucharest.
// Calcul pur aritmetic (regula UE: ultima duminică din martie/octombrie, 01:00 UTC), fără Intl, deci la fel în orice Node.
const OC_Q = 900000, OC_H = 3600000;
const ocR2 = x => Math.round(x * 100) / 100;
function ocUltimaDuminica(an, luna) { const u = new Date(Date.UTC(an, luna + 1, 0)); return u.getUTCDate() - u.getUTCDay(); }
function ocVara(t) { const an = new Date(t).getUTCFullYear(); return t >= Date.UTC(an, 2, ocUltimaDuminica(an, 2), 1) && t < Date.UTC(an, 9, ocUltimaDuminica(an, 9), 1); }
function ocData(cheie) { const p = cheie.split("-").map(Number); return Date.UTC(p[0], p[1] - 1, p[2]); }
function ocZiPlus(cheie, n) { return new Date(ocData(cheie) + n * 86400000).toISOString().slice(0, 10); }
function ocStartCET(cheie) { const u = ocData(cheie); return u - (ocVara(u - OC_H) ? 2 : 1) * OC_H; }      // 00:00 CET/CEST al zilei OPCOM, în UTC
function ocStartRO(cheie) { const u = ocData(cheie); return u - (ocVara(u - 2 * OC_H) ? 3 : 2) * OC_H; }   // 00:00 ora României a zilei locale, în UTC
function ocCheieRO(t) { return new Date(t + (ocVara(t) ? 3 : 2) * OC_H).toISOString().slice(0, 10); }      // ziua locală (Europe/Bucharest) a unui instant UTC
function ocIso(t) { return new Date(t).toISOString().slice(0, 16) + "Z"; }                                    // ISO UTC fără secunde
function ocTsSlot(zi, interval) { return ocStartCET(zi) + (interval - 1) * OC_Q; }                            // început slot (UTC ms)
function ocHHMM(interval) { const m = (interval - 1) * 15; return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0"); }
// Grila zilei locale (96/92/100 sloturi de 15 min) umplută cu prețurile din "preturi" ({zi_opcom: [{interval, ts_utc?, pret_lei_mwh}]}); lipsă = null
function ocGrila(preturi, cheieRO) {
    const start = ocStartRO(cheieRO), n = (ocStartRO(ocZiPlus(cheieRO, 1)) - start) / OC_Q, harta = {}, opcom = {};
    [ocZiPlus(cheieRO, -1), cheieRO].forEach(z => (preturi[z] || []).forEach(p => {
        const t = p.ts_utc ? Date.parse(p.ts_utc) : ocTsSlot(z, p.interval);
        harta[t] = p.pret_lei_mwh; opcom[t] = p.interval;
    }));
    const g = { start: start, ts: [], iso: [], p15: [], intervalOpcom: [] };
    for (let i = 0; i < n; i++) { const t = start + i * OC_Q; g.ts.push(t); g.iso.push(ocIso(t)); g.p15.push(harta[t] !== undefined ? harta[t] : null); g.intervalOpcom.push(opcom[t] !== undefined ? opcom[t] : null); }
    return g;
}
function ocMedii(l, n) { const o = []; for (let i = 0; i < l.length; i += n) { const v = l.slice(i, i + n).filter(x => x !== null); o.push(v.length ? ocR2(v.reduce((a, b) => a + b, 0) / v.length) : null); } return o; }
function ocMinMax(l) { const v = l.filter(x => x !== null); return v.length ? { min: Math.min(...v), max: Math.max(...v), medie: ocR2(v.reduce((a, b) => a + b, 0) / v.length) } : null; }
// Tot ce publică senzorul: preț acum, interval (poziția în ziua locală), listele azi/mâine (15/30/60) și începuturile de slot (UTC)
function ocConstruieste(preturi, acumMs) {
    const aziKey = ocCheieRO(acumMs), maineKey = ocZiPlus(aziKey, 1);
    const azi = ocGrila(preturi, aziKey);
    const maineDisp = (preturi[maineKey] || []).length > 0;   // mâine = gol până sunt publicate prețurile zilei OPCOM de mâine
    const maine = maineDisp ? ocGrila(preturi, maineKey) : { p15: [], iso: [] };
    const idx = Math.floor((acumMs - azi.start) / OC_Q);
    const pretAcum = azi.p15[idx];
    return {
        aziKey: aziKey, maineKey: maineKey, intervalAcum: idx + 1, intervalOpcom: azi.intervalOpcom[idx],
        pretAcum: pretAcum === null || pretAcum === undefined ? undefined : pretAcum,
        azi: azi, maine: maine, maineDisponibil: maineDisp,
        atribute: {
            interval: idx + 1, interval_opcom: azi.intervalOpcom[idx], azi: ocMinMax(azi.p15), maine: ocMinMax(maine.p15), maine_disponibil: maineDisp,
            data_azi: aziKey, data_maine: maineKey,
            azi_15: azi.p15, azi_30: ocMedii(azi.p15, 2), azi_60: ocMedii(azi.p15, 4),
            maine_15: maine.p15, maine_30: ocMedii(maine.p15, 2), maine_60: ocMedii(maine.p15, 4),
            azi_start_utc: azi.iso, maine_start_utc: maine.iso
        }
    };
}
// Zilele OPCOM de cerut: ieri (sloturile 93-96 = 00:00-01:00 locală de azi), azi și, după 13:00 ora României, mâine
function ocZileDeCerut(acumMs, oraMaine) {
    const azi = ocCheieRO(acumMs), ora = new Date(acumMs + (ocVara(acumMs) ? 3 : 2) * OC_H).getUTCHours();
    const z = [ocZiPlus(azi, -1), azi]; if (ora >= (oraMaine === undefined ? 13 : oraMaine)) z.push(ocZiPlus(azi, 1));
    return z.map(k => ({ key: k, opcom: k.slice(8, 10) + "/" + k.slice(5, 7) + "/" + k.slice(0, 4) }));
}
// Parsează CSV-ul OPCOM (rânduri "Romania",interval,preț,...) în sloturi cu ts_utc
function ocParseCsv(text, zi) {
    const out = [];
    String(text).split("\n").forEach(linie => {
        linie = linie.trim(); if (!linie.startsWith('"Romania"')) return;
        const col = linie.split(",").map(c => c.replace(/"/g, "").trim());
        const interval = parseInt(col[1]), pret = parseFloat(col[2]);
        if (isNaN(interval) || isNaN(pret)) return;
        out.push({ interval: interval, ora_cet: ocHHMM(interval), ts_utc: ocIso(ocTsSlot(zi, interval)), pret_lei_mwh: pret });
    });
    return out;
}
// ===== sfârșit bloc OPCOM =====
