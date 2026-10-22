// ===================== SETĂRI (aici modifici) =====================
const HA_URL   = "http://homeassistant.local:8123";   // adresa Home Assistant (ex. http://192.168.1.10:8123)
const HA_TOKEN = "PUNE_AICI_TOKEN_HA";                  // Profil HA → Securitate → Long-lived access token
const ENTITATE = "sensor.opcom_pret_acum";              // NU schimba: cardul citește acest senzor
// ==================================================================
// Trimite în HA prețul curent + listele pe 15/30/60 min pentru azi și mâine.
if (HA_TOKEN.startsWith("PUNE_AICI")) { node.status({ fill: "red", shape: "ring", text: "completează HA_URL și HA_TOKEN în acest nod" }); return null; }
const r2 = x => Math.round(x * 100) / 100;
const local = new Date(new Date().toLocaleString("en-US", { timeZone: "Europe/Bucharest" }));
const p = x => String(x).padStart(2, "0");
const cheie = d => d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate());
const maine = new Date(local); maine.setDate(maine.getDate() + 1);
const aziKey = cheie(local), maineKey = cheie(maine);
const opcom = flow.get("opcom_preturi") || {};
const pAzi = opcom[aziKey] || [], pMaine = opcom[maineKey] || [];
const intervalAcum = Math.floor((local.getHours() * 60 + local.getMinutes()) / 15) + 1;
const pretAcum = (pAzi.find(x => x.interval === intervalAcum) || {}).pret_lei_mwh;
function minmax(l) { const v = l.map(x => x.pret_lei_mwh); return v.length ? { min: Math.min(...v), max: Math.max(...v), medie: r2(v.reduce((a, b) => a + b, 0) / v.length) } : null; }
// prețuri pe 15 min (n=1) și medii pe 30 min (n=2) și 60 min (n=4), în ordinea intervalelor
function grupe(l, n) {
    const s = l.slice().sort((x, y) => x.interval - y.interval), out = [];
    for (let i = 0; i < s.length; i += n) { const g = s.slice(i, i + n); out.push(r2(g.reduce((a, x) => a + x.pret_lei_mwh, 0) / g.length)); }
    return out;
}
msg.url = HA_URL.replace(/\/+$/, "") + "/api/states/" + ENTITATE;
msg.method = "POST";
msg.headers = { "Authorization": "Bearer " + HA_TOKEN, "Content-Type": "application/json" };
msg.payload = {
    state: pretAcum !== undefined ? String(pretAcum) : "unknown",
    attributes: {
        interval: intervalAcum, azi: minmax(pAzi), maine: minmax(pMaine), maine_disponibil: pMaine.length > 0,
        data_azi: aziKey, data_maine: maineKey,
        azi_15: grupe(pAzi, 1), azi_30: grupe(pAzi, 2), azi_60: grupe(pAzi, 4),
        maine_15: grupe(pMaine, 1), maine_30: grupe(pMaine, 2), maine_60: grupe(pMaine, 4),
        unit_of_measurement: "lei/MWh", friendly_name: "OPCOM Pret acum", icon: "mdi:flash"
    }
};
node.status({ fill: pAzi.length ? "blue" : "yellow", shape: "dot",
    text: (pretAcum !== undefined ? pretAcum + " lei/MWh" : "fără preț azi") + " · mâine " + (pMaine.length ? "da" : "nu") });
return msg;
